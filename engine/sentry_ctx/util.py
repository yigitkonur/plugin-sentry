from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from . import tokens

PRUNE_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", ".next", ".nuxt", ".output", "DerivedData", "Pods",
    "Carthage", ".build", ".venv", "venv", "env", "target", "__pycache__", ".gradle", ".idea", ".turbo",
    ".cache", ".parcel-cache", "coverage", ".svelte-kit", ".expo", ".dart_tool", ".pytest_cache",
    ".mypy_cache", ".tox", "bower_components", ".sentry-plugin", ".terraform", ".serverless", "out",
}
MAX_FILE_BYTES = 1_000_000


class EngineError(Exception):
    """A user-facing failure: message to stderr, exit code 2."""

    def __init__(self, msg: str, code: int = 2):
        super().__init__(msg)
        self.code = code


def emit(obj, as_json: bool = True) -> None:
    obj = tokens.mask_deep(obj)
    if as_json:
        sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n")
    else:
        sys.stdout.write(str(obj) + "\n")


def read_text(path: str, limit: int = MAX_FILE_BYTES) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read(limit + 1)
    except OSError:
        return ""
    if len(data) > limit:
        data = data[:limit]
    return data.decode("utf-8", errors="replace")


def read_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tokens.mask_deep(obj), f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(tokens.mask(text))
    os.replace(tmp, path)


def run(cmd, cwd=None, timeout=30, env=None, input_text=None):
    """Run a command; return (returncode, stdout, stderr). Never raises on non-zero."""
    try:
        p = subprocess.run(
            cmd, cwd=cwd, env=env, input=input_text, capture_output=True, text=True, timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "command not found: %s" % (cmd[0] if cmd else "")
    except subprocess.TimeoutExpired:
        return 124, "", "timeout after %ss" % timeout


def git(root: str, *args, timeout=30):
    return run(["git", "-C", root, *args], timeout=timeout)


def is_git_repo(root: str) -> bool:
    rc, out, _ = git(root, "rev-parse", "--is-inside-work-tree")
    return rc == 0 and out.strip() == "true"


def git_files(root: str):
    """Tracked + untracked-not-ignored files, relative paths. None when not a git repo."""
    rc, out, _ = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", timeout=60)
    if rc != 0:
        return None
    return [p for p in out.split("\0") if p]


def walk_files(root: str, max_files: int = 60000):
    """Bounded walk honoring PRUNE_DIRS. Returns (relative paths, truncated)."""
    out = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS and not os.path.islink(os.path.join(dirpath, d))]
        for fn in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, fn), root))
            if len(out) >= max_files:
                return out, True
    return out, truncated


def list_repo_files(root: str):
    """(files, truncated, source). Uses git when possible, then drops pruned dirs."""
    files = git_files(root)
    if files is not None:
        kept = []
        for p in files:
            parts = p.split("/")
            if any(seg in PRUNE_DIRS for seg in parts[:-1]):
                continue
            if os.path.islink(os.path.join(root, p)):
                continue
            kept.append(p)
        if len(kept) > 80000:
            return kept[:80000], True, "git"
        return kept, False, "git"
    files, truncated = walk_files(root)
    return files, truncated, "walk"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel_inside(root: str, path: str):
    """Return the normalized relative path if `path` stays inside root, else None."""
    if not path or os.path.isabs(path):
        return None
    norm = os.path.normpath(path)
    if norm.startswith("..") or norm == "..":
        return None
    full = os.path.realpath(os.path.join(root, norm))
    if os.path.commonpath([os.path.realpath(root), full]) != os.path.realpath(root):
        return None
    return norm
