#!/usr/bin/env python3
"""Maintainer tool: turn one real Sentry event (a JSON file you fetched read-only) into a scrubbed recording for scripts/replay-events.py.

  record-event.py RAW.json NAME --source "project/eventid" --note "why this event" [--preset strict]

Only the fields `verify scan` reads are kept (user, environment and release tags, message, the exception, request and message entries,
frames); personal values are replaced (home paths, hosts, emails, city and region, header and body values). The expectation is whatever the
scan says about the scrubbed event right now: read it before committing the file."""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import verify  # noqa: E402

OUT = os.path.join(ROOT, "evals", "recordings", "events")


def clean_str(s):
    s = re.sub(r"/(?:Users|home)/[A-Za-z0-9._-]+/(?:[^\"'\s]*?/)?(sentry-plugin-test-[a-z0-9-]+)/", r"/home/dev/\1/", s)  # drop the machine's directory layout
    s = re.sub(r"/(?:Users|home)/[A-Za-z0-9._-]+", "/home/dev", s)
    s = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "person@example.invalid", s)
    s = re.sub(r"zeo-?h1", "example-org", s)
    return s


def clean(o):
    if isinstance(o, str):
        return clean_str(o)
    if isinstance(o, list):
        return [clean(x) for x in o]
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    return o


def mask_values(o):
    if isinstance(o, dict):
        return {k: mask_values(v) for k, v in o.items()}
    if isinstance(o, list):
        return [mask_values(x) for x in o]
    if isinstance(o, str):
        return o if o == "[Filtered]" else "<redacted>"
    return o


def project(ev):
    user = dict(ev.get("user") or {})
    if user.get("geo"):
        user["geo"] = {"city": "Example City", "country_code": "XX", "region": "Example Region"}
    for k in ("email", "username", "name"):
        if user.get(k):
            user[k] = "person@example.invalid" if k == "email" else "person"
    if user.get("ip_address") and user["ip_address"] != "{{auto}}":
        user["ip_address"] = "203.0.113.9"
    entries = []
    for e in ev.get("entries", []):
        t, d = e.get("type"), dict(e.get("data") or {})
        if t == "request":
            hdrs = d.get("headers") or []
            d = {"method": d.get("method"), "url": clean_str(str(d.get("url") or "")),
                 "headers": [[h[0], h[1] if h[1] == "[Filtered]" else "<redacted>"] for h in hdrs if isinstance(h, (list, tuple)) and len(h) == 2],
                 "cookies": [[c[0], c[1] if c[1] == "[Filtered]" else "<redacted>"] for c in (d.get("cookies") or []) if isinstance(c, (list, tuple)) and len(c) == 2],
                 "data": mask_values(d.get("data"))}
        elif t == "exception":
            vals = []
            for v in d.get("values", []) or []:
                frames = []
                for fr in ((v.get("stacktrace") or {}).get("frames") or []):
                    f2 = {k: fr.get(k) for k in ("filename", "absPath", "abs_path", "module", "function", "lineNo", "inApp") if k in fr}
                    if fr.get("vars"):
                        f2["vars"] = mask_values(fr["vars"])
                    frames.append(f2)
                vals.append({"type": v.get("type"), "value": v.get("value"), "stacktrace": {"frames": frames}})
            d = {"values": vals}
        elif t == "message":
            d = {"formatted": d.get("formatted")}
        else:
            continue
        entries.append({"type": t, "data": d})
    tags = [t for t in ev.get("tags", []) if t.get("key") in ("environment", "release")]
    out = {"user": user, "tags": tags, "message": ev.get("message") or ev.get("title"), "entries": entries}
    ctx = ev.get("contexts") or {}
    if "environ" in ctx:
        out["contexts"] = {"environ": {"redacted": True}}
    return clean(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw"); ap.add_argument("name")
    ap.add_argument("--source", required=True); ap.add_argument("--note", required=True)
    ap.add_argument("--preset", default="strict")
    a = ap.parse_args()
    ev = project(json.load(open(a.raw)))
    pol = {"privacy": {"preset": a.preset, "ai_io": "off"}}
    res = verify.scan(ev, pol)
    rec = {"recorded": datetime.date.today().isoformat(), "source": a.source, "note": a.note, "preset": a.preset, "event": ev,
           "expect": {"ok": res["ok"], "violations": [v[:60] for v in res["violations"]], "warnings": [w[:60] for w in res["warnings"]]}}
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, a.name + ".json")
    json.dump(rec, open(path, "w"), indent=1, sort_keys=True)
    open(path, "a").write("\n")
    print("%s: ok=%s violations=%d warnings=%d" % (a.name, res["ok"], len(res["violations"]), len(res["warnings"])))
    for x in res["violations"] + res["warnings"]:
        print("   -", x[:110])


if __name__ == "__main__":
    main()
