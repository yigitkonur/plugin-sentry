from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys

from . import cli_tools, paths, util

INSTALL_V4 = "curl https://cli.sentry.dev/install -fsS | bash   (or: npm install -g sentry, or: brew install getsentry/tools/sentry)"
LOGIN_RO = "sentry auth login --read-only"
LOGIN = "sentry auth login"
TOKEN_ENV_NAMES = ["SENTRY_AUTH_TOKEN", "SENTRY_TOKEN", "SENTRY_API_KEY"]
WRITE_SCOPES = {"project:write", "alerts:write", "project:admin", "org:write", "event:write"}
# Scopes the default OAuth login does not carry (spike S1) and what needs them.
NOT_IN_DEFAULT = {
    "org:write": "organization-level settings (org data scrubbing, Seer defaults, sampling mode)",
    "org:ci": "organization auth tokens (CI uploads)",
    "project:releases": "token-only release creation (the OAuth login can still create releases and upload source maps)",
    "member:write": "member administration",
}


def _installed_plugins():
    names = set()
    data = util.read_json(os.path.expanduser("~/.claude/plugins/installed_plugins.json"), {}) or {}
    plugins = data.get("plugins", data) if isinstance(data, dict) else {}
    if isinstance(plugins, dict):
        names |= set(plugins.keys())
    for p in (os.path.expanduser("~/.claude/settings.json"),):
        s = util.read_json(p, {}) or {}
        names |= set((s.get("enabledPlugins") or {}).keys()) if isinstance(s, dict) else set()
    return names


def coexistence():
    names = _installed_plugins()
    official = sorted(n for n in names if n.startswith("sentry@") and not n.endswith("@plugin-sentry"))
    official_cli = sorted(n for n in names if n.startswith("sentry-cli@"))
    return {
        "official_sentry_plugin": official,
        "official_sentry_cli_plugin": official_cli,
        "note": (
            "The official Sentry plugin is also named 'sentry', so both share the /sentry:* namespace. "
            "Skill names here are bare verbs (audit, init, ...) and never collide with its sentry-* skills."
            if official else None
        ),
    }


def git_info(root: str):
    if not util.is_git_repo(root):
        return {"repo": False}
    rc, out, _ = util.git(root, "status", "--porcelain")
    _, branch, _ = util.git(root, "rev-parse", "--abbrev-ref", "HEAD")
    return {"repo": True, "dirty": bool(out.strip()), "branch": branch.strip()}


def run(root: str, want_auth: bool = True) -> dict:
    v4 = cli_tools.sentry_v4()
    v3 = cli_tools.sentry_cli_v3()
    node = shutil.which("node")
    npx = shutil.which("npx")
    node_v = None
    if node:
        rc, out, _ = util.run([node, "--version"], timeout=10)
        node_v = out.strip().lstrip("v") if rc == 0 else None
    chosen = "v4" if v4 else ("v3" if v3 else "none")
    advice = []
    result = {
        "plugin": {"version": paths.plugin_version(), "python": platform.python_version(), "root": paths.plugin_root()},
        "cli": {
            "sentry_v4": v4, "sentry_cli_v3": v3, "chosen": chosen,
            "node": node_v, "npx": bool(npx),
        },
        "git": git_info(root),
        "coexistence": coexistence(),
        "legacy": {
            "home_sentryclirc_exists": os.path.isfile(os.path.expanduser("~/.sentryclirc")),
            "token_env_vars_set": [n for n in TOKEN_ENV_NAMES if os.environ.get(n)],
        },
        "auth": {"state": "unchecked"},
    }
    if chosen == "none":
        advice.append("Install the sentry CLI (not installed by this plugin): " + INSTALL_V4)
    elif chosen == "v3":
        advice.append(
            "Only sentry-cli %s is installed. Audits that read the org need the sentry v4 CLI: %s. "
            "Command names for v3 are in data/cli-map.json." % (v3["version"], INSTALL_V4)
        )
    if v3 and v3["major"] < 3:
        advice.append("sentry-cli %s is older than 3.x; upload commands differ (see cli-map)." % v3["version"])
    if chosen == "v4" and want_auth:
        st = cli_tools.auth_status()
        result["auth"] = st
        if st["state"] == "ok":
            sc = cli_tools.scopes()
            result["auth"]["scopes"] = sc
            regions = cli_tools.org_regions(st.get("orgs", []))
            result["auth"]["org_regions"] = regions
            if sc is not None:
                result["auth"]["can_write"] = bool(WRITE_SCOPES & set(sc))
                result["auth"]["missing_for_org_writes"] = {
                    s: why for s, why in NOT_IN_DEFAULT.items() if s not in sc
                }
                if not result["auth"]["can_write"]:
                    advice.append("Login is read-only: org audits work; creating projects/monitors needs: " + LOGIN)
            exp = st.get("expires_at_ms")
            if exp and st.get("refresh") is False:
                advice.append("The stored login does not auto-refresh; re-run: " + LOGIN)
        else:
            advice.append("Not logged in. Run it yourself (opens a browser): %s   (read-only audits) or %s" % (LOGIN_RO, LOGIN))
            advice.append("Without a login, every org-side check is reported UNVERIFIED, never skipped silently.")
    if result["legacy"]["home_sentryclirc_exists"]:
        advice.append(
            "~/.sentryclirc exists (legacy credential file). It is never read by this plugin; "
            "the stored login wins unless SENTRY_FORCE_ENV_TOKEN=1."
        )
    if result["legacy"]["token_env_vars_set"]:
        advice.append(
            "Token env vars set: %s (values never shown). An env token overrides nothing unless "
            "SENTRY_FORCE_ENV_TOKEN=1; org tokens (sntrys_) cannot audit." % ", ".join(result["legacy"]["token_env_vars_set"])
        )
    if not node:
        advice.append("node/npx not found: the optional @sentry/wizard route and JS tooling are unavailable.")
    if result["coexistence"]["note"]:
        advice.append(result["coexistence"]["note"])
    if result["git"].get("repo") and result["git"].get("dirty"):
        advice.append("Working tree has uncommitted changes: apply will ask you to commit/stash or create a branch.")
    result["advice"] = advice
    return result


def render_text(d: dict) -> str:
    lines = ["sentry plugin %s (engine python %s)" % (d["plugin"]["version"], d["plugin"]["python"])]
    c = d["cli"]
    lines.append("sentry v4 CLI : %s" % (("%s (%s)" % (c["sentry_v4"]["version"], c["sentry_v4"]["path"])) if c["sentry_v4"] else "not installed"))
    lines.append("sentry-cli 3.x: %s" % (("%s (%s)" % (c["sentry_cli_v3"]["version"], c["sentry_cli_v3"]["path"])) if c["sentry_cli_v3"] else "not installed"))
    lines.append("command set   : %s" % c["chosen"])
    a = d["auth"]
    if a.get("state") == "ok":
        lines.append("login         : %s via %s, orgs: %s" % (a.get("user"), a.get("source"), ", ".join(a.get("orgs", []))))
        for slug, r in (a.get("org_regions") or {}).items():
            lines.append("  %s region   : %s" % (slug, r.get("region_url")))
        if a.get("scopes") is not None:
            lines.append("  scopes      : %s" % " ".join(a["scopes"]))
    else:
        lines.append("login         : %s" % a.get("state"))
    g = d["git"]
    lines.append("git           : %s" % (("branch %s, %s" % (g.get("branch"), "dirty" if g.get("dirty") else "clean")) if g.get("repo") else "not a git repo"))
    for adv in d["advice"]:
        lines.append("- " + adv)
    return "\n".join(lines)
