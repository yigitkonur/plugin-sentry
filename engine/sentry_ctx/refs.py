"""Reference files: forge layer (ours) and upstream layer (vendored from getsentry/sentry-for-ai, attributed in NOTICE)."""
from __future__ import annotations

import os
import re

from . import docs, paths, util

LAYERS = ["forge", "upstream", ""]


def _resolve(name: str):
    name = name.strip().strip("/")
    if name.endswith(".md"):
        name = name[:-3]
    if ".." in name.split("/"):
        raise util.EngineError("invalid reference name")
    for layer in LAYERS:
        p = os.path.join(paths.ref_root(), layer, name + ".md") if layer else os.path.join(paths.ref_root(), name + ".md")
        if os.path.isfile(p):
            return p
    return None


def list_names(prefix: str = ""):
    out = []
    base = paths.ref_root()
    for dp, dn, fn in os.walk(base):
        for f in sorted(fn):
            if f.endswith(".md"):
                rel = os.path.relpath(os.path.join(dp, f), base)[:-3]
                out.append(rel)
    out.sort()
    return [n for n in out if n.startswith(prefix)]


def read(name: str, sec=None):
    p = _resolve(name)
    if not p:
        near = [n for n in list_names() if os.path.basename(name) in n][:8]
        raise util.EngineError("no reference named %r%s" % (name, ("; similar: " + ", ".join(near)) if near else ""), 6)
    text = util.read_text(p, 400_000)
    if sec:
        s = docs.section(text, sec)
        if s is None:
            raise util.EngineError("section %r not found in %s" % (sec, name), 6)
        return s
    return text


def flow(name: str):
    p = os.path.join(paths.ref_root(), "forge", "flows", name + ".md")
    if not os.path.isfile(p):
        raise util.EngineError("no flow named %r (have: %s)" % (name, ", ".join(sorted(f[:-3] for f in os.listdir(os.path.dirname(p)) if f.endswith(".md"))) if os.path.isdir(os.path.dirname(p)) else "none"), 6)
    return util.read_text(p, 200_000)
