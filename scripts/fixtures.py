#!/usr/bin/env python3
"""Fixture tooling: materialize evals/fixtures/<name> into git repos (placeholders -> fake tokens), record or
check expected detect output.

  fixtures.py materialize OUTDIR [name ...]   copy + git init + commit
  fixtures.py record [name ...]               write evals/expected/<name>.detect.json from the current engine
  fixtures.py check  [name ...]               compare engine output to the recorded JSON (exit 1 on drift)

Placeholders in fixture files are replaced when materialized, so no token-shaped string is ever committed:
  __FAKE_ORG_TOKEN__   -> sntrys_<base64 payload>_<43 chars>
  __FAKE_USER_TOKEN__  -> sntryu_<64 hex>
"""
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
FIX = os.path.join(ROOT, "evals", "fixtures")
EXP = os.path.join(ROOT, "evals", "expected")
CTX = os.path.join(ROOT, "bin", "sentry-ctx")


def fake_org():
    payload = base64.b64encode(json.dumps({"iat": 1700000000, "url": "https://sentry.io", "region_url": "https://us.sentry.io", "org": "fixture-org"}).encode()).decode().rstrip("=")
    tail = base64.b64encode(hashlib.sha256(b"fixture").digest()).decode().rstrip("=")[:43]
    return "sntrys_%s_%s" % (payload, tail)


def fake_user():
    return "sntryu_" + hashlib.sha256(b"fixture-user").hexdigest()


def names():
    return sorted(d for d in os.listdir(FIX) if os.path.isdir(os.path.join(FIX, d)))


def materialize(out, which):
    os.makedirs(out, exist_ok=True)
    made = []
    for n in which or names():
        src, dst = os.path.join(FIX, n), os.path.join(out, n)
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=False)
        for dp, dn, fn in os.walk(dst):
            for f in fn:
                p = os.path.join(dp, f)
                try:
                    t = open(p, encoding="utf-8").read()
                except (UnicodeDecodeError, OSError):
                    continue
                if "__FAKE_" in t:
                    open(p, "w", encoding="utf-8").write(t.replace("__FAKE_ORG_TOKEN__", fake_org()).replace("__FAKE_USER_TOKEN__", fake_user()))
        env = dict(os.environ, GIT_AUTHOR_NAME="fixture", GIT_AUTHOR_EMAIL="fixture@example.invalid", GIT_COMMITTER_NAME="fixture", GIT_COMMITTER_EMAIL="fixture@example.invalid")
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dst, check=True, env=env)
        subprocess.run(["git", "add", "-A"], cwd=dst, check=True, env=env)
        subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=dst, check=True, env=env)
        made.append(dst)
    return made


def detect(path):
    p = subprocess.run([CTX, "--path", path, "detect"], capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("detect failed on %s:\n%s" % (path, p.stderr))
    d = json.loads(p.stdout)
    d["repo"].pop("elapsed_ms", None)
    d.pop("elapsed_ms", None)
    d["repo"]["name"] = "<fixture>"
    d["repo"].pop("files_scanned", None)
    return d


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "materialize":
        for p in materialize(rest[0], rest[1:]):
            print(p)
        return 0
    which = rest or names()
    tmp = tempfile.mkdtemp(prefix="sentry-fixtures-")
    try:
        bad = 0
        for n in which:
            path = materialize(tmp, [n])[0]
            got = detect(path)
            f = os.path.join(EXP, n + ".detect.json")
            if cmd == "record":
                os.makedirs(EXP, exist_ok=True)
                json.dump(got, open(f, "w"), indent=1, sort_keys=True)
                open(f, "a").write("\n")
                print("recorded", n)
            elif cmd == "check":
                want = json.load(open(f)) if os.path.isfile(f) else None
                ok = want == json.loads(json.dumps(got, sort_keys=True))
                print("%-34s %s" % (n, "ok" if ok else ("DRIFT" if want else "NO EXPECTED FILE")))
                bad += 0 if ok else 1
        return 1 if bad else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
