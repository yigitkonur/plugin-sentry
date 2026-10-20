#!/usr/bin/env python3
"""Weekly drift check: every `removed` or `renamed` row of data/stale-apis/js.tsv that applies to the current SDK major (11) must
be rejected by the real, freshly installed @sentry/browser, @sentry/node and @sentry/cloudflare types, both as a `Sentry.init`
option (TS2353) and as an export (TS2339). A name the SDK still accepts in either position is a table row that gives wrong advice.

  check-sdk-types.py [--major 11] [--keep]    needs node, npm and network; exit 1 if a row is contradicted

This is a necessary-condition check: it proves the SDK no longer accepts the name at init-option or export level, not why it was removed.
Rows scoped to one framework package (for example @sentry/nextjs) are listed as not checked."""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PKGS = ["@sentry/browser", "@sentry/node", "@sentry/cloudflare"]
GENERIC = re.compile(r"^\^@sentry/\(\?!")


def rows(major):
    out, skipped = [], []
    for line in open(os.path.join(ROOT, "data", "stale-apis", "js.tsv"), encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        c = line.rstrip("\n").split("\t")
        if len(c) < 4 or c[3] not in ("removed", "renamed"):
            continue
        if major not in [m.strip() for m in c[1].split(",")]:
            continue
        (out if GENERIC.match(c[0]) else skipped).append({"pkg": c[0], "name": c[2], "kind": c[3]})
    return out, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--major", default="11")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    todo, skipped = rows(a.major)
    work = tempfile.mkdtemp(prefix="sentry-sdk-types-")
    try:
        sh = lambda cmd, **kw: subprocess.run(cmd, cwd=work, capture_output=True, text=True, **kw)  # noqa: E731
        sh(["npm", "init", "-y"])
        r = sh(["npm", "install", "--no-audit", "--no-fund", "--ignore-scripts", "typescript", "@types/node", "@cloudflare/workers-types"] + [p + "@" + a.major for p in PKGS], timeout=600)
        if r.returncode != 0:
            print("npm install failed:\n" + r.stderr[-800:])
            return 2
        versions = {p: re.search(r'"version": "([^"]+)"', open(os.path.join(work, "node_modules", p, "package.json")).read()).group(1) for p in PKGS}
        os.makedirs(os.path.join(work, "t"))
        cases = {}
        for i, row in enumerate(todo):
            for p in PKGS:
                short = p.split("/")[1]
                opt = ('import * as S from "%s";\nconst o: S.CloudflareOptions = { dsn: "x", %s: undefined as any };\n' if short == "cloudflare"  # no init(): options go to withSentry
                       else 'import * as S from "%s";\nS.init({ dsn: "x", %s: undefined as any });\n')
                for form, body in (("option", opt % (p, row["name"])),
                                   ("export", 'import * as S from "%s";\nS.%s;\n' % (p, row["name"]))):
                    fn = "t/r%d_%s_%s.ts" % (i, short, form)
                    open(os.path.join(work, fn), "w").write(body)
                    cases[fn] = (i, p, form)
        open(os.path.join(work, "tsconfig.json"), "w").write('{"compilerOptions":{"target":"ES2022","module":"NodeNext","moduleResolution":"NodeNext","strict":true,"noEmit":true,"skipLibCheck":true,"types":["node"]},"include":["t"]}')
        res = sh(["npx", "tsc", "-p", "tsconfig.json"], timeout=600)
        errs = set()
        for m in re.finditer(r"^(t/[^()\s]+)\(\d+,\d+\): error (TS\d+)", res.stdout, re.M):
            errs.add(m.group(1))
        print("SDK versions tested: " + ", ".join("%s %s" % (p, v) for p, v in versions.items()))
        bad = 0
        for i, row in enumerate(todo):
            accepted = []  # (package, position) where the removed name still compiles
            for p in PKGS:
                for f, (ri, pp, ff) in cases.items():
                    if ri == i and pp == p and f not in errs:
                        accepted.append("%s as %s" % (p, ff))
            ok = not accepted
            bad += 0 if ok else 1
            print("  %-4s %-8s %-34s %s" % ("ok" if ok else "FAIL", row["kind"], row["name"], "" if ok else "still accepted: " + ", ".join(accepted)))
        for row in skipped:
            print("  skip %-8s %-34s (package-scoped row %s: needs that framework installed)" % (row["kind"], row["name"], row["pkg"]))
        print("\n%s: %d rows checked, %d contradicted, %d not checked" % ("FAILED" if bad else "ALL ROWS CONSISTENT", len(todo), bad, len(skipped)))
        return 1 if bad else 0
    finally:
        if not a.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
