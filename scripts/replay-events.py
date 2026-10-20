#!/usr/bin/env python3
"""Replay recorded events through `verify scan` and compare with what the scan said when they were recorded. Then make each passing event
worse (IP address, email, auth header, cookie, process environment, a Sentry token) and require the scan to notice. Exit 1 on any difference.
Recordings: evals/recordings/events/*.json (scrubbed; made with scripts/record-event.py)."""
import copy
import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import verify  # noqa: E402

fails = 0


def pol(rec):
    return {"privacy": {"preset": rec.get("preset", "strict"), "ai_io": "off"}}


def worse(ev):
    out = {}
    a = copy.deepcopy(ev); a.setdefault("user", {})["ip_address"] = "203.0.113.9"; out["user.ip_address"] = a
    b = copy.deepcopy(ev); b.setdefault("user", {})["email"] = "person@example.invalid"; out["user.email"] = b
    c = copy.deepcopy(ev); c["entries"] = [e for e in c["entries"] if e["type"] != "request"] + [{"type": "request", "data": {"headers": [["Authorization", "Bearer abc"]], "cookies": [], "data": None}}]; out["auth header"] = c
    d = copy.deepcopy(ev); d["entries"] = [e for e in d["entries"] if e["type"] != "request"] + [{"type": "request", "data": {"headers": [], "cookies": [["session", "abc"]], "data": None}}]; out["cookie"] = d
    e = copy.deepcopy(ev); e["contexts"] = {"environ": {"HOME": "x"}}; out["process environment"] = e
    f = copy.deepcopy(ev); f["message"] = "token " + "sntry" + "u_" + "0123456789abcdef" * 4; out["sentry token"] = f
    g = copy.deepcopy(ev)
    g["tags"] = [t for t in g.get("tags", []) if t.get("key") != "environment"] + [{"key": "environment", "value": "production"}]
    g["message"] = "failed to open /home/dev/projects/app/config.json"; out["home path in a production event"] = g
    return out


files = sorted(glob.glob(os.path.join(ROOT, "evals", "recordings", "events", "*.json")))
if not files:
    print("no recordings")
    sys.exit(1)
for fn in files:
    name = os.path.basename(fn)[:-5]
    rec = json.load(open(fn))
    got = verify.scan(rec["event"], pol(rec))
    exp = rec["expect"]
    same = got["ok"] == exp["ok"] and [v[:60] for v in got["violations"]] == exp["violations"] and [w[:60] for w in got["warnings"]] == exp["warnings"]
    fails += 0 if same else 1
    print("%-5s replay  %-34s ok=%s (%s)" % ("ok" if same else "FAIL", name, got["ok"], rec["note"][:60]))
    if not same:
        print("      recorded:", json.dumps(exp)[:300])
        print("      now     :", json.dumps({"ok": got["ok"], "violations": [v[:60] for v in got["violations"]], "warnings": [w[:60] for w in got["warnings"]]})[:300])
    if exp["ok"]:
        for what, ev in worse(rec["event"]).items():
            r = verify.scan(ev, pol(rec))
            noticed = not r["ok"]
            fails += 0 if noticed else 1
            if not noticed:
                print("FAIL  mutation %-34s %s not noticed" % (name, what))
print("\n%s" % ("ALL REPLAYS MATCH" if not fails else "%d REPLAY DIFFERENCE(S)" % fails))
sys.exit(1 if fails else 0)
