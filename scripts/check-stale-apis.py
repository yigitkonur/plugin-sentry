#!/usr/bin/env python3
"""Every stale-API row must be backed by its source page: the name has to appear in the fetched text.
Exit 1 on any miss. Used locally and in CI (weekly)."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import docs, util  # noqa: E402

D = os.path.join(ROOT, "data", "stale-apis")
bad = 0
cache = {}
# `check-stale-apis.py [file.tsv ...]` checks the given files (e.g. a staged table); no argument checks data/stale-apis/*.tsv
files = [(os.path.basename(a), a) for a in sys.argv[1:]] or [(fn, os.path.join(D, fn)) for fn in sorted(os.listdir(D)) if fn.endswith(".tsv")]
for fn, path in files:
    for ln, line in enumerate(open(path, encoding="utf-8"), 1):
        if line.startswith("#") or not line.strip():
            continue
        cols = line.rstrip("\n").split("\t")
        if len(cols) != 8:
            print("%s:%d: expected 8 columns, got %d" % (fn, ln, len(cols)))
            bad += 1
            continue
        pkg, majors, name, kind, msg, since, src, when = cols
        if src not in cache:
            try:
                cache[src] = docs.fetch(src)[1]
            except util.EngineError as e:
                cache[src] = None
                print("%s:%d: cannot fetch %s: %s" % (fn, ln, src, e))
        txt = cache[src]
        if txt is None:
            bad += 1
        elif kind == "wrong-name":
            right = msg.split("it is ")[-1].strip().rstrip(".")
            if right not in txt:
                print("%s:%d: correct name %r not found in %s" % (fn, ln, right, src))
                bad += 1
        elif name not in txt:
            print("%s:%d: %r not found in %s" % (fn, ln, name, src))
            bad += 1
print("stale-API rows checked; failures: %d" % bad)
sys.exit(1 if bad else 0)
