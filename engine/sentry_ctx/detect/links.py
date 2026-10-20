"""Cross-unit facts for repos that hold more than one deployable unit: which unit calls which, DSNs shared between units and the
`environment` names in use. Static and heuristic: every edge is a candidate that the links auditor confirms by reading the cited lines.

Safety: only files inside the repo root are read (symlinks that leave it are skipped), URL credentials never reach the output (only the
host is kept), a DSN key is reduced to an 8-character hash, and a malformed config file is skipped, never fatal."""
from __future__ import annotations

import bisect
import fnmatch
import hashlib
import json
import os
import re

MAX_FILES_PER_UNIT = 6000      # shallowest files first; a bigger unit is reported as truncated, not scanned forever
MAX_BYTES_PER_UNIT = 40_000_000
READ_LIMIT = 200_000
MAX_URLS_PER_FILE = 400
TEXT_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".astro", ".vue", ".svelte", ".json", ".jsonc", ".toml", ".yaml", ".yml",
            ".swift", ".kt", ".java", ".py", ".go", ".rb", ".php", ".dart", ".cs", ".plist", ".xcconfig", ".properties", ".env"}
SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "Cargo.lock", "composer.lock", "Gemfile.lock", "poetry.lock", "bun.lock", "go.sum"}
SKIP_HOST_SUFFIX = ("sentry.io", "github.com", "githubusercontent.com", "npmjs.org", "w3.org", "schema.org", "cloudflare.com", "expo.dev", "apple.com",
                    "googleapis.com", "gstatic.com", "example.com", "example.org", "localhost", "opentelemetry.io", "mozilla.org")
# optional `user:password@` is matched so it is never mistaken for the host and never recorded
URL_RX = re.compile(r"https?://(?:[^/@\s\"'`<>]*@)?([A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9])(?::\d{2,5})?")
DSN_RX = re.compile(r"https?://([0-9A-Fa-f]{32})@([A-Za-z0-9.-]+)/(\d+)")
ENV_LITERAL_RX = re.compile(r"""\benvironment\s*[:=]\s*["']([A-Za-z0-9_-]+)["']|["']environment["']\s*:\s*["']([A-Za-z0-9_-]+)["']""")
ENV_VAR_RX = re.compile(r"""\bSENTRY_ENVIRONMENT\s*[:=]\s*["']?([A-Za-z0-9_-]+)["']?""")
CORS_RX = re.compile(r"(?i)\borigin\b|access-control|\bcors\b|allowedorigins|trustedorigins|allowed_hosts")
ENV_LINE_RX = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*[\"']?(https?://[^\s\"']+)")
RPC_LIST_RX = re.compile(r"rpcTracePropagationBindings\s*:\s*\[([^\]]*)\]")


def _read(root, rel, limit=READ_LIMIT):
    """File text, or "" when the file is a symlink that leaves the repo, unreadable, or not text. A leading BOM is dropped."""
    full = os.path.join(root, rel)
    try:
        real, rroot = os.path.realpath(full), os.path.realpath(root)
        if real != rroot and not real.startswith(rroot + os.sep):
            return ""
        with open(real, "rb") as f:
            data = f.read(limit)
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace").lstrip("\ufeff")


class _Lines:
    """Line numbers by position in O(log n), so a minified single-line file with thousands of URLs stays linear."""

    def __init__(self, text):
        self.text = text
        self.starts = [0] + [m.end() for m in re.finditer("\n", text)]

    def no(self, pos):
        return bisect.bisect_right(self.starts, pos)

    def line(self, n):
        a = self.starts[n - 1]
        b = self.starts[n] if n < len(self.starts) else len(self.text)
        return self.text[a:b]


def _strip_jsonc(text):
    """Remove // and /* */ comments, then trailing commas, both outside strings."""
    def walk(src, drop_comments):
        out, i, n, in_str = [], 0, len(src), False
        while i < n:
            c = src[i]
            if in_str:
                out.append(c)
                if c == "\\" and i + 1 < n:
                    out.append(src[i + 1])
                    i += 1
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
                out.append(c)
            elif drop_comments and c == "/" and src[i + 1:i + 2] == "/":
                while i < n and src[i] != "\n":
                    i += 1
                continue
            elif drop_comments and c == "/" and src[i + 1:i + 2] == "*":
                j = src.find("*/", i + 2)
                i = n if j < 0 else j + 1
            elif not drop_comments and c == ",":
                j = i + 1
                while j < n and src[j] in " \t\r\n":
                    j += 1
                if j < n and src[j] in "}]":
                    pass  # trailing comma
                else:
                    out.append(c)
            else:
                out.append(c)
            i += 1
        return "".join(out)
    return walk(walk(text, True), False)


def _load_wrangler(root, rel):
    """(raw text, config dict). A file that is not valid JSON, or not an object, gives an empty dict."""
    raw = _read(root, rel, 100_000)
    try:
        cfg = json.loads(_strip_jsonc(raw))
    except ValueError:
        cfg = {}
    return raw, cfg if isinstance(cfg, dict) else {}


def _env_blocks(cfg):
    env = cfg.get("env")
    return [v for v in (env.values() if isinstance(env, dict) else []) if isinstance(v, dict)]


def _line_of(text, needle, start=0):
    i = text.find(needle, max(0, start))
    return text.count("\n", 0, i) + 1 if i >= 0 else 1


def _host_of(pattern):
    p = re.sub(r"^https?://", "", str(pattern).strip())
    return p.split("/")[0].lower()


def _routes_of(block):
    out = []
    r = block.get("routes")
    if isinstance(r, list):
        out += r
    if block.get("route"):
        out.append(block["route"])
    return out


def _server_hosts(root, files):
    """Hostnames this unit answers on (wrangler routes of every environment, the Astro `site`) and its Worker names."""
    hosts, names = [], []
    for rel in files:
        base = os.path.basename(rel)
        if base in ("wrangler.jsonc", "wrangler.json"):
            raw, cfg = _load_wrangler(root, rel)
            at = max(raw.find('"routes"'), raw.find('"route"'), 0)
            for block in [cfg] + _env_blocks(cfg):
                for r in _routes_of(block):
                    pat = r.get("pattern") if isinstance(r, dict) else r
                    if isinstance(pat, str) and pat:
                        hosts.append({"host": _host_of(pat), "evidence": "%s:%d" % (rel, _line_of(raw, pat.split("/")[0], at))})
            if isinstance(cfg.get("name"), str):
                names.append(cfg["name"])
        elif base == "wrangler.toml":
            raw = _read(root, rel, 100_000)
            for m in re.finditer(r"""(?m)^\s*(?:pattern|route)\s*=\s*["']([^"']+)["']""", raw):
                hosts.append({"host": _host_of(m.group(1)), "evidence": "%s:%d" % (rel, raw.count("\n", 0, m.start()) + 1)})
            m = re.search(r"""(?m)^\s*name\s*=\s*["']([^"']+)["']""", raw)
            if m:
                names.append(m.group(1))
        elif re.match(r"astro\.config\.(mjs|js|ts|mts|cjs)$", base):
            raw = _read(root, rel, 100_000)
            m = re.search(r"""\bsite\s*:\s*["'](https?://[^"']+)["']""", raw)
            if m:
                hosts.append({"host": _host_of(m.group(1)), "evidence": "%s:%d" % (rel, raw.count("\n", 0, m.start()) + 1)})
    return hosts, names


def _toml_field(block, key):
    m = re.search(r"""(?m)(?:^|[{,])\s*%s\s*=\s*["']([^"']+)["']""" % key, block)
    return m.group(1) if m else None


def _service_bindings(root, files):
    """Service bindings this unit declares in wrangler config: [{binding, service, entrypoint, evidence}]."""
    out = []
    for rel in files:
        base = os.path.basename(rel)
        if base in ("wrangler.jsonc", "wrangler.json"):
            raw, cfg = _load_wrangler(root, rel)
            for b in [cfg] + _env_blocks(cfg):
                svcs = b.get("services")
                for sv in svcs if isinstance(svcs, list) else []:
                    if isinstance(sv, dict) and isinstance(sv.get("service"), str):
                        out.append({"binding": sv.get("binding") if isinstance(sv.get("binding"), str) else None, "service": sv["service"],
                                    "entrypoint": sv.get("entrypoint") if isinstance(sv.get("entrypoint"), str) else None,
                                    "evidence": "%s:%d" % (rel, _line_of(raw, '"%s"' % sv["service"]))})
        elif base == "wrangler.toml":
            raw = _read(root, rel, 100_000)
            for m in re.finditer(r"(?ms)^\[\[(?:env\.[\w-]+\.)?services\]\][^\n]*\n(.*?)(?=^\[|\Z)", raw):  # [[services]] tables
                blk = m.group(1)
                svc = _toml_field(blk, "service")
                if svc:
                    out.append({"binding": _toml_field(blk, "binding"), "service": svc, "entrypoint": _toml_field(blk, "entrypoint"),
                                "evidence": "%s:%d" % (rel, raw.count("\n", 0, m.start()) + 1)})
            for m in re.finditer(r"(?ms)^\s*services\s*=\s*\[(.*?)\]\s*$", raw):  # inline array of tables
                for item in re.finditer(r"\{([^}]*)\}", m.group(1)):
                    svc = _toml_field("{" + item.group(1), "service")
                    if svc:
                        out.append({"binding": _toml_field("{" + item.group(1), "binding"), "service": svc, "entrypoint": _toml_field("{" + item.group(1), "entrypoint"),
                                    "evidence": "%s:%d" % (rel, raw.count("\n", 0, m.start()) + 1)})
    return out


def _rpc_listed(texts):
    """Binding names a unit lists in rpcTracePropagationBindings, with file:line."""
    out = []
    for rel, t in texts.items():
        for m in RPC_LIST_RX.finditer(t):
            names = re.findall(r"""["']([^"']+)["']""", m.group(1))
            out.append({"bindings": names, "evidence": "%s:%d" % (rel, t.count("\n", 0, m.start()) + 1)})
    return out


def _matches(host, pattern):
    return fnmatch.fnmatch(host.lower(), pattern.lower())


def _scan_unit(root, files):
    origins, dsns, envs, cors = {}, {}, [], {}
    texts, total, truncated = {}, 0, False
    for rel in sorted(files, key=lambda r: (r.count("/"), r)):
        base = os.path.basename(rel)
        if base in SKIP_NAMES or rel.endswith((".min.js", ".map", ".lock")):
            continue
        if not (os.path.splitext(rel)[1] in TEXT_EXT or base.startswith(".env")):
            continue
        if len(texts) >= MAX_FILES_PER_UNIT or total >= MAX_BYTES_PER_UNIT:
            truncated = True
            break
        t = _read(root, rel)
        if t:
            texts[rel] = t
            total += len(t)
    for rel, t in texts.items():
        lines = _Lines(t)
        cut = len(t) >= READ_LIMIT - 4  # the read stopped mid-file: a URL touching the end may be cut
        if os.path.basename(rel).startswith(".env"):
            for ln in range(1, len(lines.starts) + 1):
                m = ENV_LINE_RX.match(lines.line(ln))
                if m and not DSN_RX.search(m.group(2)):
                    h = URL_RX.match(m.group(2))
                    if h:
                        origins.setdefault(h.group(1).lower(), []).append({"file": rel, "line": ln, "key": m.group(1)})
        seen = 0
        for m in URL_RX.finditer(t):
            seen += 1
            if seen > MAX_URLS_PER_FILE or (cut and m.end() >= len(t)):
                break
            host = m.group(1).lower()
            if any(host == s or host.endswith("." + s) for s in SKIP_HOST_SUFFIX) or DSN_RX.match(t, m.start()):
                continue
            ln = lines.no(m.start())
            if CORS_RX.search(lines.line(ln)):  # an allow-list of origins, not a call
                cors.setdefault(host, []).append("%s:%d" % (rel, ln))
                continue
            ent = origins.setdefault(host, [])
            if not any(e["file"] == rel and e["line"] == ln for e in ent):
                ent.append({"file": rel, "line": ln, "key": None})
        for m in DSN_RX.finditer(t):
            key = hashlib.sha1(m.group(1).lower().encode()).hexdigest()[:8]
            dsns.setdefault((key, m.group(2).lower(), m.group(3)), []).append("%s:%d" % (rel, lines.no(m.start())))
        for m in ENV_LITERAL_RX.finditer(t):
            envs.append({"value": m.group(1) or m.group(2), "evidence": "%s:%d" % (rel, lines.no(m.start()))})
        for m in ENV_VAR_RX.finditer(t):
            envs.append({"value": m.group(1), "evidence": "%s:%d" % (rel, lines.no(m.start()))})

    usage_cache = {}

    def usages(key):
        if key not in usage_cache:
            out = []
            for rel, t in texts.items():
                if os.path.basename(rel).startswith(".env"):
                    continue
                for ln, line in enumerate(t.splitlines(), 1):
                    if key in line:
                        out.append("%s:%d" % (rel, ln))
                        if len(out) >= 3:
                            break
                if len(out) >= 3:
                    break
            usage_cache[key] = out
        return usage_cache[key]

    return origins, dsns, envs, cors, usages, texts, truncated


def analyze(root, units):
    """None for repos with fewer than two deployable (non-library) units."""
    deployable = [u for u in units if u.get("role") != "library"]
    if len(deployable) < 2:
        return None
    per = {}
    for u in deployable:
        files = list(u.get("_files", []))
        hosts, names = _server_hosts(root, files)
        origins, dsns, envs, cors, usages, texts, truncated = _scan_unit(root, files)
        per[u["id"]] = {"unit": u, "hosts": hosts, "names": names, "origins": origins, "dsns": dsns, "envs": envs, "cors": cors, "usages": usages,
                        "truncated": truncated, "bindings": _service_bindings(root, files), "rpc_listed": _rpc_listed(texts)}
    edges, unmatched = [], {}
    for a_id, a in per.items():
        for host, occ in sorted(a["origins"].items()):
            matched = False
            for b_id, b in per.items():
                if b_id == a_id:
                    continue
                hit, how = next((h for h in b["hosts"] if _matches(host, h["host"])), None), "route"
                if not hit and host.endswith(".workers.dev"):  # the account part of a workers.dev host is not in the repo: name match only
                    hit, how = next(({"host": host, "evidence": "wrangler name"} for n in b["names"] if host.startswith(n.lower() + ".")), None), "worker-name-only"
                if not hit:
                    continue
                matched = True
                ev, via = [], []
                for o in occ[:4]:
                    ev.append("%s:%d" % (o["file"], o["line"]))
                    if o["key"]:
                        via.append(o["key"])
                        ev.extend(a["usages"](o["key"]))
                edges.append({
                    "kind": "http", "from": a_id, "to": b_id, "host": host, "match": how, "from_role": a["unit"].get("role"), "to_role": b["unit"].get("role"),
                    "via_env": sorted(set(via)), "evidence": {"from": sorted(set(ev))[:8], "to": [hit["evidence"]]},
                })
            if not matched and not any(_matches(host, h["host"]) for h in a["hosts"]):
                unmatched.setdefault(a_id, []).append(host)
    for a_id, a in per.items():
        for sv in a["bindings"]:
            for b_id, b in per.items():
                if b_id != a_id and sv["service"] in b["names"]:
                    listed = [x for x in a["rpc_listed"] if sv["binding"] in x["bindings"]]
                    edges.append({"kind": "service-binding", "from": a_id, "to": b_id, "binding": sv["binding"], "entrypoint": sv["entrypoint"],
                                  "from_role": a["unit"].get("role"), "to_role": b["unit"].get("role"),
                                  "rpc_binding_listed": bool(listed),
                                  "evidence": {"from": [sv["evidence"]] + [x["evidence"] for x in listed][:2], "to": []}})
    shared = {}
    for uid, p in per.items():
        for k, locs in p["dsns"].items():
            shared.setdefault(k, {})[uid] = locs[:2]
    shared_dsns = [{"project": k[2], "ingest_host": k[1], "key_sha1_8": k[0], "units": sorted(v), "evidence": [e for uid in sorted(v) for e in v[uid]]}
                   for k, v in sorted(shared.items()) if len(v) > 1]
    env_names = {}
    for uid, p in per.items():
        for e in p["envs"]:
            env_names.setdefault(e["value"], []).append({"unit": uid, "evidence": e["evidence"]})
    return {
        "note": "static candidates; the links auditor confirms each edge by reading the cited lines",
        "hosts": {uid: p["hosts"] for uid, p in per.items() if p["hosts"]},
        "edges": edges,
        **({"truncated_units": sorted(uid for uid, p in per.items() if p["truncated"])} if any(p["truncated"] for p in per.values()) else {}),
        "cors_allowed_origins": {uid: [{"host": h, "evidence": e[:2]} for h, e in sorted(p["cors"].items())] for uid, p in per.items() if p["cors"]},
        "unmatched_origins": {uid: sorted(set(h))[:8] for uid, h in unmatched.items()},
        "shared_dsns": shared_dsns,
        "environment_names": {k: sorted(v, key=lambda x: (x["unit"], x["evidence"])) for k, v in sorted(env_names.items())},
    }
