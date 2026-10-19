"""Thin wrappers around the `sentry` v4 CLI, `sentry-cli` 3.x and `sentry api`.

The plugin never reads or prints the CLI's credential: it only calls commands that reuse the stored login.
"""
from __future__ import annotations

import json
import os
import re
import shutil

from . import util

SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)")

# Exit codes documented at https://cli.sentry.dev/exit-codes/ and observed in spike S1.
EXIT_LABELS = {
    10: "auth", 11: "auth", 12: "auth", 13: "host-trust", 60: "http-error",
    40: "feature-unavailable", 41: "feature-unavailable", 42: "feature-unavailable",
}


def env() -> dict:
    e = dict(os.environ)
    e["SENTRY_NO_CACHE"] = "1"
    e["NO_COLOR"] = "1"
    e["SENTRY_CLI_NO_TELEMETRY"] = "1"
    return e


def _which(name: str):
    extra = os.path.expanduser("~/.local/bin")
    path = os.environ.get("PATH", "")
    if extra not in path.split(os.pathsep):
        path = path + os.pathsep + extra
    return shutil.which(name, path=path)


def _version(binary: str):
    rc, out, err = util.run([binary, "--version"], timeout=20, env=env())
    if rc != 0:
        return None
    m = SEMVER.search(out + err)
    return m.group(0) if m else None


def sentry_v4():
    p = _which("sentry")
    if not p:
        return None
    v = _version(p)
    return {"path": p, "version": v} if v else None


def sentry_cli_v3():
    p = _which("sentry-cli")
    if not p:
        return None
    v = _version(p)
    if not v:
        return None
    return {"path": p, "version": v, "major": int(v.split(".")[0])}


def sentry_bin():
    info = sentry_v4()
    return info["path"] if info else None


def run_json(args, timeout=60, cwd=None):
    """Run `sentry <args> --json`; returns (rc, data, stderr). data is None when stdout is not JSON."""
    binary = sentry_bin()
    if not binary:
        return 127, None, "sentry v4 CLI not installed"
    rc, out, err = util.run([binary, *args], cwd=cwd, timeout=timeout, env=env())
    try:
        data = json.loads(out) if out.strip() else None
    except ValueError:
        data = None
    return rc, data, err


def api(path: str, method: str = "GET", fields=None, body=None, timeout=60, dry_run=False):
    """`sentry api`; GET unless asked. Returns dict(rc, data, raw, label)."""
    binary = sentry_bin()
    if not binary:
        return {"rc": 127, "data": None, "raw": "", "label": "no-cli"}
    cmd = [binary, "api", "-X", method]
    if dry_run:
        cmd.append("--dry-run")
    for k, v in (fields or {}).items():
        cmd += ["-F", "%s=%s" % (k, v)]
    input_text = None
    if body is not None:
        cmd += ["--input", "-"]
        input_text = json.dumps(body)
    cmd.append(path)
    rc, out, err = util.run(cmd, timeout=timeout, env=env(), input_text=input_text)
    data = None
    try:
        data = json.loads(out) if out.strip() else None
    except ValueError:
        pass
    label = "ok" if rc == 0 else EXIT_LABELS.get(rc, "error")
    return {"rc": rc, "data": data, "raw": out if data is None else "", "err": err.strip()[:300], "label": label}


def auth_status():
    rc, data, err = run_json(["auth", "status", "--json"], timeout=40)
    if not isinstance(data, dict):
        return {"state": "none", "detail": err.strip().splitlines()[-1] if err.strip() else "not logged in"}
    ver = data.get("verification") or {}
    token = data.get("token") or {}
    state = "ok" if data.get("authenticated") and ver.get("success", True) else "invalid"
    return {
        "state": state,
        "source": data.get("source"),
        "user": (data.get("user") or {}).get("email"),
        "token_display": token.get("display"),
        "expires_at_ms": token.get("expiresAt"),
        "refresh": token.get("refreshEnabled"),
        "orgs": [o.get("slug") for o in ver.get("organizations", []) if isinstance(o, dict)],
    }


def scopes():
    """OAuth/token scopes via GET /api/0/ (spike S1: `auth.scopes`)."""
    r = api("/api/0/")
    if r["rc"] != 0 or not isinstance(r["data"], dict):
        return None
    sc = (r["data"].get("auth") or {}).get("scopes")
    return sorted(sc) if isinstance(sc, list) else None


def org_regions(slugs):
    out = {}
    for slug in slugs:
        rc, data, _ = run_json(["org", "view", slug, "--json"], timeout=40)
        if isinstance(data, dict):
            links = data.get("links") or {}
            out[slug] = {"region_url": links.get("regionUrl"), "org_url": links.get("organizationUrl")}
    return out
