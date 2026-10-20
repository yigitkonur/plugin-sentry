"""Stale-API matching: data/stale-apis/*.tsv applied to a unit's installed SDK major and platform.
The engine locates (file:line), the auditor judges. The PostToolUse hook reuses `rows_for` and `scan_text`."""
from __future__ import annotations

import os
import re

from . import paths, util

ECO_FILE = {"js": "js.tsv", "python": "python.tsv", "apple": "cocoa.tsv", "jvm": "jvm.tsv", "dotnet": "dotnet.tsv", "ruby": "ruby.tsv", "php": "php.tsv", "go": "go.tsv", "dart": "dart.tsv", "rust": "rust.tsv", "elixir": "elixir.tsv"}
_cache: dict = {}


def _files_for(eco: str):
    fn = ECO_FILE.get(eco)
    if not fn:
        return []
    d = paths.data_path("stale-apis")
    base = fn[:-4]
    names = [fn] + sorted(f for f in (os.listdir(d) if os.path.isdir(d) else []) if f.startswith(base + "-") and f.endswith(".tsv"))
    return names


def load(eco: str):
    key = eco
    if key not in _cache:
        rows = []
        for fn in _files_for(eco):
            p = paths.data_path("stale-apis", fn)
            if not os.path.isfile(p):
                continue
            for line in open(p, encoding="utf-8"):
                if line.startswith("#") or not line.strip():
                    continue
                c = line.rstrip("\n").split("\t")
                if len(c) == 8:
                    rows.append({"pkg": re.compile(c[0]), "majors": c[1].split(","), "name": c[2], "kind": c[3], "message": c[4], "since": c[5], "source": c[6], "when": c[7]})
        _cache[key] = rows
    return _cache[key]


def _when_ok(when: str, unit: dict) -> bool:
    if not when:
        return True
    k, _, v = when.partition(":")
    want = v.split(",")
    if k == "platform":
        return any(w in (unit.get("platforms") or []) for w in want)
    if k == "role":
        return unit.get("role") in want
    return True


def installed(unit: dict):
    """[(package name, major)] for the unit's SDK packages (tooling excluded)."""
    out = []
    for p in unit.get("sentry", {}).get("packages", []):
        if p.get("kind") == "tooling" or not p.get("resolved"):
            continue
        m = re.match(r"(\d+)", str(p["resolved"]).lstrip("v"))
        if m:
            out.append((p["name"], m.group(1)))
    return out


def rows_for(unit: dict):
    rows = load(unit["ecosystem"])
    pk = installed(unit)
    res = []
    for r in rows:
        if r["kind"] == "info":
            continue
        if not _when_ok(r["when"], unit):
            continue
        for name, major in pk:
            if r["pkg"].match(name) and major in r["majors"]:
                res.append(r)
                break
    return res


def _rx(name: str):
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")


def scan_text(rows, text: str, rel: str):
    hits = []
    lines = text.splitlines()
    for r in rows:
        rx = _rx(r["name"])
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith(("//", "#", "*", "/*", "<!--")):
                continue
            if rx.search(line):
                hits.append({"file": rel, "line": i, "name": r["name"], "kind": r["kind"], "message": r["message"], "since": r["since"], "source": r["source"], "text": s[:120]})
    return hits


def scan_unit(unit: dict, root: str, all_files: bool = False):
    rows = rows_for(unit)
    if not rows:
        return {"unit": unit["id"], "checked_rows": 0, "hits": []}
    sentry = unit["sentry"]
    files = {s["file"] for s in sentry.get("init_sites", [])}
    files |= set(sentry.get("config_files", []))
    for loc in sentry.get("build", {}).values():
        files.add(loc.split(":")[0])
    if all_files:
        files |= {f for f in unit.get("_files", [])}
    hits = []
    for rel in sorted(files):
        p = os.path.join(root, rel)
        if os.path.isfile(p):
            hits += scan_text(rows, util.read_text(p, 400_000), rel)
    return {"unit": unit["id"], "checked_rows": len(rows), "files_scanned": len(files), "hits": hits}
