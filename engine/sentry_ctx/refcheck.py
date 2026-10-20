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


PRODUCT_SECTIONS = ["Fit", "Properly configured", "Checks", "Common mistakes", "Volume, cost and overhead", "Verify (R6)", "Sources", "Identifiers", "Unconfirmed"]
PLATFORM_SECTIONS = ["Detect", "Install route", "Init placement", "Options by SDK major", "Product support matrix", "Release and artifacts", "Privacy", "Verify recipe", "Gotchas", "Sources", "Identifiers", "Unconfirmed"]
MAX_LINES = 200


def _check_ids():
    from . import findings
    return set(findings.checks())


def verify_text(text: str, label: str, kind: str, name: str = ""):
    """kind: 'product' | 'platform' | None (no structural checks)."""
    res = {"name": name or label, "file": label, "errors": [], "warnings": [], "declared": 0, "checked_urls": 0}
    if kind in ("product", "platform"):
        want = PRODUCT_SECTIONS if kind == "product" else PLATFORM_SECTIONS
        have = {m.strip().lower() for m in re.findall(r"(?m)^##\s+(.+?)\s*$", text)}
        for sec in want:
            if not any(h == sec.lower() or h.startswith(sec.lower() + " (") for h in have):
                res["errors"].append("missing section ## %s" % sec)
        n = text.count("\n") + 1
        if n > MAX_LINES:
            res["errors"].append("%d lines; keep a module under %d (cut, do not compress)" % (n, MAX_LINES))
        if not re.match(r"# .+\((product id|module): [a-z0-9/-]+\)\s*\n", text):
            res["errors"].append("first line must be '# <Title> (product id: <id>)' or '# <Title> (module: platforms/<id>)'")
    if kind == "product":
        ids = _check_ids()
        for row in _section(text, "Checks").splitlines():
            m = re.match(r"\|\s*`?([a-z][a-z0-9-]*\.[a-z0-9.-]+)`?\s*\|", row)
            if m and m.group(1) not in ids and not m.group(1).startswith("x."):
                res["errors"].append("check id %r is not in data/checks.tsv (use x.<slug> for an unlisted check)" % m.group(1))
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
    for u in re.findall(r"https?://[^\s)>\]`|]+", text):
        host = re.sub(r"^https?://([^/]+).*$", r"\1", u)
        if host not in ("docs.sentry.io", "develop.sentry.dev", "cli.sentry.dev", "github.com", "sentry.io", "spotlightjs.com", "skills.sentry.dev", "mcp.sentry.dev", "opentelemetry.io", "docs.github.com", "developer.apple.com", "developer.android.com", "docs.unity3d.com", "dev.epicgames.com", "learn.microsoft.com", "pkg.go.dev", "docs.rs", "hexdocs.pm", "pub.dev", "docs.python.org", "nodejs.org"):
            res["warnings"].append("non-Sentry host %s: cite official Sentry pages for Sentry facts" % host)
    res["ok"] = not res["errors"]
    return res


def _kind_of(rel: str):
    r = rel.replace("\\", "/")
    if "/products/" in "/" + r:
        return "product"
    if "/platforms/" in "/" + r:
        return "platform"
    return None


def verify_file(path: str, kind: str = None):
    text = util.read_text(path, 400_000)
    return verify_text(text, path, kind or _kind_of(path), name=os.path.basename(path))


def verify(name: str):
    p = refs._resolve(name)
    if not p:
        raise util.EngineError("no reference named %r" % name, 6)
    text = util.read_text(p, 400_000)
    rel = os.path.relpath(p, paths.ref_root())
    if "/upstream/" in "/" + rel or rel.startswith("upstream/"):
        return {"name": name, "file": rel, "errors": [], "warnings": [], "declared": 0, "checked_urls": 0, "note": "vendored upstream content is not verified here", "ok": True}
    return verify_text(text, rel, _kind_of(rel), name=name)
