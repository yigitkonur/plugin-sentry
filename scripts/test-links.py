#!/usr/bin/env python3
"""Regression checks for the cross-unit scan (engine/sentry_ctx/detect/links.py): it must never read outside the repo, never record URL
credentials or a DSN key, never crash on a malformed config, understand the wrangler forms real repos use, and stay fast on a minified file.
Each case builds a tiny two-unit repo in a temp directory. Exit 1 on any failure. Run by scripts/check.sh."""
import json
import os
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx.detect import core  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    fails += 0 if ok else 1
    print("%-5s %s %s" % ("ok" if ok else "FAIL", name, ("| " + str(detail)[:120]) if (detail and not ok) or detail == "show" else ""))


def repo(tmp, files):
    for rel, content in files.items():
        p = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(content if isinstance(content, bytes) else content.encode())
    base = {"apps/web/package.json": '{"name":"web","private":true,"dependencies":{"astro":"^7"}}',
            "services/api/package.json": '{"name":"api","private":true,"dependencies":{"hono":"^4"}}'}
    for rel, content in base.items():
        p = os.path.join(tmp, rel)
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").write(content)


def links(tmp):
    d = core.detect(tmp)
    return d.get("links") or {}


def edges_of(l, kind=None):
    return [e for e in l.get("edges", []) if kind is None or e["kind"] == kind]


API_ROUTE = '{"name":"edge-api","routes":[{"pattern":"api.example-co.com/*"}]}'

with tempfile.TemporaryDirectory() as tmp:
    # 1. malformed wrangler files never crash detection
    for i, cfg in enumerate(['{"name":"api","routes":5}', "[]", '{"env":5}', '{"services":5}', '{"name":5}', "not json at all"]):
        t = os.path.join(tmp, "bad%d" % i)
        repo(t, {"services/api/wrangler.jsonc": cfg, "apps/web/a.ts": 'fetch("https://x.workers.dev/y")\n'})
        try:
            links(t)
            check("malformed wrangler config does not crash: %s" % cfg[:24], True)
        except Exception as e:
            check("malformed wrangler config does not crash: %s" % cfg[:24], False, repr(e))

    # 2. a symlink that leaves the repo is not followed (no git: the walk keeps symlinks)
    t = os.path.join(tmp, "symlink")
    outside = os.path.join(tmp, "outside.env")
    open(outside, "w").write("PUBLIC_X=https://secret-outside-host.example-co.internal/v1\n")
    repo(t, {"services/api/wrangler.jsonc": API_ROUTE})
    os.symlink(outside, os.path.join(t, "apps/web/.env"))
    blob = json.dumps(links(t))
    check("a symlink leaving the repo is not read", "secret-outside-host" not in blob, blob)

    # 3. credentials in URLs and DSN keys never reach the output
    t = os.path.join(tmp, "creds")
    repo(t, {"services/api/wrangler.jsonc": API_ROUTE,
             "apps/web/a.ts": 'export const p = "https://Tok3nAbC123:hunter2@proxy.internal.example-co.net/x";\nfetch("https://api.example-co.com/o");\n',
             "apps/web/.env": "SOURCE_URL=https://ghtoken123@gitlab.example-co.net/x/y\nSENTRY_DSN=https://ABCDEF0123456789ABCDEF0123456789@o9.ingest.sentry.io/77\n"})
    blob = json.dumps(links(t)).lower()
    check("URL credentials are not recorded", "tok3nabc123" not in blob and "hunter2" not in blob and "ghtoken123" not in blob, blob)
    check("a DSN key is not recorded (upper or lower case)", "abcdef0123456789abcdef0123456789" not in blob, blob)
    check("the host after the credentials is still found", "proxy.internal.example-co.net" in blob)

    # 4. wrangler forms: env-level routes (JSON), BOM, toml with a comment after [[services]], inline services, entrypoint
    t = os.path.join(tmp, "forms")
    repo(t, {"services/api/wrangler.jsonc": b"\xef\xbb\xbf" + b'{"name":"edge-api","routes":[],"env":{"staging":{"routes":[{"pattern":"staging.example-co.com/*"}]}}}',
             "apps/web/a.ts": 'fetch("https://staging.example-co.com/o")\n'})
    check("a BOM does not disable the file, and an env-level route is a host", any(e["host"] == "staging.example-co.com" for e in edges_of(links(t), "http")), links(t))
    t = os.path.join(tmp, "toml")
    repo(t, {"services/api/wrangler.toml": 'name = "edge-api"\n',
             "apps/web/wrangler.toml": 'name = "web"\n[[services]] # the api\nbinding = "API"\nservice = "edge-api"\nentrypoint = "OrdersRpc"\n[[env.staging.services]]\nbinding = "B2"\nservice = "edge-api"\n'})
    sb = edges_of(links(t), "service-binding")
    check("toml [[services]] with a trailing comment, entrypoint kept, env table found", sorted(e["binding"] for e in sb) == ["API", "B2"] and {e["entrypoint"] for e in sb} == {"OrdersRpc", None}, sb)
    t = os.path.join(tmp, "toml-inline")
    repo(t, {"services/api/wrangler.toml": 'name = "edge-api"\n',
             "apps/web/wrangler.toml": 'name = "web"\nservices = [ { binding = "API", service = "edge-api", entrypoint = "R" } ]\n'})
    sb = edges_of(links(t), "service-binding")
    check("toml inline services array", [(e["binding"], e["entrypoint"]) for e in sb] == [("API", "R")], sb)

    # 5. an RPC binding listed in the caller's options is reported as listed; an unlisted one is not
    t = os.path.join(tmp, "rpc")
    repo(t, {"services/api/wrangler.jsonc": '{"name":"edge-api"}',
             "apps/web/wrangler.jsonc": '{"name":"web","services":[{"binding":"API","service":"edge-api"},{"binding":"OTHER","service":"edge-api"}]}',
             "apps/web/sentry.server.config.ts": 'export const o = () => ({ rpcTracePropagationBindings: ["API"] });\n'})
    flags = {e["binding"]: e["rpc_binding_listed"] for e in edges_of(links(t), "service-binding")}
    check("rpc_binding_listed true for the listed binding only", flags == {"API": True, "OTHER": False}, flags)

    # 6. wildcard routes match subdomains but not the apex or a look-alike
    t = os.path.join(tmp, "wild")
    repo(t, {"services/api/wrangler.jsonc": '{"name":"edge-api","routes":[{"pattern":"*.example-co.com/*"}]}',
             "apps/web/a.ts": 'fetch("https://a.example-co.com/x"); fetch("https://example-co.com/x"); fetch("https://a.example-co.com.evil.net/x");\n'})
    hosts = sorted(e["host"] for e in edges_of(links(t), "http"))
    check("wildcard route: subdomain yes, apex and look-alike no", hosts == ["a.example-co.com"], hosts)

    # 7. a single-line minified file with thousands of URLs stays fast (the scan alone, not all of detect)
    from sentry_ctx.detect import links as links_mod  # noqa: E402
    t = os.path.join(tmp, "perf")
    os.makedirs(os.path.join(t, "public"))
    open(os.path.join(t, "public", "bundle.js"), "w").write("".join('f("https://h%d.example-co.net/p");' % i for i in range(4500)))
    t0 = time.time()
    links_mod._scan_unit(t, ["public/bundle.js"])
    dt = time.time() - t0
    check("4,500 URLs on one line scan in under 3 s (was 33 s; about 0.01 s now)", dt < 3, "%.2fs" % dt)

    # 8. the evidence line of a route is the route, not an earlier mention of the host
    t = os.path.join(tmp, "evidence")
    repo(t, {"services/api/wrangler.jsonc": '{\n  "name": "edge-api",\n  "vars": { "HOME": "https://api.example-co.com" },\n  "routes": [{ "pattern": "api.example-co.com/*" }]\n}',
             "apps/web/a.ts": 'fetch("https://api.example-co.com/o")\n'})
    ev = [x for e in edges_of(links(t), "http") for x in e["evidence"]["to"]]
    check("route evidence points at the routes line (4), not the vars line (3)", ev == ["services/api/wrangler.jsonc:4"], ev)

print("\n%s" % ("LINKS TESTS PASSED" if not fails else "%d LINKS TEST(S) FAILED" % fails))
sys.exit(1 if fails else 0)
