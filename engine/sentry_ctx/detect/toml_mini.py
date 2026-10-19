"""A tolerant TOML subset reader (tables, arrays of tables, strings, numbers, bools, arrays, inline tables).

Used for pyproject.toml, Cargo.toml, uv.lock, poetry.lock, Pipfile, libs.versions.toml, wrangler.toml on every
supported Python (tomllib only exists from 3.11). Anything it cannot parse is skipped instead of raising.
"""
from __future__ import annotations

import re


class _V:
    def __init__(self, s):
        self.s, self.i = s, 0

    def ws(self, newlines=True):
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c in " \t" or (newlines and c in "\r\n"):
                self.i += 1
            elif c == "#" and newlines:
                while self.i < len(s) and s[self.i] != "\n":
                    self.i += 1
            else:
                break

    def value(self):
        self.ws(False)
        s = self.s
        c = s[self.i] if self.i < len(s) else ""
        if c == '"' or c == "'":
            return self.string()
        if c == "[":
            return self.array()
        if c == "{":
            return self.inline()
        j = self.i
        while j < len(s) and s[j] not in ",]}\n#":
            j += 1
        raw = s[self.i:j].strip()
        self.i = j
        if raw == "true":
            return True
        if raw == "false":
            return False
        try:
            return int(raw.replace("_", ""))
        except ValueError:
            try:
                return float(raw.replace("_", ""))
            except ValueError:
                return raw

    def string(self):
        s = self.s
        q = s[self.i]
        if s.startswith(q * 3, self.i):
            end = s.find(q * 3, self.i + 3)
            end = len(s) if end == -1 else end
            val = s[self.i + 3:end]
            self.i = min(len(s), end + 3)
            return val
        j = self.i + 1
        out = []
        while j < len(s) and s[j] != q and s[j] != "\n":
            if q == '"' and s[j] == "\\" and j + 1 < len(s):
                out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(s[j + 1], s[j + 1]))
                j += 2
                continue
            out.append(s[j])
            j += 1
        self.i = j + 1
        return "".join(out)

    def array(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.i >= len(self.s):
                return out
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ",":
                self.i += 1

    def inline(self):
        self.i += 1
        out = {}
        while True:
            self.ws()
            if self.i >= len(self.s):
                return out
            if self.s[self.i] == "}":
                self.i += 1
                return out
            key = self.key()
            self.ws(False)
            if self.i < len(self.s) and self.s[self.i] == "=":
                self.i += 1
            _set(out, key, self.value())
            self.ws()
            if self.i < len(self.s) and self.s[self.i] == ",":
                self.i += 1

    def key(self):
        parts = []
        while True:
            self.ws(False)
            if self.i < len(self.s) and self.s[self.i] in "\"'":
                parts.append(self.string())
            else:
                j = self.i
                while j < len(self.s) and re.match(r"[A-Za-z0-9_\-]", self.s[j]):
                    j += 1
                if j == self.i:
                    break
                parts.append(self.s[self.i:j])
                self.i = j
            self.ws(False)
            if self.i < len(self.s) and self.s[self.i] == ".":
                self.i += 1
                continue
            break
        return parts


def _set(d, key, val):
    cur = d
    for k in key[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    if key:
        cur[key[-1]] = val


def loads(text: str) -> dict:
    root: dict = {}
    cur = root
    v = _V(text)
    s = text
    n = len(s)
    while True:
        v.ws()
        if v.i >= n:
            break
        c = s[v.i]
        try:
            if c == "[":
                is_arr = s.startswith("[[", v.i)
                v.i += 2 if is_arr else 1
                key = v.key()
                v.ws(False)
                v.i = s.find("]", v.i) + (2 if is_arr else 1) if s.find("]", v.i) != -1 else n
                if is_arr:
                    parent = root
                    for k in key[:-1]:
                        parent = parent.setdefault(k, {})
                        if isinstance(parent, list):
                            parent = parent[-1]
                    lst = parent.setdefault(key[-1], [])
                    lst.append({})
                    cur = lst[-1]
                else:
                    cur = root
                    for k in key:
                        nxt = cur.setdefault(k, {})
                        if isinstance(nxt, list):
                            nxt = nxt[-1]
                        cur = nxt
            else:
                key = v.key()
                v.ws(False)
                if not key or v.i >= n or s[v.i] != "=":
                    nl = s.find("\n", v.i)
                    v.i = n if nl == -1 else nl + 1
                    continue
                v.i += 1
                _set(cur, key, v.value())
                nl = s.find("\n", v.i)
                # skip trailing comment / rest of the line
                rest_end = n if nl == -1 else nl
                v.i = max(v.i, 0)
                while v.i < rest_end and s[v.i] in " \t":
                    v.i += 1
                if v.i < rest_end and s[v.i] == "#":
                    v.i = rest_end
        except (IndexError, ValueError, TypeError, AttributeError):
            nl = s.find("\n", v.i)
            v.i = n if nl == -1 else nl + 1
    return root
