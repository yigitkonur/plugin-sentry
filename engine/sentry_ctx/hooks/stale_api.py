"""H3: after an edit, flag removed/renamed SDK options for the DETECTED SDK major, on the edited text only."""
from __future__ import annotations

import os

from .. import stale, util
from . import common


def run():
    inp = common.read_input()
    if common.mode() != "on":
        return
    root = common.project_dir(inp)
    lines_all, head = [], None
    units = None
    for path, texts in common.written(inp):
        if not path:
            continue
        rel = os.path.relpath(path, root) if os.path.isabs(path) else path
        if rel.startswith(".."):
            continue
        if units is None:
            units = common.load_units(root) or []
        best = None
        for u in units:
            r = u["root"]
            if r == "." or rel == r or rel.startswith(r + "/"):
                if best is None or len(u["root"]) > len(best["root"]):
                    best = u
        if not best or best["sentry"]["status"] == "absent":
            continue
        rows = stale.rows_for(best)
        if not rows:
            continue
        hits = []
        for t in texts:
            hits += stale.scan_text(rows, t, rel)
        seen = set()
        for h in hits:
            if h["name"] in seen:
                continue
            seen.add(h["name"])
            lines_all.append("`%s` (%s): %s [%s]" % (h["name"], h["kind"], h["message"], h["source"]))
        if hits and head is None:
            pk = [p for p in best["sentry"]["packages"] if p.get("kind") != "tooling" and p.get("resolved")]
            head = "Sentry stale-API check for %s %s in %s:" % (pk[0]["name"], pk[0]["resolved"], rel) if pk else "Sentry stale-API check:"
    if not lines_all:
        return
    common.context("PostToolUse", (head + " " + " ".join(lines_all[:4]) + " This list comes from the official migration guides: apply the instruction given for each one to the file you just edited, now, without installing the SDK or re-deriving it. Only when an entry gives no replacement, look it up with `sentry-ctx docs page`.")[:900])
