from __future__ import annotations

import hashlib
import json
import os
import sys


def read_input() -> dict:
    try:
        d = json.loads(sys.stdin.read() or "{}")
        return d if isinstance(d, dict) else {}
    except ValueError:
        return {}


def mode() -> str:
    if os.environ.get("SENTRY_PLUGIN_HOOKS", "on") == "off":
        return "off"
    m = os.environ.get("CLAUDE_PLUGIN_OPTION_HOOK_MODE", "on")
    return m if m in ("on", "quiet", "off") else "on"


def project_dir(inp: dict) -> str:
    from .. import paths
    return paths.project_root(os.environ.get("CLAUDE_PROJECT_DIR") or inp.get("cwd") or os.getcwd())


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def context(event: str, text: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}})


def decide(decision: str, reason: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}})


def _texts(ti: dict):
    out = []
    for k in ("content", "new_string"):
        if isinstance(ti.get(k), str):
            out.append(ti[k])
    for e in ti.get("edits") or []:
        if isinstance(e, dict) and isinstance(e.get("new_string"), str):
            out.append(e["new_string"])
    return out


def written(inp: dict):
    """[(path, [new text, ...])] for a file-writing tool call: Claude's Write/Edit/MultiEdit, or Codex's apply_patch (the patch text arrives in tool_input.command)."""
    ti = inp.get("tool_input") or {}
    cmd = ti.get("command")
    if isinstance(cmd, str) and not ti.get("file_path") and (inp.get("tool_name") == "apply_patch" or "*** Begin Patch" in cmd):
        files, cur = [], None
        for line in cmd.split("\n"):
            for tag in ("*** Add File: ", "*** Update File: ", "*** Move to: "):
                if line.startswith(tag):
                    cur = (line[len(tag):].strip(), [])
                    files.append(cur)
                    break
            else:
                if cur is not None and line.startswith("+"):
                    cur[1].append(line[1:])
        return [(p, ["\n".join(t)]) for p, t in files]
    return [(ti.get("file_path") or "", _texts(ti))]


def cache_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), ".cache", "sentry-plugin")
    os.makedirs(d, exist_ok=True)
    return d


def project_cache(root: str) -> str:
    return os.path.join(cache_dir(), "project-%s.json" % hashlib.sha1(os.path.abspath(root).encode()).hexdigest()[:16])


def _sig(root: str, units: list) -> str:
    h = hashlib.sha1()
    for u in units:
        base = os.path.join(root, u["root"])
        names = list(u.get("manifests", [])) 
        for rel in names:
            p = os.path.join(root, rel)
            try:
                st = os.stat(p)
                h.update(("%s:%d:%d" % (rel, st.st_mtime_ns, st.st_size)).encode())
            except OSError:
                h.update(rel.encode())
        for lf in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "uv.lock", "poetry.lock", "Pipfile.lock", "Package.resolved", "Podfile.lock", "go.sum", "Gemfile.lock", "composer.lock", "Cargo.lock"):
            for d in (base, root):
                p = os.path.join(d, lf)
                if os.path.isfile(p):
                    st = os.stat(p)
                    h.update(("%s:%d:%d" % (p, st.st_mtime_ns, st.st_size)).encode())
    return h.hexdigest()


def load_units(root: str, allow_detect: bool = True):
    """Units (compact detect output) from the per-project cache; refreshed when manifests/lockfiles change."""
    from ..detect import core
    p = project_cache(root)
    try:
        c = json.load(open(p, encoding="utf-8"))
        if c.get("sig") == _sig(root, c["units"]):
            return c["units"]
    except (OSError, ValueError, KeyError):
        pass
    if not allow_detect:
        return None
    det = core.detect(root)
    units = []
    for u in det["units"]:
        units.append({k: u.get(k) for k in ("id", "root", "ecosystem", "framework", "role", "platforms", "manifests", "library")} | {"sentry": {"status": u["sentry"]["status"], "packages": u["sentry"]["packages"], "init_sites": u["sentry"]["init_sites"][:6]}})
    try:
        json.dump({"sig": _sig(root, units), "units": units}, open(p, "w", encoding="utf-8"))
    except OSError:
        pass
    return units
