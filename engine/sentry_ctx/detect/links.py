"""Cross-unit facts for repos that hold more than one deployable unit: which unit calls which, DSNs shared between units and the
`environment` names in use. Static and heuristic: every edge is a candidate that the links auditor confirms by reading the cited lines."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re

from .. import util

TEXT_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".astro", ".vue", ".svelte", ".json", ".jsonc", ".toml", ".yaml", ".yml",
            ".swift", ".kt", ".java", ".py", ".go", ".rb", ".php", ".dart", ".cs", ".plist", ".xcconfig", ".properties", ".env"}
SKIP_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "Cargo.lock", "composer.lock", "Gemfile.lock", "poetry.lock", "bun.lock", "go.sum"}
SKIP_HOST_SUFFIX = ("sentry.io", "github.com", "githubusercontent.com", "npmjs.org", "w3.org", "schema.org", "cloudflare.com", "expo.dev", "apple.com",
                    "googleapis.com", "gstatic.com", "example.com", "example.org", "localhost", "opentelemetry.io", "mozilla.org")
URL_RX = re.compile(r"https?://([A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9])(?::\d{2,5})?")
DSN_RX = re.compile(r"https?://([0-9a-f]{32})@([A-Za-z0-9.-]+)/(\d+)")
ENV_LITERAL_RX = re.compile(r"""\benvironment\s*[:=]\s*["']([A-Za-z0-9_-]+)["']|["']environment["']\s*:\s*["']([A-Za-z0-9_-]+)["']""")
ENV_VAR_RX = re.compile(r"""\bSENTRY_ENVIRONMENT\s*[:=]\s*["']?([A-Za-z0-9_-]+)["']?""")
PUBLIC_PREFIX = ("PUBLIC_", "VITE_", "NEXT_PUBLIC_", "NUXT_PUBLIC_", "EXPO_PUBLIC_", "REACT_APP_")
CORS_RX = re.compile(r"(?i)\borigin\b|access-control|\bcors\b|allowedorigins|trustedorigins|allowed_hosts")
ENV_LINE_RX = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*[\"']?(https?://[^\s\"']+)")


def _strip_jsonc(text):
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif c == "/" and text[i + 1:i + 2] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 1
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _line_of(text, needle, start=0):
    i = text.find(needle, start)
    return text.count("\n", 0, i) + 1 if i >= 0 else 1


def _host_of(pattern):
    p = re.sub(r"^https?://", "", str(pattern).strip())
    return p.split("/")[0].lower()


def _server_hosts(root, files):
    """Hostnames this unit answers on (wrangler routes, the Astro `site`) and its Worker names."""
    hosts, names = [], []
    for rel in files:
        base = os.path.basename(rel)
        full = os.path.join(root, rel)
        if base in ("wrangler.jsonc", "wrangler.json"):
            raw = util.read_text(full, 100_000)
            try:
                cfg = json.loads(_strip_jsonc(raw))
            except ValueError:
                cfg = {}
            routes = list(cfg.get("routes") or [])
            if cfg.get("route"):
                routes.append(cfg["route"])
            for r in routes:
                pat = r.get("pattern") if isinstance(r, dict) else r
                if pat:
                    h = _host_of(pat)
                    hosts.append({"host": h, "evidence": "%s:%d" % (rel, _line_of(raw, str(pat).split("/")[0]))})
            if cfg.get("name"):
                names.append(cfg["name"])
        elif base == "wrangler.toml":
            raw = util.read_text(full, 100_000)
            for m in re.finditer(r"""(?m)^\s*(?:pattern|route)\s*=\s*["']([^"']+)["']""", raw):
                hosts.append({"host": _host_of(m.group(1)), "evidence": "%s:%d" % (rel, raw.count("\n", 0, m.start()) + 1)})
            m = re.search(r"""(?m)^\s*name\s*=\s*["']([^"']+)["']""", raw)
            if m:
                names.append(m.group(1))
        elif re.match(r"astro\.config\.(mjs|js|ts|mts|cjs)$", base):
            raw = util.read_text(full, 100_000)
            m = re.search(r"""\bsite\s*:\s*["'](https?://[^"']+)["']""", raw)
            if m:
                hosts.append({"host": _host_of(m.group(1)), "evidence": "%s:%d" % (rel, raw.count("\n", 0, m.start()) + 1)})
    return hosts, names


def _matches(host, pattern):
    return fnmatch.fnmatch(host.lower(), pattern.lower())


def _scan_unit(root, unit, files):
    origins, dsns, envs, cors = {}, {}, [], {}
    usage_cache = {}
    texts = {}
    for rel in files:
        base = os.path.basename(rel)
        if base in SKIP_NAMES or rel.endswith((".min.js", ".map", ".lock")):
            continue
        ext = os.path.splitext(rel)[1]
        if not (ext in TEXT_EXT or base.startswith(".env")):
            continue
        t = util.read_text(os.path.join(root, rel), 200_000)
        if t:
            texts[rel] = t
    for rel, t in texts.items():
        base = os.path.basename(rel)
        is_env = base.startswith(".env")
        if is_env:
            for ln, line in enumerate(t.splitlines(), 1):
                m = ENV_LINE_RX.match(line)
                if m:
                    h = URL_RX.match(m.group(2))
                    if h and not DSN_RX.search(line):
                        origins.setdefault(h.group(1).lower(), []).append({"file": rel, "line": ln, "key": m.group(1)})
        for m in URL_RX.finditer(t):
            if is_env and DSN_RX.search(t[max(0, m.start() - 40):m.end() + 80]):
                continue
            host = m.group(1).lower()
            ln = t.count("\n", 0, m.start()) + 1
            if t[m.end():m.end() + 1] == "@" or any(host == s or host.endswith("." + s) for s in SKIP_HOST_SUFFIX):
                continue
            line_text = t.splitlines()[ln - 1] if ln - 1 < len(t.splitlines()) else ""
            if CORS_RX.search(line_text):  # an allow-list of origins, not a call
                cors.setdefault(host, []).append("%s:%d" % (rel, ln))
                continue
            ent = origins.setdefault(host, [])
            if not any(e["file"] == rel and e["line"] == ln for e in ent):
                ent.append({"file": rel, "line": ln, "key": None})
        for m in DSN_RX.finditer(t):
            key = hashlib.sha1(m.group(1).encode()).hexdigest()[:8]
            d = dsns.setdefault((key, m.group(2), m.group(3)), [])
            d.append("%s:%d" % (rel, t.count("\n", 0, m.start()) + 1))
        for m in ENV_LITERAL_RX.finditer(t):
            envs.append({"value": m.group(1) or m.group(2), "evidence": "%s:%d" % (rel, t.count("\n", 0, m.start()) + 1)})
        for m in ENV_VAR_RX.finditer(t):
            envs.append({"value": m.group(1), "evidence": "%s:%d" % (rel, t.count("\n", 0, m.start()) + 1)})

    def usages(key):
        if key in usage_cache:
            return usage_cache[key]
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
        return out

    return origins, dsns, envs, cors, usages


def analyze(root, units):
    """None for repos with fewer than two deployable (non-library) units."""
    deployable = [u for u in units if u.get("role") != "library"]
    if len(deployable) < 2:
        return None
    per = {}
    for u in deployable:
        files = list(u.get("_files", []))
        hosts, names = _server_hosts(root, files)
        origins, dsns, envs, cors, usages = _scan_unit(root, u, files)
        per[u["id"]] = {"unit": u, "hosts": hosts, "names": names, "origins": origins, "dsns": dsns, "envs": envs, "cors": cors, "usages": usages}
    edges, unmatched = [], {}
    for a_id, a in per.items():
        for host, occ in sorted(a["origins"].items()):
            matched = False
            for b_id, b in per.items():
                if b_id == a_id:
                    continue
                hit = next((h for h in b["hosts"] if _matches(host, h["host"])), None)
                if not hit and host.endswith(".workers.dev"):
                    hit = next(({"host": host, "evidence": "wrangler name"} for n in b["names"] if host.startswith(n.lower() + ".")), None)
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
                    "from": a_id, "to": b_id, "host": host, "from_role": a["unit"].get("role"), "to_role": b["unit"].get("role"),
                    "via_env": sorted(set(via)), "evidence": {"from": sorted(set(ev))[:8], "to": [hit["evidence"]]},
                })
            if not matched and not any(_matches(host, h["host"]) for h in a["hosts"]):
                unmatched.setdefault(a_id, []).append(host)
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
        "cors_allowed_origins": {uid: [{"host": h, "evidence": e[:2]} for h, e in sorted(p["cors"].items())] for uid, p in per.items() if p["cors"]},
        "unmatched_origins": {uid: sorted(set(h))[:8] for uid, h in unmatched.items()},
        "shared_dsns": shared_dsns,
        "environment_names": {k: sorted(v, key=lambda x: (x["unit"], x["evidence"])) for k, v in sorted(env_names.items())},
    }
