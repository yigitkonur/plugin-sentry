"""H5: refuse to finish while the run this session owns has unfinished work. Deterministic: reads the ledger, no model call."""
from __future__ import annotations

from .. import findings, runstate
from . import common

MAX_BLOCKS = 2


def run():
    inp = common.read_input()
    if common.mode() == "off":
        return
    root = common.project_dir(inp)
    st = runstate.load(root)
    if not st or st.get("phase") in (None, "done"):
        return
    sid = inp.get("session_id")
    if not st.get("session_id") or (sid and st["session_id"] != sid):
        return  # unowned or another session's run: never trap an unrelated session (`sentry-ctx run adopt` claims it)
    if st.get("stop_blocks", 0) >= MAX_BLOCKS:
        return
    led = findings.ledger_check(root)
    problems = []
    phase = st.get("phase")
    if phase in ("auditing", "reporting") and led["pending_cells"]:
        problems.append("%d applicable coverage cells are still pending (e.g. %s). Dispatch auditors for them or mark them `sentry-ctx coverage set ... --state unverified --reason ...`." % (len(led["pending_cells"]), ", ".join(led["pending_cells"][:4])))
    if phase in ("implementing", "verifying", "approved") and led["applied_unverified"]:
        problems.append("applied findings without proof: %s. Run the verify flow, or `sentry-ctx finding set-status <id> unverified --reason ...` / `waived --reason ...`." % ", ".join(led["applied_unverified"][:8]))
    if led["live_triggers"]:
        problems.append("temporary trigger files still exist: %s. Delete them, then `sentry-ctx run trigger <path> --trigger-action remove`." % ", ".join(led["live_triggers"]))
    if not problems:
        return
    st["stop_blocks"] = st.get("stop_blocks", 0) + 1
    runstate.save(root, st)
    reason = "Sentry run %s (phase %s) is not finished: %s If the user wants to abandon the run, say so plainly and use /sentry:clean." % (st.get("run_id"), phase, " ".join(problems))
    common.emit({"decision": "block", "reason": reason[:1000]})
