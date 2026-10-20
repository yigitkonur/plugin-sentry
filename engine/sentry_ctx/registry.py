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
        if os.environ.get("SENTRY_PLUGIN_POLICY_ANSWERS"):
            raise util.EngineError("SENTRY_PLUGIN_POLICY_ANSWERS is set: the operator supplied the policy. Run `sentry-ctx policy from-env`.", 5)
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
        util.emit(runstate.start(root, args.flow, units=sorted(u["id"] for u in _detect(args)["units"])))
    elif a == "status":
        st = runstate.load(root)
        util.emit(st if st else {"active": False})
    elif a == "phase":
        util.emit(runstate.set_phase(root, args.value))
    elif a == "approve-write":
        util.emit(runstate.approve_write(root, args.method, args.value, args.finding, cli=args.cli))
    elif a == "adopt":
        util.emit(runstate.adopt(root))
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
def cmd_verify(args):
    from . import verify, policy as pol
    root = _root(args)
    a = args.action
    if a == "marker":
        print(verify.new_marker(root))
    elif a == "wait":
        if not (args.org and args.project and args.marker):
            raise util.EngineError("verify wait needs --org, --project and --marker")
        r = verify.wait(root, args.org, args.project, args.marker, timeout=args.timeout, interval=args.interval)
        util.emit(r)
        return 0 if r["arrived"] else 1
    elif a == "scan":
        if not args.file:
            raise util.EngineError("verify scan needs a path to an event JSON file")
        ev = util.read_json(args.file)
        if not isinstance(ev, dict):
            raise util.EngineError("not an event JSON object: " + args.file)
        ev = ev.get("event", ev) if isinstance(ev.get("event"), dict) else ev
        r = verify.scan(ev, pol.load(root))
        util.emit(r)
        return 0 if r["ok"] else 1


def cmd_cli_port(args):
    from . import cliport
    det = _detect(args)
    res = cliport.port_repo(det)
    if args.json:
        util.emit(res)
        return
    print("%d sentry-cli 3.x call(s) found" % res["count"])
    for r in res["rows"]:
        print("%s:%s\n  v3: %s\n  v4: %s" % (r["file"], r["line"], r["v3"], r["v4"] or "(no known counterpart)"))
        for n in r["notes"]:
            print("      - " + n)
    print(res["also"] + "; reference: " + res["reference"])


def cmd_checks(args):
    from . import findings
    want = {x for v in (args.product or []) for x in v.split(",") if x}
    rows = [c for c in findings.checks().values() if not want or c["product"] in want]
    if args.json:
        util.emit(rows)
        return
    for c in rows:
        print("%s\t%s\t%s\t[%s]\t%s" % (c["id"], c["severity"].strip("*"), c["applies"], c["method"], c["passes"]))
    if not rows:
        print("no checks for: %s (products with checks: %s)" % (", ".join(sorted(want)), ", ".join(sorted({c["product"] for c in findings.checks().values()}))))


def cmd_org(args):
    from . import org
    root = _root(args)
    projects = [x for v in (args.project or []) for x in v.split(",") if x] or None
    if args.action == "focus":
        util.emit(org.focus_cmd(root, args.org, projects))
    elif args.action == "probe":
        res = org.probe(root, args.what or "all", args.org, projects)
        if args.record:
            res["recorded"] = org.record(root, res)
        if args.json:
            util.emit(res)
        else:
            print(org.render(res))
            if args.record:
                print("recorded: " + json.dumps(res["recorded"], ensure_ascii=False))
    elif args.action == "apply":
        if not args.what:
            raise util.EngineError("usage: org apply <finding id> [--run]")
        util.emit(org.apply_write(root, args.what, run=args.run))


def cmd_stale(args):
    from . import stale
    root = _root(args)
    det = _detect(args)
    out = []
    for u in det["units"]:
        if args.unit and u["id"] != args.unit:
            continue
        out.append(stale.scan_unit(u, root))
    util.emit(out)


def cmd_clean(args):
    from . import clean
    root = _root(args)
    keep = args.keep or "none"
    if keep not in ("none", "policy", "all"):
        raise util.EngineError("--keep must be none|policy|all")
    p = clean.plan(root, keep)
    if not args.yes:
        p["dry_run"] = True
        util.emit(p)
        return
    util.emit(clean.execute(root, keep, args.gitignore_line))


def cmd_ref(args):
    from . import refs
    if args.name == "list":
        util.emit(refs.list_names(args.target or args.section or ""))
    elif args.name == "verify":
        from . import refcheck
        if args.file:
            r = refcheck.verify_file(args.file, args.kind)
            util.emit([r])
            return 0 if r["ok"] else 1
        targets = [args.target] if args.target else [n for n in refs.list_names() if n.startswith(("forge/products/", "forge/platforms/"))]
        bad = 0
        out = []
        for t in targets:
            t = t[len("forge/"):] if t.startswith("forge/") else t
            r = refcheck.verify(t)
            out.append(r)
            bad += 0 if r.get("ok", True) else 1
        util.emit(out)
        return 1 if bad else 0
    else:
        print(refs.read(args.name, args.section))


def cmd_flow(args):
    from . import refs
    text = refs.flow(args.name)
    src = os.environ.get("SENTRY_PLUGIN_POLICY_ANSWERS")
    if src and args.name in ("preamble", "policy", "start", "audit", "init", "org"):
        text = ("> **HEADLESS POLICY: `SENTRY_PLUGIN_POLICY_ANSWERS` is set (`%s`).** Run `sentry-ctx policy from-env` for the policy and do not ask or decide it yourself;\n"
                "> `sentry-ctx policy set` is refused while it is set. No human is available: every approval gate is \"Report only\" unless the prompt that started this session says otherwise.\n\n") % src + text
    print(text)


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
    r.add_argument("action", choices=["start", "status", "phase", "approve-write", "adopt", "trigger", "gitignore", "end"])
    r.add_argument("value", nargs="?")
    r.add_argument("--flow", default="audit")
    r.add_argument("--method", default="POST")
    r.add_argument("--finding", default=None)
    r.add_argument("--cli", default=None, help='approve a CLI subcommand instead of a REST call, e.g. "release create"')
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

    vf = sub.add_parser("verify", help="R3/R5: marker, wait for a marked event, scan an event against the policy")
    vf.add_argument("action", choices=["marker", "wait", "scan"])
    vf.add_argument("file", nargs="?")
    vf.add_argument("--org")
    vf.add_argument("--project")
    vf.add_argument("--marker")
    vf.add_argument("--timeout", type=int, default=120)
    vf.add_argument("--interval", type=int, default=3)
    vf.set_defaults(fn=cmd_verify)

    og = sub.add_parser("org", help="org-side probes (GET-only) and approved org writes: focus | probe [row|id|all] | apply <finding> [--run]")
    og.add_argument("action", choices=["focus", "probe", "apply"])
    og.add_argument("what", nargs="?")
    og.add_argument("--org")
    og.add_argument("--project", action="append", help="project slug(s) of this repo in the org, comma separated or repeated")
    og.add_argument("--record", action="store_true", help="probe: add candidates as open _org findings and set the _org coverage cells")
    og.add_argument("--run", action="store_true", help="apply: perform the write (only if approved in this run)")
    og.add_argument("--json", action="store_true")
    og.set_defaults(fn=cmd_org)

    cp = sub.add_parser("cli-port", help="port sentry-cli 3.x calls found in CI files and scripts to the sentry v4 CLI (exact commands)")
    cp.add_argument("--json", action="store_true")
    cp.set_defaults(fn=cmd_cli_port)

    ck = sub.add_parser("checks", help="check ids with default severity, applicability and the passing condition (data/checks.tsv)")
    ck.add_argument("--product", action="append", help="product id(s), comma separated or repeated")
    ck.add_argument("--json", action="store_true")
    ck.set_defaults(fn=cmd_checks)

    st = sub.add_parser("stale", help="removed/renamed SDK options in a unit's init and config files (data/stale-apis)")
    st.add_argument("--unit")
    st.add_argument("--include-tests", action="store_true")
    st.set_defaults(fn=cmd_stale)

    cl = sub.add_parser("clean", help="remove run artifacts (dry-run unless --yes)")
    cl.add_argument("--yes", action="store_true")
    cl.add_argument("--keep", default=None, help="none | policy | all")
    cl.add_argument("--gitignore-line", default="keep", choices=["keep", "remove"])
    cl.set_defaults(fn=cmd_clean)

    rf = sub.add_parser("ref", help="read a reference file by name (or `list`)")
    rf.add_argument("name", help="a reference name, or `list [prefix]`, or `verify [name]`")
    rf.add_argument("target", nargs="?")
    rf.add_argument("--section")
    rf.add_argument("--file", help="verify: check a staged module file by path (needs --kind product|platform)")
    rf.add_argument("--kind", choices=["product", "platform"])
    rf.set_defaults(fn=cmd_ref)

    fl = sub.add_parser("flow", help="print a flow's instructions (preamble, policy, start, audit, init, apply, verify, org)")
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
