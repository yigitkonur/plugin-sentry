#!/usr/bin/env python3
"""Every URL in the plugin's own content must resolve to a real page.
docs.sentry.io answers HTTP 200 with a 'Page Not Found' title for missing pages, so Sentry hosts are checked by content.
Usage: check-links.py [--offline]   (offline only lists the URLs)"""
import os
import re
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import docs, util  # noqa: E402

SCAN = ["references/forge", "agents", "skills", "data", "README.md", "AGENTS.md", "evals/hooks"]
URL = re.compile(r"https://[A-Za-z0-9][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)+(?:[/?#][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*)?")
SKIP_HOSTS = {"example.com", "o123456.ingest.us.sentry.io", "0123456789abcdef0123456789abcdef"}
IGNORE_SUBSTR = ("<", "{", "$", "YOUR", "ingest.", "example.", "/org/", "sentry.io/organizations/", "sentry.io/settings/", "sentry.io/get-cli", "cli.sentry.dev/install")


def urls():
    found = {}
    for entry in SCAN:
        p = os.path.join(ROOT, entry)
        files = []
        if os.path.isfile(p):
            files = [p]
        elif os.path.isdir(p):
            for dp, _, fn in os.walk(p):
                files += [os.path.join(dp, f) for f in fn if f.endswith((".md", ".tsv", ".json", ".txt"))]
        for f in files:
            try:
                text = open(f, encoding="utf-8").read()
            except OSError:
                continue
            for m in URL.finditer(text):
                u = m.group(0).rstrip(".,;:)\"'`>")
                if any(s in u for s in IGNORE_SUBSTR):
                    continue
                found.setdefault(u.split("#")[0], os.path.relpath(f, ROOT))
    return found


def check(u):
    host = re.match(r"https://([^/]+)", u).group(1)
    if host in docs.HOSTS and host not in ("github.com", "raw.githubusercontent.com"):
        try:
            docs.fetch(u)
            return None
        except util.EngineError as e:
            return str(e)
    req = urllib.request.Request(u, headers={"User-Agent": docs.UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return None if r.status < 400 else "HTTP %d" % r.status
    except urllib.error.HTTPError as e:
        return "HTTP %d" % e.code if e.code not in (401, 403, 429) else None
    except Exception as e:  # network trouble is reported, not hidden
        return "unreachable: %s" % e


def main():
    found = urls()
    print("%d distinct URLs" % len(found))
    if "--offline" in sys.argv:
        for u, f in sorted(found.items()):
            print(u, "<-", f)
        return 0
    bad = 0
    for u, f in sorted(found.items()):
        err = check(u)
        if err:
            bad += 1
            print("DEAD  %s  (%s)  <- %s" % (u, err, f))
    print("dead: %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
