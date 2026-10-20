"""H3: after an edit, flag removed/renamed SDK options for the DETECTED SDK major, on the edited text only."""
from __future__ import annotations

import os

from .. import stale, util
from . import common


def _new_texts(ti: dict):
    out = []
    for k in ("content", "new_string"):
        if isinstance(ti.get(k), str):
            out.append(ti[k])
    for e in ti.get("edits") or []:
        if isinstance(e, dict) and isinstance(e.get("new_string"), str):
            out.append(e["new_string"])
    return out


def run():
    inp = common.read_input()
    if common.mode() != "on":
        return
    ti = inp.get("tool_input") or {}
    path = ti.get("file_path") or ""
    root = common.project_dir(inp)
    if not path:
        return
    rel = os.path.relpath(path, root) if os.path.isabs(path) else path
    if rel.startswith(".."):
        return
    units = common.load_units(root)
    if not units:
        return
    best = None
    for u in units:
        r = u["root"]
        if r == "." or rel == r or rel.startswith(r + "/"):
            if best is None or len(u["root"]) > len(best["root"]):
                best = u
    if not best or best["sentry"]["status"] == "absent":
        return
    rows = stale.rows_for(best)
    if not rows:
        return
    hits = []
    for t in _new_texts(ti):
        hits += stale.scan_text(rows, t, rel)
    seen, lines = set(), []
    for h in hits:
        if h["name"] in seen:
            continue
        seen.add(h["name"])
        lines.append("`%s` (%s): %s [%s]" % (h["name"], h["kind"], h["message"], h["source"]))
    if not lines:
        return
    pk = [p for p in best["sentry"]["packages"] if p.get("kind") != "tooling" and p.get("resolved")]
    head = "Sentry stale-API check for %s %s in %s:" % (pk[0]["name"], pk[0]["resolved"], rel) if pk else "Sentry stale-API check:"
    common.context("PostToolUse", (head + " " + " ".join(lines[:4]) + " This list comes from the official migration guides: apply the instruction given for each one to the file you just edited, now, without installing the SDK or re-deriving it. Only when an entry gives no replacement, look it up with `sentry-ctx docs page`.")[:900])
