"""Live docs access: `sentry-ctx docs page <path> [--section X]`.

docs.sentry.io returns HTTP 200 with a "Page Not Found" title for missing pages, so success is decided by the
content. cli.sentry.dev serves markdown at `<page>.md`; docs.sentry.io accepts the `.md` suffix too.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from . import paths, util

HOSTS = {"docs.sentry.io", "develop.sentry.dev", "cli.sentry.dev", "skills.sentry.dev", "mcp.sentry.dev", "developers.cloudflare.com", "raw.githubusercontent.com", "github.com"}
TTL = 24 * 3600
MAX_CHARS = 14000
UA = "sentry-plugin-docs/0.1 (+https://github.com/yigitkonur/plugin-sentry)"


class _Redirect(urllib.request.HTTPRedirectHandler):
    """docs.sentry.io answers some pages with 308, which urllib follows only from Python 3.11 (the plugin runs on 3.9).
    Redirects are followed only to the same allow-listed hosts: fetched text is untrusted, and so is where it comes from."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if (urllib.parse.urlparse(newurl).hostname or "") not in HOSTS:
            raise urllib.error.HTTPError(req.full_url, code, "redirect to a host outside the docs allow-list", headers, fp)
        if code == 308 and req.get_method() in ("GET", "HEAD"):
            code = 307
        return super().redirect_request(req, fp, code, msg, headers, newurl)

    http_error_308 = urllib.request.HTTPRedirectHandler.http_error_302


def open_url(req, timeout=25):
    return urllib.request.build_opener(_Redirect).open(req, timeout=timeout)


def normalize(page: str) -> str:
    if page.startswith("http://") or page.startswith("https://"):
        u = urllib.parse.urlparse(page)
        host, path = u.hostname, u.path
    else:
        host, path = "docs.sentry.io", "/" + page.strip().lstrip("/")
    if host not in HOSTS:
        raise util.EngineError("host %s is not allowed (only %s)" % (host, ", ".join(sorted(HOSTS))))
    path = path.split("#")[0]
    if host == "developers.cloudflare.com":  # serves the markdown of a page at <page>/index.md
        if not (path.endswith(".md") or path.endswith(".txt")):
            path = path.rstrip("/") + "/index.md"
        return "https://%s%s" % (host, path)
    if host in ("github.com", "raw.githubusercontent.com"):
        if not path.startswith("/getsentry/"):
            raise util.EngineError("only github.com/getsentry/... sources are allowed")
        if host == "github.com":
            m = re.match(r"^/(getsentry/[^/]+)/blob/(.+)$", path)
            if not m:
                raise util.EngineError("use a github.com/getsentry/<repo>/blob/<ref>/<path> URL")
            return "https://raw.githubusercontent.com/%s/%s" % (m.group(1), m.group(2))
        return "https://%s%s" % (host, path)
    if path.endswith("/llms.txt") or path.endswith(".md") or path.endswith(".txt"):
        pass
    else:
        path = path.rstrip("/") + ".md"
    if path == ".md":
        path = "/index.md"
    return "https://%s%s" % (host, path)


def _cache_file(url):
    d = os.path.join(paths.cache_dir(), "docs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, hashlib.sha1(url.encode()).hexdigest() + ".md")


def is_not_found(text: str) -> bool:
    head = text[:600]
    return bool(re.search(r'(?im)^title:\s*"?(Page Not Found|404)', head) or re.search(r"(?im)^#\s*Page Not Found", head) or head.strip().startswith("The page could not be found"))


def fetch(page: str, refresh=False):
    url = normalize(page)
    cf = _cache_file(url)
    if not refresh and os.path.isfile(cf) and time.time() - os.path.getmtime(cf) < TTL:
        return url, util.read_text(cf, 3_000_000), True
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/markdown, text/plain;q=0.9, */*;q=0.5"})
    try:
        with open_url(req) as r:
            body = r.read(3_000_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise util.EngineError("docs fetch failed: HTTP %s for %s" % (e.code, url), 5)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        if os.path.isfile(cf):
            return url, util.read_text(cf, 3_000_000), True
        raise util.EngineError("docs fetch failed (offline?): %s" % e, 5)
    if is_not_found(body):
        raise util.EngineError("docs page not found (the site answers 200 with a 'Page Not Found' title): %s" % url, 5)
    util.write_text(cf, body)
    return url, body, False


def headings(text: str):
    out = []
    in_code = False
    for i, line in enumerate(text.splitlines()):
        if line.startswith("```"):
            in_code = not in_code
        if in_code:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if m:
            title = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", m.group(2)).strip()
            out.append({"level": len(m.group(1)), "title": title, "line": i})
    return out


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def section(text: str, name: str):
    lines = text.splitlines()
    hs = headings(text)
    want = _slug(name)
    pick = None
    for h in hs:
        if _slug(h["title"]) == want:
            pick = h
            break
    if not pick:
        for h in hs:
            if want in _slug(h["title"]):
                pick = h
                break
    if not pick:
        return None
    end = len(lines)
    for h in hs:
        if h["line"] > pick["line"] and h["level"] <= pick["level"]:
            end = h["line"]
            break
    return "\n".join(lines[pick["line"]:end])


def page(page_arg: str, sec=None, list_only=False, refresh=False, limit=MAX_CHARS):
    url, text, cached = fetch(page_arg, refresh)
    title = (re.search(r'(?m)^title:\s*"?([^"\n]+)"?', text[:800]) or [None, ""])[1]
    if list_only:
        return {"url": url, "title": title, "cached": cached, "headings": [("  " * (h["level"] - 1)) + h["title"] for h in headings(text)]}
    body = text
    if sec:
        body = section(text, sec)
        if body is None:
            raise util.EngineError("section %r not found in %s; try --list" % (sec, url), 6)
    truncated = len(body) > limit
    return {"url": url, "title": title, "section": sec, "cached": cached, "truncated": truncated, "text": body[:limit]}
