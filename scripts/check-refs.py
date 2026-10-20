#!/usr/bin/env python3
"""Every `sentry-ctx flow <name>` and `sentry-ctx ref <name>` mentioned in skills, agents, flows and references must exist.
Exit 1 on a dangling name (a skill that injects a missing flow breaks silently for the user)."""
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import refs  # noqa: E402

flows = {f[:-3] for f in os.listdir(os.path.join(ROOT, "references", "forge", "flows")) if f.endswith(".md")}
bad = 0
for base in ("skills", "agents", "references/forge", "README.md", "AGENTS.md"):
    p = os.path.join(ROOT, base)
    files = [p] if os.path.isfile(p) else [os.path.join(d, f) for d, _, fs in os.walk(p) for f in fs if f.endswith(".md")]
    for fp in files:
        text = open(fp, encoding="utf-8").read()
        for m in re.finditer(r"sentry-ctx flow ([a-z][a-z-]*)", text):
            if m.group(1) not in flows:
                print("%s: unknown flow %r (have %s)" % (os.path.relpath(fp, ROOT), m.group(1), ", ".join(sorted(flows))))
                bad += 1
        for m in re.finditer(r"sentry-ctx ref ((?:forge|upstream|products|platforms)/[A-Za-z0-9_./-]+)", text):
            name = m.group(1).rstrip(".")
            if "<" in name or not refs._resolve(name):
                if "<" not in name:
                    print("%s: unknown reference %r" % (os.path.relpath(fp, ROOT), name))
                    bad += 1
print("flow/ref names checked; dangling: %d" % bad)
sys.exit(1 if bad else 0)
