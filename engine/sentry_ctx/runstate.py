"""Run state (.sentry-plugin/run.json): phase, approved org writes, temporary triggers, stop-block counter."""
from __future__ import annotations

import os
import re
import time

from . import paths, util

PHASES = ["preamble", "auditing", "reporting", "approved", "implementing", "verifying", "done"]


def session_marker(root):
    import hashlib
    d = os.path.join(os.path.expanduser("~"), ".cache", "sentry-plugin")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "session-%s.txt" % hashlib.sha1(os.path.abspath(root).encode()).hexdigest()[:16])


def current_session(root):
    """Session id written by the SessionStart hook for this project, if any."""
    try:
        return open(session_marker(root), encoding="utf-8").read().strip() or None
    except OSError:
        return None


def run_path(root):
    return os.path.join(paths.state_dir(root), "run.json")


def load(root):
    return util.read_json(run_path(root))


def save(root, state):
    state["updated_at"] = util.now_iso()
    util.write_json(run_path(root), state)


def start(root, flow: str, units=None):
    if flow not in ("audit", "init", "org", "triage"):
        raise util.EngineError("flow must be audit|init|org|triage")
    run_id = "r-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    state = {
        "run_id": run_id, "flow": flow, "phase": "preamble", "created_at": util.now_iso(), "units": units or [],
        "approved_writes": [], "approved_cli": [], "temp_triggers": [], "stop_blocks": 0, "branch": None, "gitignore": "unasked",
        "session_id": current_session(root),
        "gitignore_added_by_plugin": False,
    }
    os.makedirs(paths.state_dir(root), exist_ok=True)
    save(root, state)
    return state


def require(root):
    st = load(root)
    if not st:
        raise util.EngineError("no active run: start one with `sentry-ctx run start --flow audit|init`")
    return st


def set_phase(root, phase):
    if phase not in PHASES:
        raise util.EngineError("phase must be one of: " + ", ".join(PHASES))
    st = require(root)
    st["phase"] = phase
    save(root, st)
    return st


def adopt(root):
    st = require(root)
    st["session_id"] = current_session(root)
    st["stop_blocks"] = 0
    save(root, st)
    return st


def approve_write(root, method, path_pattern, finding=None, cli=None):
    """Record a user-approved Sentry write. Either a REST call (method + path pattern) or a CLI subcommand ("release create")."""
    st = require(root)
    if cli:
        entry = {"cli": " ".join(cli.split()), "finding": finding, "approved_at": util.now_iso()}
        st.setdefault("approved_cli", []).append(entry)
        save(root, st)
        return entry
    method = method.upper()
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        raise util.EngineError("approve-write is for POST|PUT|PATCH|DELETE")
    entry = {"method": method, "path": path_pattern, "finding": finding, "approved_at": util.now_iso()}
    st["approved_writes"].append(entry)
    save(root, st)
    return entry


def cli_is_approved(state, subcommand: str) -> bool:
    sub = " ".join(subcommand.split())
    return any(sub == w["cli"] or sub.startswith(w["cli"] + " ") for w in (state or {}).get("approved_cli", []))


def write_is_approved(state, method, path) -> bool:
    """path_pattern may contain {placeholders} or * which match one path segment."""
    for w in (state or {}).get("approved_writes", []):
        if w["method"] != method.upper():
            continue
        rx = "^" + re.sub(r"\\\{[^}]+\\\}|\\\*", "[^/]+", re.escape(w["path"].rstrip("/"))) + "/?$"
        if re.match(rx, path.split("?", 1)[0].rstrip("/") or "/"):
            return True
    return False


def trigger(root, action, path=None, kind="file"):
    st = require(root)
    if action == "add":
        rel = util.rel_inside(root, path or "")
        if not rel:
            raise util.EngineError("trigger path must be a relative path inside the repo")
        st["temp_triggers"].append({"path": rel, "kind": kind, "created_at": util.now_iso()})
    elif action == "remove":
        rel = util.rel_inside(root, path or "")
        st["temp_triggers"] = [t for t in st["temp_triggers"] if t["path"] != rel]
    save(root, st)
    return st["temp_triggers"]


def live_triggers(root, st=None):
    st = st or load(root) or {}
    return [t for t in st.get("temp_triggers", []) if os.path.exists(os.path.join(root, t["path"]))]


def gitignore(root, action):
    st = require(root)
    gi = os.path.join(root, ".gitignore")
    line = paths.STATE_DIRNAME + "/"
    if action == "add":
        text = util.read_text(gi) if os.path.isfile(gi) else ""
        if line not in text.splitlines():
            with open(gi, "a", encoding="utf-8") as f:
                if text and not text.endswith("\n"):
                    f.write("\n")
                f.write(line + "\n")
            st["gitignore_added_by_plugin"] = True
        st["gitignore"] = "added"
    elif action == "decline":
        st["gitignore"] = "declined"
    save(root, st)
    return st["gitignore"]
