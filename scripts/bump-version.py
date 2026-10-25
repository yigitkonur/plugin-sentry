#!/usr/bin/env python3
"""Decide, and with --write apply, the next version of every plugin in a Claude Code plugin repo. Used by the `release` job of CI.

  bump-version.py [--write] [--github-output] [--since-tag | --range A..B]

For each plugin of .claude-plugin/marketplace.json (a local `source`), or the root plugin when there is no marketplace entry: look at the
commits since that plugin's latest tag (or in --range) that touched files inside the plugin's folder, ignoring docs, tests, evals, scripts
and CI. None: no release. Otherwise the level comes from the subjects: `type!:` or a BREAKING CHANGE line is major, `feat` is minor,
anything else patch. --write sets the new version in the marketplace entry, the plugin's .claude-plugin/plugin.json and, when present, its
.codex-plugin/plugin.json. Tags are `v<version>` for a repo with one root plugin, `<name>--v<version>` otherwise (what `claude plugin tag`
makes). Prints one `release=<name> <old> <new> <tag> <level> <n files> <folder>` line per plugin. Python 3.9+, standard library only."""
import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SKIP_TOP = {"tests", "test", "evals", "docs", "scripts", "fixtures", ".github", ".gitignore", "node_modules"}
SKIP_FILE = re.compile(r"(^|/)(README|LICENSE|NOTICE|AGENTS|CLAUDE|CHANGELOG|PORT|THIRD_PARTY_NOTICES)[^/]*$|^[^/]+\.md$", re.I)


def git(*a, check=True):
    r = subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit("bump-version: git %s: %s" % (" ".join(a), r.stderr.strip()[:200]))
    return r.stdout


def load(rel):
    p = os.path.join(ROOT, rel)
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def plugins():
    mk = load(".claude-plugin/marketplace.json")
    out = []
    for e in (mk or {}).get("plugins", []):
        src = e.get("source")
        if isinstance(src, str) and (src == "." or src.startswith("./")):
            out.append({"name": e["name"], "base": "" if src in (".", "./") else os.path.normpath(src), "version": e.get("version")})
    if not out and load(".claude-plugin/plugin.json"):
        d = load(".claude-plugin/plugin.json")
        out.append({"name": d["name"], "base": "", "version": d.get("version")})
    for p in out:
        pj = load(os.path.join(p["base"], ".claude-plugin", "plugin.json"))
        p["version"] = (pj or {}).get("version") or p["version"]
        if not p["version"]:
            raise SystemExit("bump-version: no version for %s" % p["name"])
    return out


def shipped(p, files):
    keep = []
    for f in files:
        rel = f if not p["base"] else (f[len(p["base"]) + 1:] if f.startswith(p["base"] + "/") else None)
        if rel is None or rel.split("/")[0] in SKIP_TOP or SKIP_FILE.search(rel) or rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            continue
        if f == ".claude-plugin/marketplace.json":
            continue
        keep.append(f)
    return keep


def level(subjects):
    text = "\n".join(subjects)
    if re.search(r"^\w+(\([^)]*\))?!:|^BREAKING CHANGE", text, re.M):
        return "major"
    return "minor" if re.search(r"^feat(\([^)]*\))?:", text, re.M) else "patch"


def bump(v, lv):
    x, y, z = (int(n) for n in v.split("."))
    return {"major": "%d.0.0" % (x + 1), "minor": "%d.%d.0" % (x, y + 1), "patch": "%d.%d.%d" % (x, y, z + 1)}[lv]


def write(p, new):
    for rel in (os.path.join(p["base"], ".claude-plugin", "plugin.json"), os.path.join(p["base"], ".codex-plugin", "plugin.json")):
        d = load(rel)
        if d is not None:
            d["version"] = new
            json.dump(d, open(os.path.join(ROOT, rel), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            open(os.path.join(ROOT, rel), "a").write("\n")
    mk = load(".claude-plugin/marketplace.json")
    if mk:
        for e in mk.get("plugins", []):
            if e.get("name") == p["name"] and "version" in e:
                e["version"] = new
        if len(mk.get("plugins", [])) == 1 and "version" in mk.get("metadata", {}):
            mk["metadata"]["version"] = new
        json.dump(mk, open(os.path.join(ROOT, ".claude-plugin/marketplace.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        open(os.path.join(ROOT, ".claude-plugin/marketplace.json"), "a").write("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--github-output", action="store_true")
    ap.add_argument("--range")
    a = ap.parse_args()
    ps = plugins()
    single_root = len(ps) == 1 and ps[0]["base"] == ""
    lines = []
    for p in ps:
        tag_glob = "v[0-9]*" if single_root else p["name"] + "--v[0-9]*"
        rng = a.range
        if not rng:
            tags = git("tag", "--list", tag_glob, "--sort=-v:refname", check=False).split()
            rng = "%s..HEAD" % tags[0] if tags else "HEAD~1..HEAD"
        files = shipped(p, git("diff", "--name-only", rng, check=False).splitlines())
        if not files:
            continue
        subj = git("log", "--format=%s%n%b%x00", rng, "--", *files).split("\x00")
        lv = level(subj)
        new = bump(p["version"], lv)
        tag = ("v%s" if single_root else p["name"] + "--v%s") % new
        lines.append("%s %s %s %s %s %d %s" % (p["name"], p["version"], new, tag, lv, len(files), p["base"] or "."))
        if a.write:
            write(p, new)
    for l in lines:
        print("release=" + l)
    if not lines:
        print("release=none")
    if a.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("count=%d\n" % len(lines))
            f.write("releases<<EOF\n%s\nEOF\n" % "\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
