"""Sentry state, product signals, CI wiring and secret hygiene per unit / repo."""
from __future__ import annotations

import fnmatch
import os
import re

from .. import paths, tokens, util
from . import lockfiles

_cache: dict = {}
SENSITIVE_NAMES = [".sentryclirc", ".env.sentry-build-plugin", "sentry.properties", "SentryCliOptions.asset"]
DSN_RE = re.compile(r"https?://[a-f0-9]{32}@([^/\s\"'`]+)/(\d+)")
DSN_ENV_RE = re.compile(r"\b[A-Z0-9_]*SENTRY[A-Z0-9_]*DSN[A-Z0-9_]*\b|\bSentry__?Dsn\b|\bsentry\.dsn\b")
ENV_LINE_RE = re.compile(r"^\s*(?:export\s+)?([A-Z0-9_]*SENTRY[A-Z0-9_]*)\s*=\s*(.*)$")
TEXT_EXT = {
    ".json", ".yml", ".yaml", ".toml", ".env", ".properties", ".sh", ".bash", ".zsh", ".md", ".mdx", ".txt", ".js", ".jsx",
    ".ts", ".tsx", ".mjs", ".cjs", ".py", ".go", ".rb", ".php", ".cs", ".java", ".kt", ".kts", ".swift", ".m", ".mm", ".xml",
    ".ini", ".cfg", ".conf", ".gradle", ".plist", ".tf", ".dart", ".rs", ".ex", ".exs", ".html", ".vue", ".svelte", ".astro",
    ".pbxproj", ".xcconfig", ".entitlements", ".props", ".targets", ".csproj", ".make", ".mk", ".lock", ".asset", ".cmake", "",
}
SKIP_SRC = re.compile(r"(\.min\.|\.d\.ts$|\.pb\.go$|_pb2\.py$|\.generated\.|/generated/|\.map$)")
CONFIGISH = [
    "next.config.*", "vite.config.*", "webpack.config.*", "rollup.config.*", "esbuild*.*", "nuxt.config.*", "svelte.config.*",
    "astro.config.*", "app.config.*", "app.json", "metro.config.*", "build.gradle", "build.gradle.kts", "pom.xml", "pubspec.yaml",
    "*.csproj", "Fastfile", "Makefile", "justfile", "Taskfile.yml", "project.pbxproj", "package.json", "CMakeLists.txt",
    "wrangler.*", "Dockerfile", "Dockerfile.*", "*.sh", "tsup.config.*", "remix.config.*", "angular.json", "turbo.json",
    "Package.swift", "Podfile", "*.xcconfig", "pyproject.toml", "setup.py", "Gemfile", "composer.json", "mix.exs", "Cargo.toml",
    "build.rs", "settings.gradle", "settings.gradle.kts", "*.targets", "Directory.Build.props",
]



CTOR_RX = {
    "python": re.compile(r"^\s*[\w.]+(?:\s*:\s*[\w.\[\], ]+)?\s*=\s*(?:[\w.]+\.)?(FastAPI|Flask|Starlette|Quart|Sanic|Litestar|Celery|Bottle|Falcon|Tornado|Application)\("),
    "go": re.compile(r"\b(gin\.(?:Default|New)|echo\.New|fiber\.New|chi\.NewRouter|http\.NewServeMux|mux\.NewRouter)\("),
    "js": re.compile(r"\b(?:const|let|var)\s+\w+\s*=\s*(?:new\s+)?(express|fastify|Fastify|Koa|Hono|Elysia)\s*\("),
}



UPLOAD_OPTS = ["org", "project", "authToken", "release", "sourcemaps", "silent", "widenClientFileUpload", "telemetry", "url", "disable", "errorHandler"]
UPLOAD_OPT_RX = re.compile(r"""['"]?\b(%s)\b['"]?\s*(?:=>|[:=])\s*([^\n,;]{1,70})""" % "|".join(UPLOAD_OPTS))
TOKEN_ENV_RX = re.compile(r"SENTRY_AUTH_TOKEN|SENTRY_AUTH|SENTRY_TOKEN")


def artifact_facts(root, unit, ci_files):
    """Facts about whether a build can upload source maps / debug files: the options passed to the bundler plugin or
    withSentryConfig, and where a token could come from (CI files, build-plugin env file). Absence is the finding material."""
    sentry = unit["sentry"]
    build = {k: v for k, v in sentry.get("build", {}).items() if k != "xcode-run-script"}
    if not build:
        return None
    configs = []
    for bid, loc in build.items():
        rel, _, ln = loc.rpartition(":")
        text = _readable(root, rel, 400_000)
        if not text:
            continue
        lines = text.splitlines()
        start = max(0, int(ln) - 1)
        window = "\n".join(lines[start:start + 60])
        opts = {}
        for m in UPLOAD_OPT_RX.finditer(window):
            val = m.group(2).strip().rstrip(")").strip()
            if m.group(1) == "authToken":  # presence and source only; the value never enters detection output
                em = re.search(r"process\.env\.([A-Z_][A-Z0-9_]*)|env\[['\"]([A-Z_][A-Z0-9_]*)['\"]\]", val)
                val = "env:%s" % (em.group(1) or em.group(2)) if em else "<literal value present: not recorded>"
            opts.setdefault(m.group(1), tokens.clip(val, 60))
        configs.append({"build": bid, "file": rel, "line": int(ln), "options": opts})
    refs = []
    for rel in ci_files:
        text = _readable(root, rel, 200_000)
        if text and TOKEN_ENV_RX.search(text):
            refs.append({"kind": "ci-file", "file": rel})
    udir = unit["root"] if unit["root"] != "." else ""
    for name in (".env.sentry-build-plugin", ".sentryclirc", "sentry.properties"):
        p = os.path.join(udir, name) if udir else name
        if os.path.exists(os.path.join(root, p)):
            refs.append({"kind": "file", "file": p})
    return {"configs": configs, "token_sources": refs,
            "note": "token_sources empty and no org/project/authToken in options means the build has no way to authenticate an upload"}


def _local_roots(unit, eco):
    """Top-level names a `from x import` can refer to inside this repo (Python: packages and root modules)."""
    roots = set()
    if eco != "python":
        return roots
    base = unit["root"] if unit["root"] != "." else ""
    for rel in unit.get("_files", []):
        if not rel.endswith(".py"):
            continue
        sub = rel[len(base) + 1:] if base and rel.startswith(base + "/") else rel
        parts = sub.split("/")
        roots.add(parts[0][:-3] if len(parts) == 1 else parts[0])
    return roots


def _placement(eco, lines, init_line, local_roots):
    """Facts about what runs before Sentry.init in the same file: app constructors and imports of the repo's own modules."""
    rx = CTOR_RX.get(eco)
    ctors, local = [], []
    for i, line in enumerate(lines[: max(0, init_line - 1)], 1):
        if rx and rx.search(line) and len(ctors) < 3:
            ctors.append({"line": i, "text": tokens.clip(line.strip(), 100)})
        if eco == "python":
            m = re.match(r"^\s*(?:from\s+(\.+|[A-Za-z_][\w]*)[\w.]*\s+import|import\s+([A-Za-z_][\w]*))", line)
            if m:
                top = m.group(1) or m.group(2)
                if top.startswith(".") or top in local_roots:
                    if len(local) < 5:
                        local.append({"line": i, "text": tokens.clip(line.strip(), 100)})
    return {"app_ctor_before": ctors, "local_imports_before": local}


def data(name):
    if name not in _cache:
        _cache[name] = paths.load_json_data("detect", name)
    return _cache[name]


def _signal_rows():
    if "sigrows" not in _cache:
        rows = []
        with open(paths.data_path("detect", "signal_deps.tsv"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                cat, eco, pat = line.rstrip("\n").split("\t")
                rows.append((cat, eco, re.compile("^(?:%s)$" % pat)))
        _cache["sigrows"] = rows
    return _cache["sigrows"]


def _delim_prefix(name: str, prefix: str) -> bool:
    if prefix and prefix[-1] in "/:._-":
        return name.startswith(prefix)
    return name == prefix or name.startswith(prefix + "-") or name.startswith(prefix + "_") or name.startswith(prefix + ".") or name.startswith(prefix + "/") or name.startswith(prefix + ":")


def is_sdk_dep(name: str, spec: dict) -> bool:
    return any(_delim_prefix(name, p) for p in spec["sdk_prefixes"]) or name in spec.get("sdk_exact", [])


def _legacy_note(name: str, spec: dict):
    for k, note in spec.get("legacy", {}).items():
        if name == k or _delim_prefix(name, k):
            return note
    return None


def _region(host: str):
    m = re.match(r"o\d+\.ingest\.(de|us)\.sentry\.io$", host)
    if m:
        return m.group(1)
    if re.match(r"o\d+\.ingest\.sentry\.io$", host):
        return "us"
    return "self-hosted-or-custom"


def _readable(root, rel, limit=300_000):
    p = os.path.join(root, rel)
    try:
        if os.path.getsize(p) > limit * 4:
            return ""
    except OSError:
        return ""
    return util.read_text(p, limit)


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def attach(unit: dict, root: str, udir: str, tracked: set) -> None:
    eco = unit["ecosystem"]
    spec = unit["_spec"]
    deps = unit["_deps"]
    # --- packages
    sdk_names = [n for n in deps if is_sdk_dep(n, spec)]
    legacy = []
    for n in deps:
        note = _legacy_note(n, spec)
        if note:
            legacy.append({"name": n, "note": note})
    resolved = lockfiles.resolve(eco, udir, root, sdk_names)
    tooling_rx = [re.compile(t) for t in spec.get("tooling", [])]
    packages = []
    for n in sorted(sdk_names):
        declared = deps.get(n) or ""
        res = resolved.get(n)
        if not res and eco in ("go",) and declared:
            res = declared.lstrip("v")
        if not res and eco in ("jvm", "dotnet", "dart", "elixir") and re.match(r"^\d+(\.\d+)*$", declared or ""):
            res = declared
        pkg = {"name": n, "declared": declared or None, "resolved": res}
        if any(t.match(n) for t in tooling_rx):
            pkg["kind"] = "tooling"
        if eco == "unity" and not res and "#" in declared:
            pkg["resolved"] = declared.split("#", 1)[1].lstrip("v")
        packages.append(pkg)
    # --- single pass over unit sources
    init_sites, dsn_literals, env_names, sig_src = [], [], {}, {}
    local_roots = _local_roots(unit, eco)
    init_rx = re.compile("|".join("(?:%s)" % p for p in spec["init_patterns"]))
    opt_names = data("option_names.json")["options"]
    opt_rx = re.compile(r"""['"]?\b(%s)\b['"]?\s*(?:=>|[:=])\s*([^\n,;]{1,80})""" % "|".join(re.escape(o) for o in opt_names))
    src_sigs = [(s, re.compile(s["regex"])) for s in data("source_signals.json") if s["eco"] in (eco, "*") and s["category"] != "public_url"]
    exts = set(spec["src_exts"])
    scanned = 0
    option_snapshots = []
    for rel in unit["_files"]:
        ext = os.path.splitext(rel)[1]
        if ext not in exts or SKIP_SRC.search(rel):
            continue
        scanned += 1
        if scanned > 4000:
            break
        text = _readable(root, rel)
        if not text:
            continue
        for s, rx in src_sigs:
            if rx.search(text):
                sig_src.setdefault(s["category"], {}).setdefault(s["value"], rel)
        if "sentry" not in text.lower() and "Sentry" not in text:
            continue
        m_init = init_rx.search(text)
        if m_init:
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                if init_rx.search(line) and len(init_sites) < 25:
                    init_sites.append({"file": rel, "line": i, "text": tokens.clip(line.strip(), 140), "placement": _placement(eco, lines, i, local_roots)})
            if len(option_snapshots) < 4:
                start = max(0, _line_of(text, m_init.start()) - 6)
                window = "\n".join(lines[start:start + 90])
                opts = {}
                for m in opt_rx.finditer(window):
                    opts.setdefault(m.group(1), tokens.clip(m.group(2).strip().rstrip(")").strip(), 80))
                option_snapshots.append({"file": rel, "options": opts})
        for m in DSN_RE.finditer(text):
            host = m.group(1)
            dsn_literals.append({"file": rel, "line": _line_of(text, m.start()), "host": host, "project_id": m.group(2), "region": _region(host)})
        for m in DSN_ENV_RE.finditer(text):
            env_names.setdefault(m.group(0), {"kind": "code", "name": m.group(0), "file": rel, "line": _line_of(text, m.start())})
    # --- env / properties / config files (names only; values of untracked files are never read for DSNs)
    cfg_hits = []
    n_cfg = 0
    for rel in unit["_files"]:
        base = os.path.basename(rel)
        depth = rel.count("/") - (0 if unit["root"] == "." else unit["root"].count("/") + 1)
        if depth > 2:
            continue
        if base.startswith(".env") or fnmatch.fnmatch(base, "*.properties") or base in ("sentry.properties",):
            n_cfg += 1
            if n_cfg > 60:
                break
            text = util.read_text(os.path.join(root, rel), 60_000)
            for i, line in enumerate(text.splitlines(), 1):
                m = ENV_LINE_RE.match(line)
                if m:
                    env_names.setdefault(m.group(1), {"kind": "env-file", "name": m.group(1), "file": rel, "line": i, "has_value": bool(m.group(2).strip().strip("\"'"))})
                if base.endswith(".properties") and re.match(r"^\s*(sentry\.)?dsn\s*=", line):
                    env_names.setdefault("properties:dsn", {"kind": "properties", "name": "dsn", "file": rel, "line": i})
                mm = DSN_RE.search(line)
                if mm and rel in tracked:
                    dsn_literals.append({"file": rel, "line": i, "host": mm.group(1), "project_id": mm.group(2), "region": _region(mm.group(1))})
    # --- config-driven init (the SDK is configured in a file instead of an init call)
    cfg_init = spec.get("config_init", [])
    if cfg_init:
        n_ci = 0
        for rel in unit["_files"]:
            base = os.path.basename(rel)
            for ci in cfg_init:
                if fnmatch.fnmatch(base, ci["glob"]) and (not ci.get("path") or fnmatch.fnmatch(rel, ci["path"])):
                    n_ci += 1
                    if n_ci > 80:
                        break
                    text = _readable(root, rel, 200_000)
                    m = re.search(ci["regex"], text)
                    if m and len(init_sites) < 25:
                        init_sites.append({"file": rel, "line": _line_of(text, m.start()), "text": tokens.clip(text.splitlines()[_line_of(text, m.start()) - 1].strip(), 140), "kind": "config"})
                        lines = text.splitlines()
                        opts = {}
                        for mm in opt_rx.finditer("\n".join(lines[:200])):
                            opts.setdefault(mm.group(1), tokens.clip(mm.group(2).strip().rstrip(")").strip(), 80))
                        if len(option_snapshots) < 6:
                            option_snapshots.append({"file": rel, "options": opts, "kind": "config"})
                        for dm in DSN_RE.finditer(text):
                            dsn_literals.append({"file": rel, "line": _line_of(text, dm.start()), "host": dm.group(1), "project_id": dm.group(2), "region": _region(dm.group(1))})
                        for em in DSN_ENV_RE.finditer(text):
                            env_names.setdefault(em.group(0), {"kind": "config", "name": em.group(0), "file": rel, "line": _line_of(text, em.start())})
    # --- config files present
    config_files = []
    cfg_patterns = spec["config_names"]
    for rel in unit["_files"]:
        base = os.path.basename(rel)
        if any(fnmatch.fnmatch(base, p) for p in cfg_patterns) and base not in ("application.properties", "application.yml", "application.yaml", "appsettings.json", "logback.xml", "log4j2.xml", "AndroidManifest.xml", "Info.plist", "pubspec.yaml", "config.exs", "runtime.exs", "prod.exs", "DefaultEngine.ini", "*.entitlements") and not rel.endswith(".entitlements"):
            config_files.append(rel)
    # --- build wiring
    bpats = [(b["id"], re.compile(b["regex"])) for b in data("build_patterns.json")]
    build, n_b = {}, 0
    for rel in unit["_files"]:
        base = os.path.basename(rel)
        if any(fnmatch.fnmatch(base, p) for p in CONFIGISH):
            n_b += 1
            if n_b > 400:
                break
            text = _readable(root, rel, 400_000)
            if not text:
                continue
            for bid, rx in bpats:
                m = rx.search(text)
                if m and bid not in build:
                    build[bid] = "%s:%d" % (rel, _line_of(text, m.start()))
    if unit["_meta"].get("run_script_sentry"):
        build.setdefault("xcode-run-script", unit["manifests"][0])
    # --- status
    if packages and init_sites:
        status = "present"
    elif packages and not init_sites:
        status = "partial"
    elif init_sites and not packages:
        status = "partial"
    elif legacy:
        status = "legacy"
    else:
        status = "absent"
    notes = []
    if packages and not init_sites:
        notes.append("SDK declared but no init call found in this unit (initialized elsewhere, or never)")
    if init_sites and not packages:
        notes.append("init call found but the SDK is not declared in this unit's manifests (hoisted or shared dependency?)")
    majors = sorted({(p["resolved"] or "").split(".")[0] for p in packages if p["resolved"] and p.get("kind") != "tooling"})
    if len(majors) > 1:
        notes.append("multiple SDK majors resolved: %s" % ", ".join(majors))
    unit["sentry"] = {
        "status": status, "packages": packages, "legacy": legacy, "init_sites": init_sites,
        "config_snapshot": option_snapshots, "dsn_sources": sorted(env_names.values(), key=lambda x: (x["file"], x["line"])),
        "dsn_literals": dsn_literals[:10], "config_files": sorted(config_files)[:20], "build": build, "notes": notes,
    }
    # --- signals
    sig: dict = {}
    allnames = list(deps.keys())
    for cat, e, rx in _signal_rows():
        if e != eco:
            continue
        for n in allnames:
            if rx.match(n):
                sig.setdefault(cat, [])
                if n not in sig[cat]:
                    sig[cat].append(n)
    for cat, vals in sig_src.items():
        for v, rel in vals.items():
            sig.setdefault(cat, []).append("%s (%s)" % (v, rel))
    udir_files = unit["_files"]
    fs = data("file_signals.json")["files"]
    fcount = 0
    for rel in udir_files:
        base = os.path.basename(rel)
        for f in fs:
            pat = f["match"]
            if fnmatch.fnmatch(base, pat) or fnmatch.fnmatch(rel, pat):
                if f.get("content"):
                    fcount += 1
                    if fcount > 400:
                        continue
                    if not re.search(f["content"], util.read_text(os.path.join(root, rel), 200_000)):
                        continue
                sig.setdefault(f["category"], [])
                v = "%s (%s)" % (f["value"], rel)
                if v not in sig[f["category"]]:
                    sig[f["category"]].append(v)
    # public URL hints
    url_rule = [s for s in data("source_signals.json") if s["category"] == "public_url"]
    if url_rule:
        rx = re.compile(url_rule[0]["regex"])
        names = set(url_rule[0]["files"])
        for rel in udir_files:
            if os.path.basename(rel) in names:
                text = util.read_text(os.path.join(root, rel), 100_000)
                for m in rx.finditer(text):
                    sig.setdefault("public_url", [])
                    if len(sig["public_url"]) < 6 and m.group(0) not in sig["public_url"]:
                        sig["public_url"].append(m.group(0))
    if unit["_meta"].get("homepage"):
        sig.setdefault("public_url", []).append(str(unit["_meta"]["homepage"]))
    unit["signals"] = {k: v[:12] for k, v in sorted(sig.items())}
    # --- sensitive credential files next to the unit (existence + git status only)
    sens = {}
    for name in SENSITIVE_NAMES:
        for base_dir in {udir, root}:
            p = os.path.join(base_dir, name)
            if os.path.isfile(p):
                rel = os.path.relpath(p, root)
                sens[rel] = _git_state(root, rel, tracked)
    unit["secrets"] = {"sensitive_files": sens}


def _git_state(root, rel, tracked):
    if not util.is_git_repo(root):
        return "unknown (not a git repo)"
    if rel in tracked:
        return "tracked"
    rc, _, _ = util.git(root, "check-ignore", "-q", rel)
    return "ignored" if rc == 0 else "untracked-not-ignored"


def repo_signals(root, files, outside, units, tracked):
    fs = data("file_signals.json")
    bpats = {b["id"]: re.compile(b["regex"]) for b in data("build_patterns.json")}
    ci_providers, ci_files = set(), []
    for rel in files:
        for c in fs["ci"]:
            if c["ci"] and (fnmatch.fnmatch(rel, c["match"]) or rel == c["match"]):
                ci_providers.add(c["ci"])
                ci_files.append((rel, c["ci"]))
    sentry_refs, deploy, scheduler = [], [], []
    script_files = [r for r in files if os.path.basename(r) in ("Makefile", "justfile", "Taskfile.yml", "Taskfile.yaml") or r.endswith(".sh") or os.path.basename(r).startswith("Dockerfile")]
    for rel, prov in [(r, p) for r, p in ci_files[:120]] + [(r, "script") for r in script_files[:120] if r not in {c for c, _ in ci_files}]:
        text = _readable(root, rel)
        if not text:
            continue
        has_setx = bool(re.search(r"(?m)^\s*set\s+-[a-z]*x", text)) or "ACTIONS_STEP_DEBUG" in text
        for bid in ("sentry-cli-v3", "sentry-v4-cli", "wizard", "github-action-release", "sentry-upload-ci", "token-on-command-line"):
            for m in bpats[bid].finditer(text):
                line_no = _line_of(text, m.start())
                line = text.splitlines()[line_no - 1].strip()
                sentry_refs.append({"file": rel, "line": line_no, "kind": bid, "where": "script" if prov == "script" else "ci", "text": tokens.clip(line.strip(), 140), "set_x_in_file": has_setx})
                if len(sentry_refs) > 160:
                    break
        for cc in fs["ci_content"]:
            if cc.get("only") and cc["only"] != prov:
                continue
            if re.search(cc["regex"], text):
                (deploy if cc["category"] == "deploy" else scheduler).append({"file": rel, "value": cc["value"]})
    # secrets scan over text files
    hits, scanned_bytes, nfiles = [], 0, 0
    hint = re.compile(r"(?i)sentry_auth_token|sentry_token|authtoken|auth\.token|auth_token|client_secret")
    for rel in files:
        ext = os.path.splitext(rel)[1].lower()
        base = os.path.basename(rel)
        if ext not in TEXT_EXT and not base.startswith(".env") and base not in ("Dockerfile", "Makefile", "Fastfile", "Podfile", "Gemfile", "Procfile"):
            continue
        nfiles += 1
        if nfiles > 20000 or scanned_bytes > 80_000_000:
            break
        p = os.path.join(root, rel)
        try:
            sz = os.path.getsize(p)
        except OSError:
            continue
        if sz > 1_000_000:
            continue
        text = util.read_text(p, 1_000_000)
        scanned_bytes += len(text)
        if "sntry" not in text and not hint.search(text):
            continue
        for kind, s, e in tokens.find_tokens(text):
            ln = _line_of(text, s)
            hits.append({"file": rel, "line": ln, "kind": kind, "tracked": rel in tracked})
            if len(hits) > 200:
                break
    sec = {"token_hits": hits[:100], "token_hits_total": len(hits), "tracked_token_hits": sum(1 for h in hits if h["tracked"])}
    for u in units:
        pre = "" if u["root"] == "." else u["root"] + "/"
        mine = [h for h in hits if (u["root"] == "." or h["file"].startswith(pre))]
        u["secrets"]["token_hits"] = len(mine)
        u["secrets"]["tracked_token_hits"] = sum(1 for h in mine if h["tracked"])
    iac = sorted({rel for rel in files if rel.endswith(".tf") and re.search(r"jianyuan/sentry|sentry_project|sentry_key|sentry_issue_alert|sentry_metric_alert|sentry_", util.read_text(os.path.join(root, rel), 100_000))})[:10]
    return {"ci": {"providers": sorted(ci_providers), "files": [r for r, _ in ci_files][:30], "script_files_scanned": len(script_files), "sentry_refs": sentry_refs[:120], "deploy": deploy[:12], "scheduler": scheduler[:12]},
            "secrets": sec, "iac": {"terraform_sentry_files": iac}}
