"""H2: deny writing a Sentry credential into a file git would track."""
from __future__ import annotations

import os

from .. import tokens, util
from . import common


def run():
    inp = common.read_input()
    if common.mode() == "off":
        return
    root = common.project_dir(inp)
    # the plugin's own artifacts are masked by the engine; fixtures use placeholders
    if inp.get("agent_type") == "sentry:auditor":
        common.decide("deny", "The auditor is read-only; it records findings with `sentry-ctx finding add`, not by editing files.")
        return
    for path, texts in common.written(inp):
        if _check(path, texts, root):
            return


def _check(path: str, texts: list, root: str) -> bool:
    """Decide for one written file; True once a decision was emitted."""
    # the run state holds the user's approvals: only `sentry-ctx run approve-write` (which asks) may change it
    if path and os.path.basename(path) == "run.json" and os.path.basename(os.path.dirname(path)) == ".sentry-plugin":
        common.decide("deny", "The run state (.sentry-plugin/run.json) holds the user's approvals and is written only by `sentry-ctx`. Use `sentry-ctx run ...` commands.")
        return True
    # the plugin's own files (engine, references, data, hooks) are never edited by a run in a user's repo; engine bugs are reported
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root and path and not os.environ.get("SENTRY_PLUGIN_DEV"):
        try:
            ap = os.path.realpath(path if os.path.isabs(path) else os.path.join(root, path))
            pr = os.path.realpath(plugin_root)
            if ap == pr or ap.startswith(pr + os.sep):
                common.decide("deny", "That file belongs to the sentry plugin itself (%s). A run never edits the plugin: if `sentry-ctx` misbehaves, stop and report the exact command and its output to the user." % os.path.relpath(ap, pr))
                return True
        except OSError:
            pass
    if not any(tokens.has_token(t) for t in texts):
        return False
    rel = os.path.relpath(path, root) if os.path.isabs(path) else path
    ignored = False
    if rel and not rel.startswith(".."):
        rc, _, _ = util.git(root, "check-ignore", "-q", rel)
        ignored = rc == 0
    if ignored:
        return False
    common.decide("deny", (
        "This write puts a Sentry credential-shaped string (sntryu_/sntrys_ token or SENTRY_AUTH_TOKEN value) into %s, which git would track. "
        "Do this instead: (1) add %s to .gitignore, (2) repeat this write; it is allowed once `git check-ignore -v %s` prints a rule. "
        "In CI use a secret or an environment variable. The DSN is public and is not blocked." % (rel or "a file", rel or "the file", rel or "the file")))
    return True
