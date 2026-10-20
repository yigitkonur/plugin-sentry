#!/usr/bin/env python3
"""Weekly drift check: every `removed` or `renamed` row of data/stale-apis/js.tsv that applies to the current SDK major (11) must
be rejected by the real, freshly installed @sentry/browser, @sentry/node and @sentry/cloudflare types, both as a `Sentry.init`
option and as an export. A name the SDK still accepts in either position is a table row that gives wrong advice.

  check-sdk-types.py [--major 11] [--keep]    needs node, npm and network
  exit 0 all rows consistent | 1 a row is contradicted | 2 the check itself could not run (install, compiler, controls, no rows)

A name counts as rejected only when TypeScript says it does not exist (TS2353, TS2339, TS2551, TS2561, TS2305, TS2724). Any other compiler
error (an unresolved module, a syntax error) is not evidence, and fails the run. Two known-valid control names (`tracesSampleRate`,
`captureException`) must compile cleanly in every package, so a broken setup cannot look like a pass.
This is a necessary-condition check: it proves the SDK no longer accepts the name at init-option or export level, not why it was removed.
Rows scoped to one framework package (for example @sentry/nextjs) are listed as not checked."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PKGS = ["@sentry/browser", "@sentry/node", "@sentry/cloudflare"]
GENERIC = re.compile(r"^\^@sentry/\(\?!")
IDENT = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
REJECT = {"TS2353", "TS2339", "TS2551", "TS2561", "TS2305", "TS2724"}  # "unknown property" / "no such member or export"
CONTROLS = ("tracesSampleRate", "captureException")  # an init option and an export that exist in every package


def rows(major):
    out, skipped, invalid = [], [], []
    for line in open(os.path.join(ROOT, "data", "stale-apis", "js.tsv"), encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        c = line.rstrip("\n").split("\t")
        if len(c) < 4 or c[3] not in ("removed", "renamed"):
            continue
        if major not in [m.strip() for m in c[1].split(",")]:
            continue
        if not IDENT.match(c[2]):
            invalid.append(c[2])
            continue
        (out if GENERIC.match(c[0]) else skipped).append({"pkg": c[0], "name": c[2], "kind": c[3]})
    return out, skipped, invalid


def option_src(pkg, name):
    if pkg.endswith("/cloudflare"):  # no init(): the options type is what withSentry takes
        return 'import * as S from "%s";\nconst o: S.CloudflareOptions = { dsn: "x", %s: undefined as any };\n' % (pkg, name)
    return 'import * as S from "%s";\nS.init({ dsn: "x", %s: undefined as any });\n' % (pkg, name)


def export_src(pkg, name):
    return 'import * as S from "%s";\nS.%s;\n' % (pkg, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--major", default="11")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    todo, skipped, invalid = rows(a.major)
    if invalid:
        print("rows with a name that is not a plain identifier (fix the table): %s" % ", ".join(invalid))
        return 2
    if not todo:
        print("no removed or renamed rows apply to major %s: nothing was checked" % a.major)
        return 2
    work = tempfile.mkdtemp(prefix="sentry-sdk-types-")
    try:
        sh = lambda cmd, **kw: subprocess.run(cmd, cwd=work, capture_output=True, text=True, **kw)  # noqa: E731
        sh(["npm", "init", "-y"])
        r = sh(["npm", "install", "--no-audit", "--no-fund", "--ignore-scripts", "typescript", "@types/node", "@cloudflare/workers-types"] + [p + "@" + a.major for p in PKGS], timeout=600)
        tsc = os.path.join(work, "node_modules", ".bin", "tsc")
        if r.returncode != 0 or not os.path.isfile(tsc):
            print("npm install failed or typescript is missing:\n" + (r.stderr or "")[-800:])
            return 2
        try:
            versions = {p: json.load(open(os.path.join(work, "node_modules", p, "package.json")))["version"] for p in PKGS}
        except (OSError, ValueError, KeyError) as e:
            print("cannot read the installed package versions: %s" % e)
            return 2
        os.makedirs(os.path.join(work, "t"))
        cases = {}  # file -> (row index or control name, package, position)
        for p in PKGS:
            short = p.split("/")[1]
            for form, src, name in (("option", option_src, CONTROLS[0]), ("export", export_src, CONTROLS[1])):
                fn = "t/ctl_%s_%s.ts" % (short, form)
                open(os.path.join(work, fn), "w").write(src(p, name))
                cases[fn] = ("control", p, form)
        for i, row in enumerate(todo):
            for p in PKGS:
                for form, src in (("option", option_src), ("export", export_src)):
                    fn = "t/r%d_%s_%s.ts" % (i, p.split("/")[1], form)
                    open(os.path.join(work, fn), "w").write(src(p, row["name"]))
                    cases[fn] = (i, p, form)
        open(os.path.join(work, "tsconfig.json"), "w").write('{"compilerOptions":{"target":"ES2022","module":"NodeNext","moduleResolution":"NodeNext","strict":true,"noEmit":true,"skipLibCheck":true,"types":["node"]},"include":["t"]}')
        res = subprocess.run([tsc, "-p", "tsconfig.json"], cwd=work, capture_output=True, text=True, timeout=600)
        codes = {}  # file -> set of TS codes
        for m in re.finditer(r"^(t/[^()\s]+)\(\d+,\d+\): error (TS\d+)", res.stdout, re.M):
            codes.setdefault(m.group(1), set()).add(m.group(2))
        broken = [f for f, c in cases.items() if cases[f][0] == "control" and f in codes]
        if broken:
            print("the controls did not compile cleanly, so the check cannot be trusted: %s\n%s" % (", ".join(broken), res.stdout[:600]))
            return 2
        unclassified = sorted(f for f, c in codes.items() if not (c & REJECT))
        if unclassified:
            print("compiler errors that are not 'does not exist' (a setup problem, not evidence): %s\n%s" % (", ".join(unclassified[:6]), res.stdout[:600]))
            return 2
        print("SDK versions tested: " + ", ".join("%s %s" % (p, v) for p, v in versions.items()))
        bad = 0
        for i, row in enumerate(todo):
            accepted = ["%s as %s" % (cases[f][1], cases[f][2]) for f in sorted(cases) if cases[f][0] == i and f not in codes]
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
