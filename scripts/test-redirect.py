#!/usr/bin/env python3
"""Regression checks for the docs fetcher's redirect handler (engine/sentry_ctx/docs.py): a redirect is followed only to https on a listed
docs host with no userinfo and no port. Exit 1 on any failure. Run by scripts/check.sh."""
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import docs  # noqa: E402

fails = 0
handler = docs._Redirect()
req = urllib.request.Request("https://docs.sentry.io/a.md")
for url, want in (("https://developers.cloudflare.com/x/index.md", True), ("https://DEVELOPERS.cloudflare.com/x", True), ("https://docs.sentry.io/y.md", True),
                  ("http://developers.cloudflare.com/x", False), ("https://developers.cloudflare.com@evil.example/x", False),
                  ("https://developers.cloudflare.com:8443/x", False), ("https://evil.example/x", False), ("file:///etc/passwd", False)):
    try:
        got = handler.redirect_request(req, None, 308, "x", {}, url) is not None
    except urllib.error.HTTPError:
        got = False
    fails += 0 if got == want else 1
    print("%-5s redirect to %-52s %s" % ("ok" if got == want else "FAIL", url, "followed" if got else "refused"))
print("\n%s" % ("REDIRECT TESTS PASSED" if not fails else "%d REDIRECT TEST(S) FAILED" % fails))
sys.exit(1 if fails else 0)
