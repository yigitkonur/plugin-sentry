"""Subcommand registration for every engine command."""
from __future__ import annotations

import json
import os
import sys

from . import paths, util


def _root(args):
    return paths.project_root(args.path)


def _read_stdin_json():
    data = sys.stdin.read()
    if not data.strip():
        raise util.EngineError("expected a JSON object on stdin")
    try:
        obj = json.loads(data)
    except ValueError as e:
        raise util.EngineError("stdin is not valid JSON: %s" % e)
    if not isinstance(obj, dict):
        raise util.EngineError("stdin JSON must be an object")
    return obj


def _detect(args, fresh=True):
    from .detect import core
    return core.detect(_root(args), include_tests=getattr(args, "include_tests", False))


def _units(root):
    d = util.read_json(os.path.join(paths.state_dir(root), "plan.json"))
    if d:
        return {u["id"] for u in d["units"]}
    return set()


# ---- detect / steer ----
def cmd_detect(args):
    root = _root(args)
    res = _detect(args)
    if args.write:
        util.write_json(os.path.join(paths.state_dir(root), "detect.json"), res)
    util.emit(res)


def cmd_steer(args):
    from . import findings, policy, steer
    root = _root(args)
    det = _detect(args)
    pol = policy.load(root)
    org_access = (pol or {}).get("org_access") or args.org_access or "none"
    pl = steer.plan(det, pol, org_access)
    if args.write:
        util.write_json(os.path.join(paths.state_dir(root), "detect.json"), det)
        util.write_json(os.path.join(paths.state_dir(root), "plan.json"), pl)
        findings.cov_init(root, pl)
    util.emit(pl)


# ---- policy ----
def cmd_policy(args):
    from . import policy, steer
    root = _root(args)
    act = args.action
    if act == "get":
        util.emit({"exists": policy.load(root) is not None, "policy": policy.load(root)})
    elif act == "questions":
        det = _detect(args)
        prev = policy.load(root)
        pl = steer.plan(det, prev, (prev or {}).get("org_access") or "none")
        util.emit(policy.questions(det, pl, prev))
    elif act == "set":
        answers = _read_stdin_json()
        pol = policy.from_answers(answers)
        policy.save(root, pol)
        util.emit({"saved": policy.path(root), "policy": pol})
    elif act == "from-env":
        src = os.environ.get("SENTRY_PLUGIN_POLICY_ANSWERS")
        if not src:
            raise util.EngineError("SENTRY_PLUGIN_POLICY_ANSWERS is not set (headless policy answers file)")
        answers = util.read_json(src)
        if not isinstance(answers, dict):
            raise util.EngineError("answers file must be a JSON object of {question id: value}")
        pol = policy.from_answers(answers)
        policy.save(root, pol)
        util.emit({"saved": policy.path(root), "policy": pol, "source": "env"})


# ---- run state ----
def cmd_run(args):
    from . import runstate
    root = _root(args)
    a = args.action
    if a == "start":
        util.emit(runstate.start(root, args.flow, units=sorted(_units(root))))
    elif a == "status":
        st = runstate.load(root)
        util.emit(st if st else {"active": False})
    elif a == "phase":
        util.emit(runstate.set_phase(root, args.value))
    elif a == "approve-write":
        util.emit(runstate.approve_write(root, args.method, args.value, args.finding))
    elif a == "trigger":
        util.emit(runstate.trigger(root, args.trigger_action, args.value))
    elif a == "gitignore":
        util.emit({"gitignore": runstate.gitignore(root, args.value)})
    elif a == "end":
        st = runstate.require(root)
        st["phase"] = "done"
        runstate.save(root, st)
        util.emit(st)


# ---- findings ----
def cmd_finding(args):
    from . import findings
    root = _root(args)
    a = args.action
    if a == "add":
        obj = _read_stdin_json()
        util.emit(findings.add(root, obj, _units(root), force=args.force))
    elif a == "list":
        rows = findings.load_all(root)
        for k, v in (("unit", args.unit), ("status", args.status), ("severity", args.severity), ("product", args.product)):
            if v:
                rows = [r for r in rows if r.get(k) == v]
        util.emit([{k: r.get(k) for k in ("id", "unit", "product", "check", "severity", "status", "kind", "title", "files")} for r in rows])
    elif a == "show":
        p = findings.find_path(root, args.id)
        if not p:
            raise util.EngineError("no such finding: " + args.id)
        print(util.read_text(p))
    elif a == "set-status":
        util.emit(findings.set_status(root, args.id, args.value, reason=args.reason, ran=args.ran, saw=args.saw))
    elif a == "approve":
        ids = args.ids.split(",") if args.ids else None
        sev = args.severity.split(",") if args.severity else None
        kinds = args.kinds.split(",") if args.kinds else None
        util.emit({"approved": findings.approve(root, ids=ids, severities=sev, all_open=args.all, kinds=kinds)})


def cmd_coverage(args):
    from . import findings
    root = _root(args)
    if args.action == "set":
        util.emit(findings.cov_set(root, args.unit, args.product, args.state, note=args.note, reason=args.reason))
    elif args.action == "show":
        util.emit(findings.cov_load(root))


def cmd_ledger(args):
    from . import findings
    res = findings.ledger_check(_root(args))
    util.emit(res)
    return 0 if res["ok"] else 1


def cmd_report(args):
    from . import findings
    root = _root(args)
    plan = util.read_json(os.path.join(paths.state_dir(root), "plan.json"))
    text = findings.report(root, plan)
    print(text)


# ---- knowledge ----
def cmd_ref(args):
    from . import refs
    if args.name == "list":
        util.emit(refs.list_names(args.section or ""))
    else:
        print(refs.read(args.name, args.section))


def cmd_flow(args):
    from . import refs
    print(refs.flow(args.name))


def cmd_docs(args):
    from . import docs
    r = docs.page(args.page, sec=args.section, list_only=args.list, refresh=args.refresh)
    if args.json:
        util.emit(r)
    elif args.list:
        print("# %s\n# %s" % (r["title"], r["url"]))
        print("\n".join(r["headings"]))
    else:
        print("<!-- source: %s%s -->" % (r["url"], " (cached)" if r["cached"] else ""))
        print(r["text"])
        if r["truncated"]:
            print("\n<!-- truncated: ask for a narrower --section -->")


def cmd_cli_map(args):
    data = paths.load_json_data("cli-map.json")
    if args.intent:
        it = data["intents"].get(args.intent)
        if not it:
            raise util.EngineError("unknown intent; have: " + ", ".join(sorted(data["intents"])))
        util.emit(it)
    elif args.v3:
        q = args.v3.strip().lower()
        util.emit([c for c in data["commands"] if q in c["v3"].lower()])
    else:
        util.emit(data)


def register(sub):
    d = sub.add_parser("detect", help="deterministic repo detection")
    d.add_argument("--include-tests", action="store_true")
    d.add_argument("--write", action="store_true", help="write .sentry-plugin/detect.json")
    d.set_defaults(fn=cmd_detect)

    s = sub.add_parser("steer", help="product applicability per unit")
    s.add_argument("--include-tests", action="store_true")
    s.add_argument("--org-access", choices=["none", "read-only", "read-write"], default=None)
    s.add_argument("--write", action="store_true", help="write plan.json and initialise coverage")
    s.set_defaults(fn=cmd_steer)

    p = sub.add_parser("policy", help="policy answers (always asked)")
    p.add_argument("action", choices=["get", "questions", "set", "from-env"])
    p.add_argument("--include-tests", action="store_true")
    p.set_defaults(fn=cmd_policy)

    r = sub.add_parser("run", help="run state: phase, approved org writes, temp triggers")
    r.add_argument("action", choices=["start", "status", "phase", "approve-write", "trigger", "gitignore", "end"])
    r.add_argument("value", nargs="?")
    r.add_argument("--flow", default="audit")
    r.add_argument("--method", default="POST")
    r.add_argument("--finding", default=None)
    r.add_argument("--trigger-action", choices=["add", "remove"], default="add")
    r.set_defaults(fn=cmd_run)

    f = sub.add_parser("finding", help="validated findings ledger")
    f.add_argument("action", choices=["add", "list", "show", "set-status", "approve"])
    f.add_argument("id", nargs="?")
    f.add_argument("value", nargs="?")
    f.add_argument("--force", action="store_true")
    f.add_argument("--unit")
    f.add_argument("--status")
    f.add_argument("--severity")
    f.add_argument("--product")
    f.add_argument("--reason")
    f.add_argument("--ran")
    f.add_argument("--saw")
    f.add_argument("--ids")
    f.add_argument("--kinds")
    f.add_argument("--all", action="store_true")
    f.set_defaults(fn=cmd_finding)

    c = sub.add_parser("coverage", help="coverage cells: clean | findings | n/a | unverified | pending")
    c.add_argument("action", choices=["set", "show"])
    c.add_argument("--unit")
    c.add_argument("--product")
    c.add_argument("--state")
    c.add_argument("--note")
    c.add_argument("--reason")
    c.set_defaults(fn=cmd_coverage)

    sub.add_parser("ledger", help="completeness check (exit 1 when work remains)").set_defaults(fn=cmd_ledger, action="check")
    sub.add_parser("report", help="render .sentry-plugin/report.md").set_defaults(fn=cmd_report)

    rf = sub.add_parser("ref", help="read a reference file by name (or `list`)")
    rf.add_argument("name")
    rf.add_argument("--section")
    rf.set_defaults(fn=cmd_ref)

    fl = sub.add_parser("flow", help="print a flow's instructions (audit, init, apply, verify, org, policy, clean)")
    fl.add_argument("name")
    fl.set_defaults(fn=cmd_flow)

    dc = sub.add_parser("docs", help="fetch a live Sentry docs page or section")
    dc.add_argument("what", choices=["page"])
    dc.add_argument("page")
    dc.add_argument("--section")
    dc.add_argument("--list", action="store_true")
    dc.add_argument("--refresh", action="store_true")
    dc.set_defaults(fn=cmd_docs)

    cm = sub.add_parser("cli-map", help="sentry-cli v3 <-> sentry v4 command map")
    cm.add_argument("--intent")
    cm.add_argument("--v3")
    cm.set_defaults(fn=cmd_cli_map)
