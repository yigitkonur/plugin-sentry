"""H1: restore the run digest after compaction/resume, and name the detected SDK once. Emits nothing otherwise."""
from __future__ import annotations

import os

from .. import runstate, util
from . import common


def _digest(root, st) -> str:
    from .. import findings
    allf = findings.load_all(root)
    counts = {}
    for f in allf:
        counts[f.get("status")] = counts.get(f.get("status"), 0) + 1
    led = findings.ledger_check(root)
    nxt = {
        "preamble": "finish the preamble (sentry-ctx flow preamble)",
        "auditing": "finish dispatching auditors, then sentry-ctx ledger and report",
        "reporting": "present the report and ask for approval",
        "approved": "run sentry-ctx flow apply",
        "implementing": "continue sentry-ctx flow apply (git log shows committed groups)",
        "verifying": "continue sentry-ctx flow verify",
    }.get(st.get("phase"), "")
    pol = ""
    try:
        from .. import policy
        p = policy.load(root) or {}
        pol = " policy: preset=%s ai_io=%s replay=%s org=%s release_owner=%s." % ((p.get("privacy") or {}).get("preset"), (p.get("privacy") or {}).get("ai_io"), (p.get("privacy") or {}).get("replay_mask"), p.get("org_access"), p.get("release_owner"))
    except Exception:
        pass
    trig = ", live temp triggers: %s" % ",".join(led["live_triggers"]) if led["live_triggers"] else ""
    s = "sentry plugin: run %s (%s) in phase '%s'. findings %s; pending coverage cells %d%s.%s Next: %s. State is in .sentry-plugin/ (sentry-ctx run status)." % (
        st.get("run_id"), st.get("flow"), st.get("phase"), counts or "none yet", len(led["pending_cells"]), trig, pol, nxt or "ask the user")
    return s[:1200]


def run():
    inp = common.read_input()
    if common.mode() == "off":
        return
    root = common.project_dir(inp)
    sid = inp.get("session_id")
    if sid:
        try:
            with open(runstate.session_marker(root), "w", encoding="utf-8") as f:
                f.write(sid)
        except OSError:
            pass
    source = inp.get("source", "startup")
    st = runstate.load(root)
    parts = []
    if st and st.get("phase") != "done":
        if source in ("compact", "resume") or st.get("session_id") == sid:
            parts.append(_digest(root, st))
        elif source in ("startup", "clear"):
            parts.append("sentry plugin: an unfinished %s run (%s, phase '%s') exists in this repo from an earlier session. Offer to continue it (sentry-ctx run adopt) or discard it (/sentry:clean) if the user brings up Sentry." % (st.get("flow"), st.get("run_id"), st.get("phase")))
    if common.mode() == "on" and source in ("startup", "clear", "resume"):
        try:
            units = common.load_units(root)
        except Exception:
            units = None
        sdk = []
        for u in units or []:
            pk = [p for p in u["sentry"]["packages"] if p.get("kind") != "tooling" and p.get("resolved")]
            if pk and u["sentry"]["status"] != "absent":
                init = (u["sentry"]["init_sites"][0]["file"] if u["sentry"]["init_sites"] else "no init call found")
                sdk.append("%s %s %s (%s)" % (u["id"], pk[0]["name"], pk[0]["resolved"], init))
        if sdk:
            parts.append(("Sentry detected: %s. SDK majors changed in 2026 (JS v11, Cocoa 9, Python 3 alpha, sentry v4 CLI): do not write Sentry options from memory; look them up with `sentry-ctx docs page <path>` / `sentry-ctx ref <module>`. Deep review: /sentry:audit." % "; ".join(sdk[:3]))[:500])
    if util.host() == "codex" and source in ("startup", "clear", "resume"):
        from .. import paths
        ctx = os.path.join(paths.plugin_root(), "bin", "sentry-ctx")
        parts.append("Sentry plugin (Codex): its skills (start, audit, init, doctor, ...) tell you to run `sentry-ctx ...`; that command is not on PATH here, so run it as `%s ...`. A skill's `!`-prefixed lines are not run for you: run them yourself. There are no subagents and no AskUserQuestion: ask as a numbered list and wait." % ctx)
    if parts:
        common.context("SessionStart", "\n".join(parts))
