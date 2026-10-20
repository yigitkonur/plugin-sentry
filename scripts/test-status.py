#!/usr/bin/env python3
"""Regression checks for finding status changes: `verified` needs the rung that was reached and refuses one below what the finding
requires, so the ledger cannot say verified for something only partly proven. Exit 1 on any failure. Run by scripts/check.sh."""
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import findings, util  # noqa: E402

fails = 0


def expect(name, fn, want_error_part=None):
    global fails
    try:
        out = fn()
        ok = want_error_part is None
        detail = out
    except util.EngineError as e:
        ok = want_error_part is not None and want_error_part in str(e)
        detail = str(e)[:90]
    fails += 0 if ok else 1
    print("%-5s %s | %s" % ("ok" if ok else "FAIL", name, str(detail)[:90]))


def make(root, fid, rung, status):
    d = os.path.join(root, ".sentry-plugin", "findings", "u")
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(root, ".sentry-plugin", "findings", ".ids"), exist_ok=True)
    open(os.path.join(root, ".sentry-plugin", "findings", ".ids", fid), "w").close()
    open(os.path.join(d, "%s-x.md" % fid), "w").write("---\nid: %s\nunit: u\nproduct: core\ncheck: core.release\nseverity: P1\nkind: fix\nstatus: %s\ntitle: t\nverify: { rung: %s, how: h, expect: e }\n---\n## What\nx\n" % (fid, status, rung))


with tempfile.TemporaryDirectory() as root:
    make(root, "F-001", "R6", "applied")
    make(root, "F-002", "R3", "applied")
    make(root, "F-003", "R0", "applied")
    expect("verified without --rung is refused", lambda: findings.set_status(root, "F-001", "verified", ran="r", saw="s"), "--rung")
    expect("rung below the required one is refused", lambda: findings.set_status(root, "F-001", "verified", ran="r", saw="s", rung="R3"), "needs rung R6")
    expect("the refusal points at unverified", lambda: findings.set_status(root, "F-001", "verified", ran="r", saw="s", rung="R3"), "unverified")
    expect("an unknown rung is refused", lambda: findings.set_status(root, "F-001", "verified", ran="r", saw="s", rung="R9"), "--rung")
    expect("the required rung is accepted", lambda: findings.set_status(root, "F-002", "verified", ran="r", saw="s", rung="R3"))
    expect("a higher rung is accepted", lambda: findings.set_status(root, "F-003", "verified", ran="r", saw="s", rung="R5"))
    fm, _ = findings._load_file(findings.find_path(root, "F-003"))
    got = (fm.get("proof") or {}).get("rung")
    fails += 0 if got == "R5" else 1
    print("%-5s proof records the rung reached (R5), not the required one | %s" % ("ok" if got == "R5" else "FAIL", got))
    expect("verified is still refused without --ran and --saw", lambda: findings.set_status(root, "F-001", "verified", rung="R6"), "--ran")
    expect("applied -> unverified with a reason still works", lambda: findings.set_status(root, "F-001", "unverified", reason="R3 reached, deploy not run"))

print("\n%s" % ("STATUS TESTS PASSED" if not fails else "%d STATUS TEST(S) FAILED" % fails))
sys.exit(1 if fails else 0)
