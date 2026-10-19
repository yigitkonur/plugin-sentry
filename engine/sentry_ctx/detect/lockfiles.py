"""Resolved versions from lockfiles (declared ranges are not trusted for SDK versions)."""
from __future__ import annotations

import json
import os
import re

from . import toml_mini
from .. import util


def _ancestors(unit_dir: str, repo_root: str):
    cur = os.path.abspath(unit_dir)
    root = os.path.abspath(repo_root)
    while True:
        yield cur
        if cur == root or len(cur) <= len(root):
            return
        parent = os.path.dirname(cur)
        if parent == cur:
            return
        cur = parent


def _find(unit_dir, repo_root, names):
    for d in _ancestors(unit_dir, repo_root):
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p):
                return p
    return None


def js(unit_dir, repo_root, wanted):
    out = {}
    rel_unit = os.path.relpath(unit_dir, repo_root).replace(os.sep, "/")
    p = _find(unit_dir, repo_root, ["package-lock.json", "npm-shrinkwrap.json"])
    if p:
        d = util.read_json(p, {}) or {}
        pk = d.get("packages") or {}
        for n in wanted:
            for key in ("%s/node_modules/%s" % (rel_unit, n) if rel_unit != "." else None, "node_modules/%s" % n):
                if key and key in pk and pk[key].get("version"):
                    out[n] = pk[key]["version"]
                    break
        if out:
            return out
    p = _find(unit_dir, repo_root, ["pnpm-lock.yaml"])
    if p:
        text = util.read_text(p, 8_000_000)
        scope = text
        m = re.search(r"(?m)^importers:\s*$", text)
        if m:
            imp = text[m.end():]
            key = "." if rel_unit == "." else rel_unit
            sm = re.search(r"(?m)^  '?%s'?:\s*$" % re.escape(key), imp)
            if sm:
                rest = imp[sm.end():]
                nx = re.search(r"(?m)^  \S", rest)
                scope = rest[:nx.start()] if nx else rest
        for n in wanted:
            mm = re.search(r"(?m)^\s+'?%s'?:\s*\n\s+specifier:[^\n]*\n\s+version:\s*['\"]?([0-9][^\s('\"]*)" % re.escape(n), scope)
            if not mm:
                mm = re.search(r"(?m)^\s+'?%s'?:\s+['\"]?([0-9][^\s('\"]*)" % re.escape(n), scope)
            if not mm:
                mm = re.search(r"(?m)^\s*'?/?%s@([0-9][^\s('\":]*)" % re.escape(n), text)
            if mm:
                out[n] = mm.group(1)
        if out:
            return out
    p = _find(unit_dir, repo_root, ["yarn.lock"])
    if p:
        text = util.read_text(p, 8_000_000)
        for n in wanted:
            mm = re.search(r'(?ms)^"?%s@[^\n]*:\n(?:[ ]+[^\n]*\n)*?[ ]+version:?\s+"?([0-9][^"\n]*)"?' % re.escape(n), text)
            if mm:
                out[n] = mm.group(1)
        if out:
            return out
    p = _find(unit_dir, repo_root, ["bun.lock"])
    if p:
        text = util.read_text(p, 8_000_000)
        for n in wanted:
            mm = re.search(r'"%s":\s*\["%s@([0-9][^"]*)"' % (re.escape(n), re.escape(n)), text)
            if mm:
                out[n] = mm.group(1)
    return out


def python(unit_dir, repo_root, wanted):
    out = {}
    for lock in ("uv.lock", "poetry.lock", "pdm.lock"):
        p = _find(unit_dir, repo_root, [lock])
        if p:
            d = toml_mini.loads(util.read_text(p, 8_000_000))
            for pkg in d.get("package", []) or []:
                nm = re.sub(r"[-_.]+", "-", str(pkg.get("name", ""))).lower()
                if nm in wanted and pkg.get("version"):
                    out[nm] = str(pkg["version"])
            if out:
                return out
    p = _find(unit_dir, repo_root, ["Pipfile.lock"])
    if p:
        d = util.read_json(p, {}) or {}
        for sec in ("default", "develop"):
            for k, v in (d.get(sec) or {}).items():
                nm = re.sub(r"[-_.]+", "-", k).lower()
                if nm in wanted and isinstance(v, dict) and v.get("version"):
                    out[nm] = v["version"].lstrip("=")
    for fn in ("requirements.txt", "requirements.lock"):
        p = _find(unit_dir, repo_root, [fn])
        if p:
            for line in util.read_text(p).splitlines():
                m = re.match(r"^([A-Za-z0-9._-]+)(?:\[[^\]]*\])?==([0-9][^\s;#]*)", line.strip())
                if m:
                    nm = re.sub(r"[-_.]+", "-", m.group(1)).lower()
                    if nm in wanted:
                        out.setdefault(nm, m.group(2))
    return out


def ruby(unit_dir, repo_root, wanted):
    p = _find(unit_dir, repo_root, ["Gemfile.lock"])
    out = {}
    if p:
        text = util.read_text(p)
        for n in wanted:
            m = re.search(r"(?m)^    %s \(([0-9][^)]*)\)" % re.escape(n), text)
            if m:
                out[n] = m.group(1)
    return out


def php(unit_dir, repo_root, wanted):
    p = _find(unit_dir, repo_root, ["composer.lock"])
    out = {}
    if p:
        d = util.read_json(p, {}) or {}
        for pkg in (d.get("packages") or []) + (d.get("packages-dev") or []):
            if pkg.get("name") in wanted:
                out[pkg["name"]] = str(pkg.get("version", "")).lstrip("v")
    return out


def rust(unit_dir, repo_root, wanted):
    p = _find(unit_dir, repo_root, ["Cargo.lock"])
    out = {}
    if p:
        d = toml_mini.loads(util.read_text(p, 8_000_000))
        for pkg in d.get("package", []) or []:
            if pkg.get("name") in wanted:
                out.setdefault(pkg["name"], str(pkg.get("version", "")))
    return out


def elixir(unit_dir, repo_root, wanted):
    p = _find(unit_dir, repo_root, ["mix.lock"])
    out = {}
    if p:
        text = util.read_text(p)
        for n in wanted:
            m = re.search(r'"%s":\s*\{:hex,\s*:%s,\s*"([^"]+)"' % (re.escape(n.lstrip(":")), re.escape(n.lstrip(":"))), text)
            if m:
                out[n] = m.group(1)
    return out


def dart(unit_dir, repo_root, wanted):
    p = _find(unit_dir, repo_root, ["pubspec.lock"])
    out = {}
    if p:
        text = util.read_text(p)
        for n in wanted:
            m = re.search(r'(?m)^  %s:\n(?:    .*\n)*?    version:\s*"([^"]+)"' % re.escape(n), text)
            if m:
                out[n] = m.group(1)
    return out


def apple(unit_dir, repo_root, wanted):
    out = {}
    cands = []
    for root, dirs, files in os.walk(unit_dir):
        dirs[:] = [d for d in dirs if d not in util.PRUNE_DIRS or d.endswith(".xcodeproj")]
        depth = os.path.relpath(root, unit_dir).count(os.sep)
        if depth > 5:
            dirs[:] = []
        if "Package.resolved" in files:
            cands.append(os.path.join(root, "Package.resolved"))
    p = _find(unit_dir, repo_root, ["Package.resolved"])
    if p:
        cands.append(p)
    for c in cands:
        d = util.read_json(c, {}) or {}
        pins = d.get("pins") or (d.get("object") or {}).get("pins") or []
        for pin in pins:
            ident = (pin.get("identity") or pin.get("package") or "").lower()
            st = pin.get("state") or {}
            ver = st.get("version") or st.get("revision", "")[:8]
            for n in wanted:
                if ident == n.lower() and ver:
                    out.setdefault(n, ver)
        if out:
            return out
    p = _find(unit_dir, repo_root, ["Podfile.lock"])
    if p:
        text = util.read_text(p)
        for n in wanted:
            m = re.search(r"(?m)^  - %s(?:/\w+)? \(([0-9][^)]*)\)" % re.escape(n), text)
            if m:
                out[n] = m.group(1)
    return out


def dotnet(unit_dir, repo_root, wanted):
    out = {}
    p = _find(unit_dir, repo_root, ["packages.lock.json"])
    if p:
        d = util.read_json(p, {}) or {}
        for fw in (d.get("dependencies") or {}).values():
            for n, v in fw.items():
                if n in wanted and v.get("resolved"):
                    out.setdefault(n, v["resolved"])
    return out


RESOLVERS = {"js": js, "python": python, "ruby": ruby, "php": php, "rust": rust, "elixir": elixir, "dart": dart, "apple": apple, "dotnet": dotnet}


def resolve(ecosystem, unit_dir, repo_root, wanted):
    fn = RESOLVERS.get(ecosystem)
    if not fn or not wanted:
        return {}
    try:
        return fn(unit_dir, repo_root, list(wanted))
    except Exception:  # a malformed lockfile must never break detection
        return {}
