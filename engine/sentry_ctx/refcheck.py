"""`ref verify`: option names in reference modules must be backed by an official page fetched this session.

A module declares the identifiers it relies on in a fenced block:

    ```identifiers
    dataCollection | https://docs.sentry.io/platforms/javascript/configuration/options/
    ```

Every declared name must appear in the fetched text of its URL. Every option-shaped token in the body
(camelCase or snake_case in single backticks) must be declared, listed under `## Unconfirmed`, known to a
stale-API table, or be in data/ref-allow.txt. Anything else is a failure: the agent that wrote it did not look it up.
"""
from __future__ import annotations

import os
import re

from . import docs, paths, refs, util

CAMEL = re.compile(r"^[a-z][a-z0-9]*[A-Z][A-Za-z0-9]*$|^[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*$")
SNAKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)+$")
BLOCK = re.compile(r"```identifiers\n(.*?)```", re.S)
INLINE = re.compile(r"(?<!`)`([A-Za-z_][A-Za-z0-9_]*)`(?!`)")
_page_cache: dict = {}


def allowlist():
    p = paths.data_path("ref-allow.txt")
    out = set()
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8"):
            line = line.split("#", 1)[0].strip()
            if line:
                out.add(line)
    return out


def stale_names():
    out = set()
    d = paths.data_path("stale-apis")
    if os.path.isdir(d):
        for fn in os.listdir(d):
            if fn.endswith(".tsv"):
                for line in open(os.path.join(d, fn), encoding="utf-8"):
                    if line.startswith("#") or not line.strip():
                        continue
                    cols = line.rstrip("\n").split("\t")
                    if len(cols) > 2:
                        out.add(cols[2])
    return out


def _section(text, title):
    m = re.search(r"(?ims)^##\s+%s\s*$(.*?)(?=^##\s|\Z)" % re.escape(title), text)
    return m.group(1) if m else ""


def _page_text(url):
    if url not in _page_cache:
        _, text, _ = docs.fetch(url)
        _page_cache[url] = text
    return _page_cache[url]


def declared(text):
    out = []
    for blk in BLOCK.findall(text):
        for line in blk.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, _, url = [x.strip() for x in line.partition("|")]
            out.append((name, url))
    return out


def verify(name: str):
    p = refs._resolve(name)
    if not p:
        raise util.EngineError("no reference named %r" % name, 6)
    text = util.read_text(p, 400_000)
    rel = os.path.relpath(p, paths.ref_root())
    res = {"name": name, "file": rel, "errors": [], "warnings": [], "declared": 0, "checked_urls": 0}
    if "/upstream/" in "/" + rel or rel.startswith("upstream/"):
        res["note"] = "vendored upstream content is not verified here"
        return res
    decl = declared(text)
    res["declared"] = len(decl)
    unconfirmed = set(re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)`", _section(text, "Unconfirmed")))
    known = {n for n, _ in decl} | unconfirmed | stale_names() | allowlist()
    for n, url in decl:
        if not url:
            res["errors"].append("identifier %r has no URL" % n)
            continue
        try:
            pt = _page_text(url)
            res["checked_urls"] += 1
        except util.EngineError as e:
            res["errors"].append("cannot fetch %s for %r: %s" % (url, n, e))
            continue
        if n not in pt:
            res["errors"].append("identifier %r not found in %s" % (n, url))
    body = BLOCK.sub("", text)
    body = re.sub(r"(?ims)^##\s+Unconfirmed\s*$.*?(?=^##\s|\Z)", "", body)
    seen = set()
    for tok in INLINE.findall(body):
        if tok in seen:
            continue
        seen.add(tok)
        if (CAMEL.match(tok) or SNAKE.match(tok)) and tok not in known:
            res["errors"].append("option-shaped token `%s` is neither declared (with a URL), listed under Unconfirmed, nor allowlisted" % tok)
    if not re.search(r"(?im)^##\s+Sources\s*$", text):
        res["errors"].append("missing ## Sources section")
    res["ok"] = not res["errors"]
    return res
