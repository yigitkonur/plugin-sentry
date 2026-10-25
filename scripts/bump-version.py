#!/usr/bin/env python3
"""Bump the plugin version for CI (the `release` job in .github/workflows/ci.yml).

  bump-version.py --range BEFORE..AFTER [--write] [--github-output]

Looks at the commits in the range. If none touched a shipped path (see SHIPPED), prints `bump=false` and exits 0. Otherwise the level comes
from the commit subjects: a `!:` after the type or a BREAKING CHANGE line is major, `feat` is minor, anything else is patch. With --write both
manifests are rewritten in place (text replace, so the JSON formatting stays). Exit 2 when the two manifests disagree."""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MANIFESTS = [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"]
SHIPPED = (".claude-plugin/", "skills/", "agents/", "hooks/", "engine/", "references/", "data/", "bin/")


def git(*a):
    return subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True, check=True).stdout


def versions():
    found = set()
    for m in MANIFESTS:
        found |= set(re.findall(r'"version"\s*:\s*"(\d+\.\d+\.\d+)"', open(os.path.join(ROOT, m)).read()))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--github-output", action="store_true")
    a = ap.parse_args()
    rng = a.range
    if re.match(r"^0+\.\.", rng):  # first push of a branch: look at the last commit only
        rng = "HEAD~1..HEAD"
    files = [f for f in git("diff", "--name-only", rng).splitlines() if f.startswith(SHIPPED) and f not in MANIFESTS]
    subjects = git("log", "--format=%s%n%b%x00", rng).split("\x00")
    cur = versions()
    if len(cur) != 1:
        print("manifests disagree on the version: %s" % sorted(cur), file=sys.stderr)
        return 2
    old = cur.pop()
    out = {"bump": "false", "old": old, "new": old, "level": "none", "files": str(len(files))}
    if files:
        text = "\n".join(subjects)
        level = "major" if re.search(r"^\w+(\([^)]*\))?!:|^BREAKING CHANGE", text, re.M) else "minor" if re.search(r"^feat(\([^)]*\))?:", text, re.M) else "patch"
        x, y, z = (int(n) for n in old.split("."))
        new = {"major": "%d.0.0" % (x + 1), "minor": "%d.%d.0" % (x, y + 1), "patch": "%d.%d.%d" % (x, y, z + 1)}[level]
        out.update({"bump": "true", "new": new, "level": level})
        if a.write:
            for m in MANIFESTS:
                p = os.path.join(ROOT, m)
                s = open(p).read()
                open(p, "w").write(s.replace('"version": "%s"' % old, '"version": "%s"' % new))
            json.load(open(os.path.join(ROOT, MANIFESTS[0])))
            json.load(open(os.path.join(ROOT, MANIFESTS[1])))
            assert versions() == {new}, "manifests do not agree after the bump"
    for k, v in out.items():
        print("%s=%s" % (k, v))
    if a.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            for k, v in out.items():
                f.write("%s=%s\n" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
