"""R3 (arrive) and R5 (private) for marked events. Reads go through the sentry CLI; nothing here writes to Sentry."""
from __future__ import annotations

import json
import os
import re
import time

from . import cli_tools, paths, policy, tokens, util

PATH_LEAK = re.compile(r"(/Users/[^/\s\"']+|/home/[^/\s\"']+|[A-Za-z]:\\\\Users\\\\[^\\\\\s\"']+)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "x-auth-token", "proxy-authorization", "x-csrf-token"}
GENAI_KEYS = ("gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.prompt", "gen_ai.completion", "gen_ai.request.messages", "gen_ai.response.text")


def new_marker(root):
    from . import runstate
    st = runstate.load(root) or {}
    rid = st.get("run_id", "r-adhoc").replace("r-", "")
    n = int(time.time()) % 100000
    return "%s-%d" % (rid, n)


def _tags(event):
    t = event.get("tags")
    if isinstance(t, list):
        return {x.get("key"): x.get("value") for x in t if isinstance(x, dict)}
    return t if isinstance(t, dict) else {}


def summarize(event):
    tags = _tags(event)
    rel = event.get("release")
    if isinstance(rel, dict):
        rel = rel.get("version")
    return {
        "event_id": event.get("eventID") or event.get("id"), "release": rel or tags.get("release"),
        "environment": tags.get("environment"), "platform": event.get("platform"),
        "sdk": event.get("sdk"), "tags": {k: v for k, v in tags.items() if k not in ("level", "interface_type")},
        "date": event.get("dateCreated"),
    }


def wait(root, org, project, marker, timeout=120, interval=3):
    deadline = time.time() + timeout
    q = "plugin_marker:%s" % marker
    issue = None
    tries = 0
    while time.time() < deadline:
        tries += 1
        rc, data, err = cli_tools.run_json(["issue", "list", "%s/%s" % (org, project), "-q", q, "--json", "--fields", "id,shortId,title,permalink", "-n", "5"], timeout=40)
        rows = (data or {}).get("data") if isinstance(data, dict) else data
        if rc == 0 and rows:
            issue = rows[0]
            break
        if rc in (10, 11, 12, 13):
            raise util.EngineError("not authenticated (exit %d): run `sentry auth login` yourself" % rc, 3)
        time.sleep(interval)
    if not issue:
        return {"arrived": False, "marker": marker, "waited_s": timeout, "polls": tries}
    r = cli_tools.api("/organizations/%s/issues/%s/events/latest/" % (org, issue["id"]))
    ev = r["data"] if isinstance(r["data"], dict) else {}
    ev_path = os.path.join(paths.state_dir(root), "evidence", "event-%s.json" % marker)
    util.write_json(ev_path, ev)
    out = {"arrived": True, "marker": marker, "issue": {k: issue.get(k) for k in ("id", "shortId", "title", "permalink")}, "polls": tries, "event_file": os.path.relpath(ev_path, root)}
    out.update(summarize(ev))
    return out


def _walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, path + "." + str(k) if path else str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, "%s[%d]" % (path, i))
    else:
        yield path, o


def scan(event: dict, pol: dict | None):
    pol = pol or {}
    preset = ((pol.get("privacy") or {}).get("preset")) or "standard"
    ai_io = ((pol.get("privacy") or {}).get("ai_io")) or "off"
    strict = preset == "strict"
    permissive = preset == "permissive"
    v, w = [], []
    user = event.get("user") or {}
    if user.get("ip_address") and user.get("ip_address") not in ("{{auto}}",) and not permissive:
        v.append("user.ip_address is set")
    if user.get("geo"):
        (w if permissive else v if strict else w).append("user.geo is present (country/city inferred from the connecting IP at ingest; only the server-side IP-storage setting removes it)")
    for f in ("email", "username", "name"):
        if user.get(f) and not permissive:
            (v if (strict or f == "email") else w).append("user.%s is set" % f)
    if user.get("id") and strict:
        v.append("user.id is set under the strict preset")
    ctx = event.get("context") or {}
    if "environ" in ctx or "environ" in (event.get("contexts") or {}):
        v.append("context.environ is present (the sender attached its process environment; send with --no-environ)")
    for ent in event.get("entries", []) or []:
        t, d = ent.get("type"), ent.get("data") or {}
        if t == "request":
            hdrs = d.get("headers") or []
            pairs = hdrs.items() if isinstance(hdrs, dict) else [(h[0], h[1]) for h in hdrs if isinstance(h, (list, tuple)) and len(h) == 2]
            for k, val in pairs:
                if str(k).lower() in SENSITIVE_HEADERS and val not in ("[Filtered]", None, ""):
                    v.append("request header %s is present unfiltered" % k)
            if d.get("cookies") and any(c[1] not in ("[Filtered]", None, "") for c in d["cookies"] if isinstance(c, (list, tuple)) and len(c) == 2):
                v.append("request cookies are present unfiltered")
            if d.get("data") not in (None, "", {}, "[Filtered]") and not permissive:
                v.append("request body is present")
        if t == "exception":
            for val in d.get("values", []) or []:
                for fr in ((val.get("stacktrace") or {}).get("frames") or []):
                    if fr.get("vars"):
                        (v if strict else w).append("stack frame local variables are present (%s)" % fr.get("function", "?"))
                        break
    blob = json.dumps(event, ensure_ascii=False)
    if tokens.has_token(blob):
        v.append("a Sentry credential-shaped string is present in the event")
    m = PATH_LEAK.search(blob)
    if m:
        v.append("a user home path is present: %s" % re.sub(r"(/Users/|/home/)[^/\s\"']+", r"\1<name>", m.group(0)))
    if ai_io == "off":
        for k in GENAI_KEYS:
            if k in blob:
                v.append("AI input/output attribute %s is present but the policy says AI I/O off" % k)
                break
    em = EMAIL.search(json.dumps({"m": event.get("message"), "e": [e for e in event.get("entries", []) if e.get("type") in ("message", "exception")]}, ensure_ascii=False))
    if em and not permissive:
        w.append("an email-shaped string is present in the message/exception text")
    return {"ok": not v, "preset": preset, "violations": sorted(set(v)), "warnings": sorted(set(w))}
