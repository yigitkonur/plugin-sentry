"""A tiny YAML subset for front matter the engine itself writes and reads.

Supported: `key: scalar`, `key: [a, b]`, `key: { a: b, c: [d] }`, block maps (2-space indent),
block lists (`- item`), quoted strings ("..." with JSON escapes, '...'), null/true/false, ints, floats,
`#` comments on their own line. Emission uses flow style for collections, one top-level key per line.
"""
from __future__ import annotations

import json
import re

_PLAIN_OK = re.compile(r"^[A-Za-z0-9_./@%+~*()<>=|\-][A-Za-z0-9_./@%+~*()<>=|\- ]*$")
_RESERVED = {"null", "true", "false", "~", ""}
_NUM = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def _scalar_out(v) -> str:
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    if "\n" in s or s.lower() in _RESERVED or _NUM.match(s) or not _PLAIN_OK.match(s) or s != s.strip() or s.endswith(":"):
        return json.dumps(s, ensure_ascii=False)
    return s


def flow(v) -> str:
    if isinstance(v, dict):
        if not v:
            return "{}"
        return "{ " + ", ".join("%s: %s" % (_key_out(k), flow(x)) for k, x in v.items()) + " }"
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(flow(x) for x in v) + "]"
    return _scalar_out(v)


def _key_out(k) -> str:
    k = str(k)
    return k if re.match(r"^[A-Za-z0-9_.\-]+$", k) else json.dumps(k)


def dumps(d: dict) -> str:
    return "".join("%s: %s\n" % (_key_out(k), flow(v)) for k, v in d.items())


# ---------- parsing ----------

class _P:
    def __init__(self, s: str):
        self.s, self.i = s, 0

    def ws(self):
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def parse(self):
        self.ws()
        c = self.s[self.i] if self.i < len(self.s) else ""
        if c == "[":
            return self.list_()
        if c == "{":
            return self.map_()
        return self.scalar(stops="")

    def list_(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.i >= len(self.s):
                raise ValueError("unterminated list")
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.item(",]"))
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ",":
                self.i += 1

    def map_(self):
        self.i += 1
        out = {}
        while True:
            self.ws()
            if self.i >= len(self.s):
                raise ValueError("unterminated map")
            if self.s[self.i] == "}":
                self.i += 1
                return out
            key = self.scalar(stops=":,}")
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ":":
                self.i += 1
                self.ws()
                out[str(key)] = self.item(",}")
            else:
                out[str(key)] = None
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ",":
                self.i += 1

    def item(self, stops):
        self.ws()
        c = self.s[self.i] if self.i < len(self.s) else ""
        if c == "[":
            return self.list_()
        if c == "{":
            return self.map_()
        return self.scalar(stops=stops)

    def scalar(self, stops):
        self.ws()
        if self.i < len(self.s) and self.s[self.i] == '"':
            j = self.i + 1
            while j < len(self.s):
                if self.s[j] == "\\":
                    j += 2
                    continue
                if self.s[j] == '"':
                    break
                j += 1
            val = json.loads(self.s[self.i:j + 1])
            self.i = j + 1
            return val
        if self.i < len(self.s) and self.s[self.i] == "'":
            j = self.s.index("'", self.i + 1)
            val = self.s[self.i + 1:j]
            self.i = j + 1
            return val
        j = self.i
        while j < len(self.s) and self.s[j] not in stops:
            j += 1
        raw = self.s[self.i:j].strip()
        self.i = j
        return _typed(raw)


def _typed(raw: str):
    low = raw.lower()
    if low in ("null", "~", ""):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if _NUM.match(raw):
        return float(raw) if ("." in raw or "e" in low) else int(raw)
    return raw


def parse_value(text: str):
    p = _P(text.strip())
    return p.parse()


def loads(text: str) -> dict:
    """Parse a mapping. Block maps/lists are nested by 2-space indentation."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    val, _ = _block(lines, 0, 0)
    return val if isinstance(val, dict) else {}


def _indent(ln: str) -> int:
    return len(ln) - len(ln.lstrip(" "))


def _block(lines, idx, indent):
    if idx < len(lines) and lines[idx].lstrip().startswith("- "):
        out = []
        while idx < len(lines) and _indent(lines[idx]) == indent and lines[idx].lstrip().startswith("- "):
            out.append(parse_value(lines[idx].lstrip()[2:]))
            idx += 1
        return out, idx
    out = {}
    while idx < len(lines):
        ln = lines[idx]
        ind = _indent(ln)
        if ind < indent:
            break
        if ind > indent:
            idx += 1
            continue
        body = ln.strip()
        key, sep, rest = body.partition(":")
        if not sep:
            idx += 1
            continue
        key = key.strip().strip('"')
        rest = rest.strip()
        idx += 1
        if rest == "":
            if idx < len(lines) and _indent(lines[idx]) > indent:
                child, idx = _block(lines, idx, _indent(lines[idx]))
                out[key] = child
            else:
                out[key] = None
        else:
            out[key] = parse_value(rest)
    return out, idx


def split_front_matter(text: str):
    """Return (front_matter_dict, body). No front matter -> ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm = text[3:end].lstrip("\n")
    body = text[end + 4:].lstrip("\n")
    return loads(fm), body


def join_front_matter(fm: dict, body: str) -> str:
    return "---\n" + dumps(fm) + "---\n" + body
