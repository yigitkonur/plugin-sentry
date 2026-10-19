from __future__ import annotations

import json
import os

STATE_DIRNAME = ".sentry-plugin"


def plugin_root() -> str:
    root = os.environ.get("SENTRY_PLUGIN_ROOT") or os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        return os.path.abspath(root)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def data_path(*parts: str) -> str:
    return os.path.join(plugin_root(), "data", *parts)


def ref_root() -> str:
    return os.path.join(plugin_root(), "references")


def plugin_version() -> str:
    try:
        with open(os.path.join(plugin_root(), ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            return json.load(f).get("version", "0.0.0")
    except (OSError, ValueError):
        return "0.0.0"


def cache_dir() -> str:
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(os.path.expanduser("~"), ".cache", "sentry-plugin")
    os.makedirs(base, exist_ok=True)
    return base


def project_root(start: str | None = None) -> str:
    """Directory the user is working in: CLAUDE_PROJECT_DIR, else git toplevel, else cwd."""
    if start is None:
        start = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    cur = os.path.abspath(start)
    probe = cur
    while True:
        if os.path.exists(os.path.join(probe, ".git")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            return cur
        probe = parent


def state_dir(root: str | None = None) -> str:
    return os.path.join(root or project_root(), STATE_DIRNAME)


def load_json_data(*parts: str):
    with open(data_path(*parts), encoding="utf-8") as f:
        return json.load(f)
