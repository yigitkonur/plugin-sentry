"""Run state (.sentry-plugin/run.json): phase, approved org writes, temporary triggers, stop-block counter."""
from __future__ import annotations

import hashlib
import json
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
    """Claim an existing run for this session. Approvals recorded by an earlier session do not carry over: the user decides again."""
    st = require(root)
    st["session_id"] = current_session(root)
    st["stop_blocks"] = 0
    st["approved_writes"], st["approved_cli"] = [], []
    save(root, st)
    return st


def _norm_cli(cmd: str) -> str:
    words = " ".join((cmd or "").split()).split(" ")
    if words and words[0] == "sentry":
        words = words[1:]
    return " ".join(w for w in words if w not in ("--dry-run", "-n", "--json", "--yes"))


def fingerprint(org_write: dict) -> str:
    """Stable hash of the exact operation a finding asks for: method + path + body, or the CLI command line."""
    if org_write.get("cli"):
        basis = {"cli": _norm_cli(org_write["cli"])}
    else:
        basis = {"method": str(org_write.get("method", "")).upper(), "path": re.sub(r"^/api/0(?=/)", "", org_write.get("path", "")).rstrip("/"), "body": org_write.get("body")}
    return hashlib.sha256(json.dumps(basis, sort_keys=True).encode()).hexdigest()[:20]


def _finding_org_write(root, finding_id):
    from . import findings
    p = findings.find_path(root, finding_id)
    if not p:
        raise util.EngineError("no such finding: %s" % finding_id)
    fm, _ = findings._load_file(p)
    return fm


def approve_write(root, method, path_pattern, finding=None, cli=None):
    """Record a user-approved Sentry write for THIS run and session. Either a REST call (method + exact path) or a CLI command.
    With --finding the approval is bound to the exact operation that finding holds (a hash of method+path+body, or the CLI line):
    changing the finding afterwards voids it. A CLI approval of two words or fewer ("sourcemap upload") covers that subcommand class;
    a longer one covers exactly that command line."""
    st = require(root)
    fp = None
    if finding:
        fm = _finding_org_write(root, finding)
        ow = fm.get("org_write")
        if fm.get("kind") == "org-write" and isinstance(ow, dict):
            if cli and not ow.get("cli"):
                raise util.EngineError("%s holds a REST call, not a CLI command" % finding)
            if not cli and ow.get("cli"):
                raise util.EngineError("%s holds a CLI command; approve it with --cli" % finding)
            if cli and not _norm_cli(ow["cli"]).startswith(_norm_cli(cli)):
                raise util.EngineError("the approved command %r does not match the one in %s (%s)" % (cli, finding, ow["cli"]))
            if not cli and (str(ow.get("method", "")).upper() != method.upper() or re.sub(r"^/api/0(?=/)", "", ow.get("path", "")).rstrip("/") != re.sub(r"^/api/0(?=/)", "", path_pattern or "").rstrip("/")):
                raise util.EngineError("the approved call %s %s does not match the one in %s (%s %s)" % (method, path_pattern, finding, ow.get("method"), ow.get("path")))
            fp = fingerprint(ow)
    base = {"finding": finding, "fingerprint": fp, "run_id": st.get("run_id"), "session_id": current_session(root), "approved_at": util.now_iso()}
    if cli:
        entry = dict(base, cli=_norm_cli(cli))
        st.setdefault("approved_cli", []).append(entry)
        save(root, st)
        return entry
    method = method.upper()
    path_pattern = re.sub(r"^/api/0(?=/)", "", path_pattern or "").split("?", 1)[0].rstrip("/") or "/"
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        raise util.EngineError("approve-write is for POST|PUT|PATCH|DELETE")
    entry = dict(base, method=method, path=path_pattern)
    st["approved_writes"].append(entry)
    save(root, st)
    return entry


def _live(state, entry, session_id=None):
    """An approval counts only inside the active run (not done) and the session that recorded it."""
    if not state or state.get("phase") in (None, "done"):
        return False
    if entry.get("run_id") and entry["run_id"] != state.get("run_id"):
        return False
    if session_id and entry.get("session_id") and entry["session_id"] != session_id:
        return False
    return True


def cli_is_approved(state, subcommand: str, session_id=None) -> bool:
    """`subcommand` is the normalized command line after `sentry` (no --dry-run/--json). Class approvals (<=2 words) cover the subcommand;
    longer approvals must equal the command line exactly."""
    cmd = _norm_cli(subcommand)
    for w in (state or {}).get("approved_cli", []):
        if not _live(state, w, session_id):
            continue
        ap = _norm_cli(w["cli"])
        if len(ap.split()) <= 2:
            if cmd == ap or cmd.startswith(ap + " "):
                return True
        elif cmd == ap:
            return True
    return False


def cli_approved_for(state, subcommand: str, finding_id: str, session_id=None, ow=None) -> bool:
    """For `org apply`: the approval must be recorded for this finding (or be a run-wide class approval) and, when it carries a fingerprint, the finding's operation must be unchanged."""
    cmd = _norm_cli(subcommand)
    for w in (state or {}).get("approved_cli", []):
        if not _live(state, w, session_id):
            continue
        if w.get("finding") not in (None, "", finding_id):
            continue
        if w.get("fingerprint") and ow is not None and w["fingerprint"] != fingerprint(ow):
            continue
        ap = _norm_cli(w["cli"])
        if (len(ap.split()) <= 2 and (cmd == ap or cmd.startswith(ap + " "))) or cmd == ap or cmd.startswith(ap + " "):
            return True
    return False


def write_is_approved(state, method, path, session_id=None, finding_id=None, ow=None) -> bool:
    """Exact method and path (no wildcards). With a finding, the approval must be that finding's and its operation unchanged."""
    want = re.sub(r"^/api/0(?=/)", "", path or "").split("?", 1)[0].rstrip("/") or "/"
    for w in (state or {}).get("approved_writes", []):
        if not _live(state, w, session_id) or w["method"] != method.upper():
            continue
        if w["path"] != want:
            continue
        if finding_id is not None:
            if w.get("finding") not in (None, "", finding_id):
                continue
            if w.get("fingerprint") and ow is not None and w["fingerprint"] != fingerprint(ow):
                continue
        return True
    return False


def trigger(root, action, path=None, kind="file"):
    """Temporary trigger files. Register the path BEFORE creating it: only a file that did not exist at registration can ever be deleted by cleanup."""
    st = require(root)
    rel = util.rel_inside(root, path or "")
    if action == "add":
        if not rel or rel in (".", "") or os.path.normpath(rel) in (".", ".."):
            raise util.EngineError("trigger path must name one new file inside the repo, not the repo root or a directory")
        top = os.path.normpath(rel).split(os.sep)[0]
        if top in (".git", paths.STATE_DIRNAME):
            raise util.EngineError("trigger path may not be inside .git or %s" % paths.STATE_DIRNAME)
        ap = os.path.join(root, rel)
        if os.path.lexists(ap):
            raise util.EngineError("%s already exists: register a trigger path before creating the file (an existing file is never a trigger)" % rel)
        if util.is_git_repo(root):
            rc, _, _ = util.git(root, "ls-files", "--error-unmatch", "--", rel)
            if rc == 0:
                raise util.EngineError("%s is tracked by git: a tracked file is not a temporary trigger" % rel)
        st["temp_triggers"].append({"path": rel, "kind": "file", "created_at": util.now_iso()})
    elif action == "remove":
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
