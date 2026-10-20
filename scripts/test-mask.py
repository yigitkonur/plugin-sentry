#!/usr/bin/env python3
"""Regression checks for credential masking (engine/sentry_ctx/tokens.py), including credentials inside URLs, and that detection masks them
in the init-option snapshot it writes to .sentry-plugin/detect.json. Exit 1 on any failure. Run by scripts/check.sh."""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import tokens  # noqa: E402

fails = 0


def check(name, ok, detail=""):
    global fails
    fails += 0 if ok else 1
    print("%-5s %s %s" % ("ok" if ok else "FAIL", name, ("| " + str(detail)[:140]) if not ok else ""))


M = tokens.mask
check("user:password@host is masked", "hunter2" not in M("https://Tok3nAbC123:hunter2@proxy.example-co.net/x") and "proxy.example-co.net" in M("https://u:hunter2@proxy.example-co.net/x"))
check("a long single-token userinfo is masked", "ghp_abcdef123456" not in M("https://ghp_abcdef123456@github.com/o/r"))
check("a short userinfo (ssh://git@host) is left alone", M("ssh://git@github.com/o/r") == "ssh://git@github.com/o/r")
dsn = "https://0123456789abcdef0123456789abcdef@o1.ingest.de.sentry.io/42"
check("a Sentry DSN (public key) is not masked", M(dsn) == dsn, M(dsn))
check("a legacy DSN with a secret part is masked", "secretpart" not in M("https://0123456789abcdef0123456789abcdef:secretpart@o1.ingest.sentry.io/42"))
check("a Sentry user token is still masked", "a" * 64 not in M("sntryu_" + "a" * 64))
check("plain text is unchanged", M("Hello https://example.com/a?b=c and mail@host") == "Hello https://example.com/a?b=c and mail@host")

with tempfile.TemporaryDirectory() as tmp:
    for rel, text in {"package.json": '{"name":"web","private":true,"dependencies":{"@sentry/node":"11.8.0","hono":"^4"}}',
                      "package-lock.json": '{"lockfileVersion":3,"packages":{"node_modules/@sentry/node":{"version":"11.8.0"}}}',
                      "src/index.ts": 'import * as Sentry from "@sentry/node";\nSentry.init({ dsn: process.env.SENTRY_DSN, proxy: "https://Tok3nAbC123:hunter2@proxy.internal.example-co.net/x", tracesSampleRate: 0.1 });\n'}.items():
        os.makedirs(os.path.dirname(os.path.join(tmp, rel)) or tmp, exist_ok=True)
        open(os.path.join(tmp, rel), "w").write(text)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e.invalid", "commit", "-qm", "x"], cwd=tmp, check=True)
    out = subprocess.run([os.path.join(ROOT, "bin", "sentry-ctx"), "--json", "--path", tmp, "detect"], capture_output=True, text=True).stdout
    check("detect output carries no URL credential from Sentry.init options", out and "hunter2" not in out and "Tok3nAbC123" not in out, out[:100])
    check("detect still sees the init (the case is not vacuous)", '"status": "present"' in out or '"status":"present"' in out)

print("\n%s" % ("MASK TESTS PASSED" if not fails else "%d MASK TEST(S) FAILED" % fails))
sys.exit(1 if fails else 0)
