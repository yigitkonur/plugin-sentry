"""Repo detection: units, ecosystems, frameworks, roles. Decisions come from data/detect/*.json;
no ecosystem name appears in this algorithm."""
from __future__ import annotations

import fnmatch
import os
import re
import time

from .. import cli_tools, paths, util
from . import lockfiles, manifests, sentry_state

SKIP_UNIT_SEGMENTS = {
    "examples", "example", "fixtures", "__fixtures__", "test", "tests", "__tests__", "e2e", "docs", "doc",
    "samples", "sample", "benchmark", "benchmarks", "testdata", "third_party", "third-party",
}
WORKSPACE_FILES = ["pnpm-workspace.yaml", "turbo.json", "nx.json", "lerna.json", "go.work", "rush.json"]
NATIVE_CHILD_DIRS = {"ios", "android", "macos", "windows", "linux", "web"}
FOLD_INTO = {"react-native", "expo", "flutter", "cordova"}

_cache: dict = {}


def data(name):
    if name not in _cache:
        _cache[name] = paths.load_json_data("detect", name)
    return _cache[name]


def _match_manifest(rel: str):
    base = os.path.basename(rel)
    parent = os.path.basename(os.path.dirname(rel))
    for eco, spec in data("ecosystems.json").items():
        for pat in spec["manifests"]:
            if "@" in pat:
                name, par = pat.split("@")
                if base == name and parent == par:
                    return eco, 2
            elif fnmatch.fnmatch(base, pat):
                return eco, (2 if base == "project.pbxproj" else 0)
    return None, 0


def _slug(rel_dir: str, taken: set, repo_name: str) -> str:
    if rel_dir in (".", ""):
        base = re.sub(r"[^a-z0-9]+", "-", repo_name.lower()).strip("-") or "app"
        base = "app" if base in ("", ".") else base
    else:
        base = os.path.basename(rel_dir)
    cand, n = base, 2
    if cand in taken:
        cand = re.sub(r"[^A-Za-z0-9]+", "-", rel_dir).strip("-")
    while cand in taken:
        cand = "%s-%d" % (base, n)
        n += 1
    taken.add(cand)
    return cand


def _scm(root):
    rc, out, _ = util.git(root, "remote", "get-url", "origin")
    url = out.strip() if rc == 0 else ""
    provider = None
    for needle, name in (("github.com", "github"), ("gitlab", "gitlab"), ("bitbucket", "bitbucket"), ("dev.azure.com", "azure-devops"), ("visualstudio.com", "azure-devops")):
        if needle in url:
            provider = name
            break
    # never echo credentials embedded in a remote URL
    safe = re.sub(r"//[^@/]+@", "//", url)
    return provider, safe


def _default_branch(root):
    rc, out, _ = util.git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if rc == 0 and out.strip():
        return out.strip().split("/", 1)[-1]
    rc, out, _ = util.git(root, "rev-parse", "--abbrev-ref", "HEAD")
    return out.strip() if rc == 0 else None


def _framework_for(unit, texts_hint=None):
    """Most specific wins; overlay frameworks (e.g. Cloudflare) never displace a primary framework."""
    eco = unit["ecosystem"]
    depnames = list(unit["_deps"].keys())
    best = None
    overlays = []
    for rule in data("frameworks.json"):
        if rule["eco"] != eco:
            continue
        rx = re.compile("^(?:%s)$" % rule["dep"])
        hit = None
        if rule["dep"].startswith("__"):
            hit = rule["dep"] if rule["dep"] in unit["_deps"] else None
        elif rule["dep"] == ".*":
            hit = "(default)"
        else:
            for d in depnames:
                if rx.match(d):
                    hit = d
                    break
        if not hit:
            continue
        if rule.get("overlay"):
            overlays.append(rule["id"])
            continue
        if best is None or rule["priority"] > best[0]["priority"]:
            best = (rule, hit)
    if best is None:
        return None, None, overlays
    return best[0], best[1], overlays


def detect(root: str, include_tests: bool = False) -> dict:
    t0 = time.time()
    root = os.path.abspath(root)
    files, truncated, file_source = util.list_repo_files(root)
    tracked = set()
    if util.is_git_repo(root):
        rc, out, _ = util.git(root, "ls-files", "-z")
        tracked = set(p for p in out.split("\0") if p)
    fileset = set(files)

    # ---- 1. manifest candidates grouped by (dir, ecosystem)
    groups: dict = {}
    for rel in files:
        eco, up = _match_manifest(rel)
        if not eco:
            continue
        d = os.path.dirname(rel)
        for _ in range(up // 2 if up else 0):
            d = os.path.dirname(d)
        d = d or "."
        segs = [] if d == "." else d.split("/")
        if not include_tests and any(s.lower() in SKIP_UNIT_SEGMENTS for s in segs):
            continue
        groups.setdefault((d, eco), []).append(rel)

    # ---- 2. parse manifests -> candidate units
    cands = []
    for (d, eco), mans in sorted(groups.items()):
        deps, meta, parsed = {}, {}, []
        for m in sorted(mans):
            text = util.read_text(os.path.join(root, m), 2_000_000)
            r = manifests.parse(m, text)
            parsed.append(m)
            for k, v in r["deps"].items():
                deps.setdefault(k, v)
            for k, v in r["meta"].items():
                meta.setdefault(k, v)
        if eco == "js" and not deps and not meta.get("name") and not meta.get("scripts"):
            continue
        cands.append({"root": d, "ecosystem": eco, "manifests": parsed, "_deps": deps, "meta": meta})

    # ---- 3. workspace roots without their own app signals are not units
    dirs_with_markers = set()
    for rel in files:
        if os.path.basename(rel) in WORKSPACE_FILES or os.path.basename(rel) in ("settings.gradle", "settings.gradle.kts"):
            dirs_with_markers.add(os.path.dirname(rel) or ".")
    for c in cands:
        m = c["meta"]
        c["workspace_root"] = bool(
            c["root"] in dirs_with_markers or m.get("workspaces") or m.get("workspace_members") or m.get("modules")
        )

    def has_children(c):
        pre = "" if c["root"] == "." else c["root"] + "/"
        return any(o is not c and o["root"] != c["root"] and (c["root"] == "." or o["root"].startswith(pre)) for o in cands)

    def sdk_dep(c):
        spec = data("ecosystems.json")[c["ecosystem"]]
        return any(sentry_state.is_sdk_dep(k, spec) for k in c["_deps"])

    kept = []
    for c in cands:
        if c["workspace_root"] and has_children(c) and not sdk_dep(c):
            rule, _, _ = _framework_for(c)
            if rule is None or rule["priority"] <= 10:
                continue
        kept.append(c)
    cands = kept

    # ---- 4. frameworks, folding native subprojects into cross-platform parents
    for c in cands:
        rule, hit, overlays = _framework_for(c)
        c["_rule"], c["_hit"], c["overlays"] = rule, hit, overlays
    folded = set()
    for p in cands:
        if p["_rule"] and p["_rule"]["id"] in FOLD_INTO:
            pre = "" if p["root"] == "." else p["root"] + "/"
            for ch in cands:
                if ch is p:
                    continue
                rel = ch["root"][len(pre):] if ch["root"].startswith(pre) else None
                if rel and rel.split("/")[0] in NATIVE_CHILD_DIRS:
                    folded.add(id(ch))
                    p.setdefault("native_subprojects", []).append({"root": ch["root"], "ecosystem": ch["ecosystem"]})
                    for k, v in ch["_deps"].items():
                        p.setdefault("_native_deps", {}).setdefault(k, v)
    cands = [c for c in cands if id(c) not in folded]

    # ---- 5. assign files to the deepest unit
    cands.sort(key=lambda c: (c["root"] != ".", c["root"]))
    roots_sorted = sorted(cands, key=lambda c: -len(c["root"]))
    unit_files = {id(c): [] for c in cands}
    outside = []
    for rel in files:
        owner = None
        for c in roots_sorted:
            if c["root"] == "." or rel == c["root"] or rel.startswith(c["root"] + "/"):
                owner = c
                break
        (unit_files[id(owner)] if owner else outside).append(rel)

    repo_name = os.path.basename(root)
    taken: set = set()
    units = []
    for c in cands:
        uid = _slug(c["root"], taken, repo_name)
        spec = data("ecosystems.json")[c["ecosystem"]]
        ufiles = unit_files[id(c)]
        unit = {
            "id": uid, "root": c["root"], "ecosystem": c["ecosystem"], "manifests": c["manifests"],
            "framework": None, "framework_label": None, "framework_version": None,
            "overlays": c["overlays"], "role": "unknown", "platforms": [],
            "package_manager": None, "library": False,
            "_deps": c["_deps"], "_meta": c["meta"], "_files": ufiles, "_spec": spec,
        }
        if c.get("native_subprojects"):
            unit["native_subprojects"] = c["native_subprojects"]
        for k, v in c.get("_native_deps", {}).items():
            unit["_deps"].setdefault(k, v)
        units.append((unit, c))

    result_units = []
    for unit, c in units:
        udir = os.path.join(root, unit["root"])
        _classify(unit, c, root, udir, fileset)
        sentry_state.attach(unit, root, udir, tracked)
        result_units.append(unit)

    # ---- 6. repo-level facts
    provider, remote = _scm(root)
    repo_level = sentry_state.repo_signals(root, files, outside, result_units, tracked)
    dirty = False
    if util.is_git_repo(root):
        rc, out, _ = util.git(root, "status", "--porcelain")
        dirty = bool(out.strip())
    for u in result_units:
        for k in ("_deps", "_meta", "_files", "_spec"):
            u.pop(k, None)
    return {
        "schema": 1,
        "repo": {
            "root": ".", "name": repo_name, "git": util.is_git_repo(root), "dirty": dirty, "scm": provider,
            "remote": remote or None, "default_branch": _default_branch(root) if util.is_git_repo(root) else None,
            "files_scanned": len(files), "truncated": truncated, "file_source": file_source,
            "workspace_files": sorted(dirs_with_markers),
        },
        "units": result_units,
        "ci": repo_level["ci"],
        "secrets": repo_level["secrets"],
        "iac": repo_level["iac"],
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


def _classify(unit, c, root, udir, fileset):
    eco = unit["ecosystem"]
    rule = c["_rule"]
    deps, meta = unit["_deps"], unit["_meta"]
    unit["framework"] = rule["id"] if rule else None
    unit["framework_label"] = rule["label"] if rule else None
    unit["framework_module"] = rule.get("module") if rule else None
    unit["docs_platform"] = rule.get("docs_platform") if rule else None
    unit["wizard"] = rule.get("wizard") if rule else None
    role = rule["role"] if rule else "unknown"
    pm = meta.get("package_manager")
    if eco == "js":
        for fn, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"), ("bun.lockb", "bun"), ("package-lock.json", "npm")):
            if lockfiles._find(udir, root, [fn]):
                unit["package_manager"] = name
                break
        if not unit["package_manager"] and pm:
            unit["package_manager"] = str(pm).split("@")[0]
    elif eco == "python":
        for fn, name in (("uv.lock", "uv"), ("poetry.lock", "poetry"), ("Pipfile.lock", "pipenv"), ("pdm.lock", "pdm")):
            if lockfiles._find(udir, root, [fn]):
                unit["package_manager"] = name
                break
        unit["package_manager"] = unit["package_manager"] or "pip"
    # resolved versions for the framework dependency
    if unit["framework"] and c["_hit"] and c["_hit"] not in ("(default)",):
        res = lockfiles.resolve(eco, udir, root, [c["_hit"]])
        unit["framework_version"] = res.get(c["_hit"]) or _clean_spec(deps.get(c["_hit"]))
    # ----- ecosystem-independent library / role refinements driven by manifest meta
    src_text_cache: dict = {}

    def grep_src(regex, exts, limit=400):
        rx = re.compile(regex)
        n = 0
        for rel in unit["_files"]:
            if os.path.splitext(rel)[1] in exts:
                n += 1
                if n > limit:
                    break
                if rx.search(src_text_cache.setdefault(rel, util.read_text(os.path.join(root, rel), 200_000))):
                    return rel
        return None

    generic = (rule is None) or rule["priority"] <= 10
    if eco == "js":
        scripts = set(meta.get("scripts") or [])
        peers = set(meta.get("peer") or [])
        if generic or unit["framework"] in ("react", "vue", "svelte", "solid", "angular"):
            looks_lib = meta.get("has_main") and not (scripts & {"start", "dev", "serve", "preview"}) and not meta.get("private")
            if looks_lib or (peers and meta.get("has_main") and not meta.get("private")):
                role = "library"
        if unit["framework"] in ("node", None) and role != "library":
            if meta.get("has_bin") and not (scripts & {"start", "dev", "serve"}):
                role = "cli"
            elif unit["framework"] == "node" or scripts & {"start", "dev", "serve"}:
                role = "backend" if (scripts & {"start", "serve"} or "server" in str(meta.get("name"))) else "backend"
    elif eco == "python":
        if unit["framework"] == "python":
            if meta.get("has_scripts"):
                role = "cli"
            elif meta.get("has_build_system") and not meta.get("has_setup"):
                role = "library"
            elif meta.get("has_setup") and not grep_src(r"__main__|argparse|click|typer", {".py"}, 60):
                role = "library"
            else:
                role = "backend" if not meta.get("has_scripts") and grep_src(r"uvicorn|gunicorn|flask|app\.run", {".py"}, 60) else "cli"
        if unit["framework"] == "celery":
            role = "worker"
    elif eco == "go":
        has_main = grep_src(r"(?m)^package main\b", {".go"}, 800)
        if not has_main:
            role = "library"
        elif unit["framework"] == "go":
            role = "backend" if grep_src(r"net/http|ListenAndServe|grpc\.NewServer", {".go"}, 800) else "cli"
    elif eco == "rust":
        if meta.get("has_lib") and not meta.get("has_bin") and ("src/main.rs" not in {os.path.relpath(f, unit["root"]) if unit["root"] != "." else f for f in unit["_files"]}):
            role = "library"
        elif unit["framework"] == "rust":
            role = "cli"
    elif eco == "ruby":
        if any(f.endswith(".gemspec") for f in unit["_files"]) and unit["framework"] in ("ruby", "rack", None):
            role = "library"
    elif eco == "php":
        if meta.get("type") == "library":
            role = "library"
    elif eco == "dotnet":
        ot = (meta.get("output_type") or "").lower()
        if ot == "library" or (not ot and unit["framework"] == "dotnet" and not (meta.get("sdk") or "").endswith("Web")):
            role = "library" if ot == "library" else role
        if ot == "winexe" and unit["framework"] == "dotnet":
            role = "desktop"
        if ot == "exe" and unit["framework"] == "dotnet":
            role = "cli"
    elif eco == "jvm":
        if unit["framework"] == "jvm":
            role = "backend" if meta.get("packaging") in ("war",) else "unknown"
        if meta.get("android"):
            unit["framework"], unit["framework_label"], role = "android", "Android", "mobile"
            unit["framework_module"], unit["docs_platform"], unit["wizard"] = "platforms/android", "android", "android"
    elif eco == "elixir":
        pass
    elif eco == "dart":
        if unit["framework"] == "dart" and not grep_src(r"void main\(", {".dart"}, 100):
            role = "library"
    elif eco == "apple":
        _apple(unit, root, udir, meta, deps, grep_src)
        role = unit["role"]
    unit["role"] = role
    unit["library"] = role == "library"
    unit["confidence"] = 0.95 if (rule and rule["priority"] > 10) else (0.7 if rule else 0.5)
    unit["evidence"] = {"framework": ["%s:deps:%s" % (unit["manifests"][0], c["_hit"])] if c["_hit"] and c["_hit"] != "(default)" else unit["manifests"][:1]}
    if unit["framework"] == "node" and "cloudflare" in unit["overlays"]:
        unit["framework"], unit["framework_label"] = "cloudflare", "Cloudflare Workers / Pages"
        unit["framework_module"], unit["docs_platform"], unit["wizard"] = "platforms/cloudflare", "javascript/guides/cloudflare", "cloudflare"
        unit["role"] = "serverless"
    if "cloudflare" in unit["overlays"] and unit["role"] in ("backend", "unknown", "fullstack") and unit["framework"] in ("hono", "node"):
        unit["role"] = "serverless"


def _clean_spec(spec):
    if not spec:
        return None
    m = re.search(r"\d+(\.\d+){0,2}", str(spec))
    return m.group(0) if m else None


def _apple(unit, root, udir, meta, deps, grep_src):
    plats = set(meta.get("platforms") or [])
    sdkroots = set(meta.get("sdkroots") or [])
    for r in sdkroots:
        plats.add({"macosx": "macos", "iphoneos": "ios", "iphonesimulator": "ios", "appletvos": "tvos", "watchos": "watchos", "xros": "visionos"}.get(r, r))
    if meta.get("macos_deployment"):
        plats.add("macos")
    if meta.get("ios_deployment"):
        plats.add("ios")
    for sp in meta.get("supported_platforms") or []:
        for tok in sp.split():
            t = {"macosx": "macos", "iphoneos": "ios", "iphonesimulator": "ios", "appletvos": "tvos", "watchos": "watchos", "xros": "visionos"}.get(tok)
            if t:
                plats.add(t)
    unit["platforms"] = sorted(plats)
    ui = []
    if grep_src(r"(?m)^\s*import\s+SwiftUI\b", {".swift"}, 300):
        ui.append("swiftui")
    if grep_src(r"(?m)^\s*import\s+AppKit\b|NSApplicationDelegate", {".swift", ".m", ".mm"}, 300):
        ui.append("appkit")
    if grep_src(r"(?m)^\s*import\s+UIKit\b|UIApplicationDelegate", {".swift", ".m", ".mm"}, 300):
        ui.append("uikit")
    unit["ui_frameworks"] = ui
    if "swiftui" in ui:
        unit["framework"], unit["framework_label"] = "swiftui", "SwiftUI app"
    is_app = meta.get("is_app") or meta.get("has_executable")
    if "Package.swift" in unit["manifests"] and not is_app and meta.get("has_library"):
        role = "library"
    elif plats == {"macos"} or ("macos" in plats and not (plats & {"ios", "tvos", "visionos", "watchos"})):
        role = "desktop" if is_app or not meta.get("has_library") else "library"
    elif plats & {"ios", "tvos", "visionos", "watchos"}:
        role = "mobile" if is_app or not meta.get("has_library") else "library"
    else:
        role = "desktop" if is_app else "unknown"
    unit["role"] = role
    info = {"entitlement_files": [], "sandbox": None, "network_client": None, "sparkle": False}
    for rel in unit["_files"]:
        if rel.endswith(".entitlements"):
            txt = util.read_text(os.path.join(root, rel), 50_000)
            info["entitlement_files"].append(rel)
            m = re.search(r"<key>com\.apple\.security\.app-sandbox</key>\s*<(true|false)\s*/>", txt)
            if m:
                info["sandbox"] = (m.group(1) == "true") if info["sandbox"] is None else (info["sandbox"] or m.group(1) == "true")
            m = re.search(r"<key>com\.apple\.security\.network\.client</key>\s*<(true|false)\s*/>", txt)
            if m:
                info["network_client"] = m.group(1) == "true"
            if info["sandbox"] and info["network_client"] is None:
                info["network_client"] = False
    info["sparkle"] = any(k.lower() == "sparkle" for k in deps) or bool(grep_src(r"SUFeedURL|SPUStandardUpdaterController", {".plist", ".swift"}, 200))
    info["cocoapods"] = "Podfile" in unit["manifests"]
    info["carthage"] = "Cartfile" in unit["manifests"]
    unit["apple"] = info
