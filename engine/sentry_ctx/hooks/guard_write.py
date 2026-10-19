"""H2: deny writing a Sentry credential into a file git would track."""
from __future__ import annotations

import os

from .. import tokens, util
from . import common


def _texts(ti: dict):
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
    if common.mode() == "off":
        return
    ti = inp.get("tool_input") or {}
    root = common.project_dir(inp)
    path = ti.get("file_path") or ""
    # the plugin's own artifacts are masked by the engine; fixtures use placeholders
    if inp.get("agent_type") == "sentry:auditor":
        common.decide("deny", "The auditor is read-only; it records findings with `sentry-ctx finding add`, not by editing files.")
        return
    if not any(tokens.has_token(t) for t in _texts(ti)):
        return
    rel = os.path.relpath(path, root) if os.path.isabs(path) else path
    ignored = False
    if rel and not rel.startswith(".."):
        rc, _, _ = util.git(root, "check-ignore", "-q", rel)
        ignored = rc == 0
    if ignored:
        return
    common.decide("deny", (
        "This write puts a Sentry credential-shaped string (sntryu_/sntrys_ token or SENTRY_AUTH_TOKEN value) into %s, which git would track. "
        "Use a CI secret or an environment variable, or write it to a gitignored file (.env.sentry-build-plugin, .sentryclirc: add it to .gitignore first). "
        "The DSN is public and is not blocked." % (rel or "a file")))
