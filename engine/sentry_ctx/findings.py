"""Findings ledger: validated at write time so the auditor -> implementer handoff cannot drift."""
from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.parse

from . import miniyaml, paths, tokens, util

SEVERITIES = ["P0", "P1", "P2", "P3"]
KINDS = ["fix", "add", "remove", "org-write", "manual"]
STATUSES = ["open", "approved", "applied", "verified", "skipped", "blocked", "waived", "unverified"]
REQUIRES = {"token", "org-write", "deploy", "tty", "policy"}
RUNGS = ["R0", "R1", "R2", "R3", "R4", "R5", "R6"]
DOC_HOSTS = {"docs.sentry.io", "develop.sentry.dev", "cli.sentry.dev", "skills.sentry.dev", "mcp.sentry.dev", "spotlightjs.com", "sentry.io", "developers.cloudflare.com"}
DOC_GITHUB_PREFIX = "https://github.com/getsentry/"
SECTIONS = ["what", "why", "evidence_text", "fix", "verify_text", "source"]
SECTION_TITLES = {"what": "What", "why": "Why it matters here", "evidence_text": "Evidence", "fix": "Fix", "verify_text": "Verify", "source": "Source"}
TRANSITIONS = {
    "open": {"approved", "skipped", "waived", "blocked", "unverified"},
    "approved": {"applied", "blocked", "skipped", "open"},
    "applied": {"verified", "unverified", "blocked", "approved"},
    "unverified": {"verified", "waived", "approved", "blocked"},
    "blocked": {"approved", "open", "skipped"},
    "skipped": {"open"},
    "waived": {"open"},
    "verified": set(),
}
_cache: dict = {}


def checks():
    if "checks" not in _cache:
        rows = {}
        with open(paths.data_path("checks.tsv"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                p = line.rstrip("\n").split("\t")
                rows[p[0]] = {"id": p[0], "product": p[1], "severity": p[2], "applies": p[3], "method": p[4], "passes": p[5] if len(p) > 5 else ""}
        _cache["checks"] = rows
    return _cache["checks"]


def products():
    if "products" not in _cache:
        _cache["products"] = paths.load_json_data("products.json")
    return _cache["products"]


def fdir(root):
    return os.path.join(paths.state_dir(root), "findings")


def _all_files(root):
    out = []
    base = fdir(root)
    for dp, dn, fn in os.walk(base):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for f in fn:
            if re.match(r"^F-\d{3,}-", f) and f.endswith(".md"):
                out.append(os.path.join(dp, f))
    return sorted(out)


def _load_file(path):
    fm, body = miniyaml.split_front_matter(util.read_text(path))
    return fm, body


def load_all(root):
    res = []
    for p in _all_files(root):
        fm, body = _load_file(p)
        if fm.get("id"):
            fm["_path"] = os.path.relpath(p, root)
            res.append(fm)
    return res


def find_path(root, fid):
    for p in _all_files(root):
        if os.path.basename(p).startswith(fid + "-"):
            return p
    return None


def _reserve_id(root):
    d = os.path.join(fdir(root), ".ids")
    os.makedirs(d, exist_ok=True)
    n = 1
    existing = [int(m.group(1)) for p in _all_files(root) for m in [re.match(r"F-(\d+)-", os.path.basename(p))] if m]
    n = max(existing + [0]) + 1
    while True:
        try:
            fd = os.open(os.path.join(d, "F-%03d" % n), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return "F-%03d" % n
        except FileExistsError:
            n += 1


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "finding"


class Invalid(util.EngineError):
    def __init__(self, errors):
        super().__init__("invalid finding:\n  - " + "\n  - ".join(errors), 3)
        self.errors = errors


def validate(root, f: dict, units):
    errs, warns = [], []
    unit = f.get("unit")
    if not unit or (unit not in units and unit not in ("_org", "_links")):
        errs.append("unit %r is not a detected unit (%s), _org or _links" % (unit, ", ".join(sorted(units)) or "none; run steer first"))
    chk = f.get("check")
    cat = checks()
    if chk in cat:
        want = cat[chk]["product"]
        if f.get("product") and f["product"] != want:
            warns.append("product %r replaced by %r (owner of %s)" % (f["product"], want, chk))
        f["product"] = want
        f.setdefault("severity", cat[chk]["severity"].split("/")[0])
        f["severity_default"] = cat[chk]["severity"]
    elif chk and chk.startswith("x."):
        if f.get("product") not in products():
            errs.append("product %r unknown (known: %s)" % (f.get("product"), ", ".join(sorted(products()))))
    else:
        errs.append("check %r is not in the catalog (data/checks.tsv); use an `x.<slug>` id for an unlisted check" % chk)
    if f.get("severity") not in SEVERITIES:
        errs.append("severity must be one of P0..P3")
    kind = f.get("kind")
    if kind not in KINDS:
        errs.append("kind must be one of " + "|".join(KINDS))
    try:
        c = float(f.get("confidence", 0.8))
        if not 0 <= c <= 1:
            raise ValueError
        f["confidence"] = c
    except (TypeError, ValueError):
        errs.append("confidence must be a number in [0,1]")
    st = f.setdefault("status", "open")
    if st not in ("open", "unverified"):
        errs.append("a new finding must start as open or unverified")
    files = f.get("files") or []
    if not isinstance(files, list):
        errs.append("files must be a list")
        files = []
    clean_files = []
    for p in files:
        rel = util.rel_inside(root, str(p))
        if not rel:
            errs.append("file %r is outside the repo (or absolute)" % p)
        else:
            clean_files.append(rel)
    f["files"] = clean_files
    if kind in ("fix", "add", "remove") and not clean_files:
        errs.append("kind=%s needs files (the implementer's allowed touch set)" % kind)
    req = f.get("requires") or []
    for r in req:
        if r.split(":")[0] not in REQUIRES:
            errs.append("requires entry %r unknown (%s)" % (r, "|".join(sorted(REQUIRES))))
    f["requires"] = req
    ver = f.get("verify") or {}
    if ver:
        if ver.get("rung") not in RUNGS:
            errs.append("verify.rung must be R0..R6")
    else:
        f["verify"] = {"rung": "R0", "how": "static", "expect": ""}
    docs = f.get("docs") or []
    for u in docs:
        pu = urllib.parse.urlparse(str(u))
        ok = pu.scheme == "https" and (pu.hostname in DOC_HOSTS or str(u).startswith(DOC_GITHUB_PREFIX))
        if not ok:
            errs.append("docs URL %r is outside the allow-list (%s, github.com/getsentry/...)" % (u, ", ".join(sorted(DOC_HOSTS))))
    f["docs"] = docs
    if kind == "org-write":
        ow = f.get("org_write")
        if not isinstance(ow, dict) or not (ow.get("cli") or (ow.get("method") and ow.get("path"))):
            errs.append("kind=org-write needs org_write {method, path, effect} for a REST call, or {cli, effect} for a CLI subcommand (e.g. cli: \"project create ORG/name:platform --team T\")")
        elif ow.get("cli"):
            words = str(ow["cli"]).split()
            if words[:1] == ["sentry"]:
                words = words[1:]
            ow["cli"] = " ".join(words)
            if len(words) < 2 or words[0] in ("auth", "cli", "init") or (words[0], words[1]) in (("issue", "explain"), ("issue", "plan")):
                errs.append("org_write.cli %r is not an allowed Sentry write (Seer runs, auth and CLI self-management are never findings)" % ow["cli"])
            if "org-write" not in f["requires"]:
                f["requires"].append("org-write")
        elif str(ow["method"]).upper() not in ("POST", "PUT", "PATCH", "DELETE"):
            errs.append("org_write.method must be POST|PUT|PATCH|DELETE")
        else:
            ow["method"] = str(ow["method"]).upper()
            if "org-write" not in f["requires"]:
                f["requires"].append("org-write")
    else:
        f.setdefault("org_write", None)
    ev = f.get("evidence") or {}
    if st == "unverified":
        if not f.get("reason"):
            errs.append("status=unverified needs `reason` (why it could not be checked)")
    else:
        if not (isinstance(ev, dict) and str(ev.get("ran", "")).strip() and str(ev.get("saw", "")).strip()):
            errs.append("evidence.ran and evidence.saw are required: a finding without something the auditor ran/read is a guess")
    if not f.get("title"):
        errs.append("title is required (one line)")
    f.setdefault("sdk", None)
    f.setdefault("fix_ref", None)
    return errs, warns


def add(root, f: dict, units, force=False):
    raw = json.dumps(f)
    leaked = tokens.has_token(raw)
    f = tokens.mask_deep(f)
    errs, warns = validate(root, f, units)
    if errs:
        raise Invalid(errs)
    if not force:
        for ex in load_all(root):
            if ex.get("status") in ("open", "approved", "applied") and ex.get("unit") == f["unit"] and ex.get("check") == f["check"] and sorted(ex.get("files", [])) == sorted(f["files"]) and (f["files"] or ex.get("title") == f.get("title")):
                raise util.EngineError("duplicate of %s (same unit, check, files); update it instead or pass --force" % ex["id"], 4)
    fid = _reserve_id(root)
    f["id"] = fid
    f["created_at"] = util.now_iso()
    order = ["id", "unit", "product", "check", "severity", "confidence", "status", "kind", "title", "files", "requires", "fix_ref", "verify", "docs", "sdk", "org_write", "evidence", "reason", "severity_default", "created_at"]
    fm = {k: f[k] for k in order if k in f and f[k] is not None}
    fm.setdefault("org_write", None)
    ev, vf = f.get("evidence") or {}, f.get("verify") or {}
    derived = {
        "evidence_text": "ran: %s\nsaw: %s" % (ev.get("ran", ""), ev.get("saw", "")) if ev else "",
        "verify_text": "%s: %s -> expect %s" % (vf.get("rung", ""), vf.get("how", ""), vf.get("expect", "")) if vf else "",
    }
    body = ""
    for key in SECTIONS:
        body += "## %s\n%s\n\n" % (SECTION_TITLES[key], (f.get(key) or derived.get(key) or "").strip() or "(none)")
    d = os.path.join(fdir(root), f["unit"])
    p = os.path.join(d, "%s-%s-%s.md" % (fid, f["product"], _slug(f["check"].split(".", 1)[-1] if "." in f["check"] else f["check"])))
    util.write_text(p, miniyaml.join_front_matter(fm, body))
    return {"id": fid, "path": os.path.relpath(p, root), "warnings": warns + (["token-shaped text was masked"] if leaked else [])}


def set_status(root, fid, status, reason=None, ran=None, saw=None, rung=None):
    p = find_path(root, fid)
    if not p:
        raise util.EngineError("no such finding: " + fid)
    fm, body = _load_file(p)
    cur = fm.get("status")
    if status not in STATUSES:
        raise util.EngineError("status must be one of " + ", ".join(STATUSES))
    if status not in TRANSITIONS.get(cur, set()) and status != cur:
        raise util.EngineError("illegal transition %s -> %s (allowed: %s)" % (cur, status, ", ".join(sorted(TRANSITIONS.get(cur, set()))) or "none"))
    if status == "verified":
        if not (ran and ran.strip() and saw and saw.strip()):
            raise util.EngineError("verified needs --ran and --saw (what was run, what was seen)")
        rung = (rung or "").strip().upper()
        if rung not in RUNGS:
            raise util.EngineError("verified needs --rung R0..R6: the highest rung your proof actually reached")
        vf = fm.get("verify")
        need = vf.get("rung") if isinstance(vf, dict) else None
        if need not in RUNGS:
            raise util.EngineError("this finding has no valid verify.rung (found %r): fix the finding file before verifying it" % (need,))
        if RUNGS.index(rung) < RUNGS.index(need):
            raise util.EngineError("this finding needs rung %s and you reached %s: record it as unverified with --reason (what is missing, and %s as the highest rung reached), or verify again at %s"
                                   % (need, rung, rung, need))
    if status in ("waived", "skipped", "blocked", "unverified") and not reason:
        raise util.EngineError("%s needs --reason" % status)
    fm["status"] = status
    if rung and status != "verified":
        fm["reached_rung"] = str(rung).strip().upper()[:2]  # the highest rung reached, kept for an unverified finding
    if reason:
        fm["reason"] = tokens.mask(reason)
    if ran and saw:
        proofs = fm.get("proof") or {}
        fm["proof"] = {"ran": tokens.mask(ran), "saw": tokens.mask(saw), "at": util.now_iso(), "rung": rung or fm.get("verify", {}).get("rung")}
    util.write_text(p, miniyaml.join_front_matter(fm, body))
    return {"id": fid, "status": status}


def approve(root, ids=None, severities=None, all_open=False, kinds=None):
    changed = []
    for fm in load_all(root):
        if fm.get("status") != "open":
            continue
        if ids and fm["id"] not in ids:
            continue
        if severities and fm.get("severity") not in severities:
            continue
        if kinds and fm.get("kind") not in kinds:
            continue
        if not (ids or severities or all_open):
            continue
        set_status(root, fm["id"], "approved")
        changed.append(fm["id"])
    return changed


# ---------- coverage ----------

def cov_path(root):
    return os.path.join(paths.state_dir(root), "coverage.json")


def cov_load(root):
    return util.read_json(cov_path(root), {"cells": {}}) or {"cells": {}}


def cov_init(root, plan):
    cov = cov_load(root)
    cells = cov["cells"]
    for u in plan["units"]:
        for pid, c in u["products"].items():
            key = "%s/%s" % (u["id"], pid)
            if c["state"] == "applicable":
                cells.setdefault(key, {"state": "pending"})
            elif c["state"] == "n/a":
                cells[key] = {"state": "n/a", "reason": c.get("reason", "")}
            else:
                cells[key] = {"state": "unverified", "reason": c.get("reason", "unknown applicability: ask the user")} if c["state"] == "unknown" else cells.setdefault(key, {"state": "pending"})
    for pid, c in plan.get("org", {}).items():
        key = "_org/%s" % pid
        if c["state"] == "applicable":
            cells.setdefault(key, {"state": "pending"})
        else:
            cells[key] = {"state": "unverified", "reason": c.get("reason", "no org access")}
    lk = plan.get("links")
    if lk:
        if lk["state"] == "applicable":
            cells.setdefault("_links/links", {"state": "pending"})
        else:
            cells["_links/links"] = {"state": "n/a", "reason": lk.get("reason", "")}
    util.write_json(cov_path(root), cov)
    return cov


def cov_set(root, unit, product, state, note=None, reason=None):
    if state not in ("clean", "findings", "n/a", "unverified", "pending"):
        raise util.EngineError("state must be clean|findings|n/a|unverified|pending")
    if state == "unverified" and not reason:
        raise util.EngineError("unverified needs --reason")
    key = "%s/%s" % (unit, product)
    cov = cov_load(root)
    if key not in cov["cells"]:
        raise util.EngineError("no coverage cell %s (run steer/coverage init first)" % key)
    if state == "clean":
        bad = [f["id"] for f in load_all(root) if f.get("unit") == unit and f.get("product") == product and f.get("status") in ("open", "approved", "applied")]
        if bad:
            raise util.EngineError("cannot mark clean: open findings %s" % ", ".join(bad))
    cell = {"state": state}
    if note:
        cell["note"] = tokens.mask(note)
    if reason:
        cell["reason"] = tokens.mask(reason)
    cov["cells"][key] = cell
    util.write_json(cov_path(root), cov)
    return {key: cell}


def ledger_check(root):
    cov = cov_load(root)
    allf = load_all(root)
    pending = sorted(k for k, c in cov["cells"].items() if c.get("state") == "pending")
    inconsistent = []
    for k, c in cov["cells"].items():
        unit, _, product = k.partition("/")
        has_open = any(f.get("unit") == unit and f.get("product") == product and f.get("status") in ("open", "approved", "applied") for f in allf)
        if c.get("state") == "clean" and has_open:
            inconsistent.append(k + ": marked clean but has open findings")
    unproven = sorted(f["id"] for f in allf if f.get("status") == "applied")
    from . import runstate
    st = runstate.load(root) or {}
    trig = [t["path"] for t in runstate.live_triggers(root, st)]
    return {"ok": not (pending or inconsistent or unproven or trig), "pending_cells": pending, "inconsistent": inconsistent, "applied_unverified": unproven, "live_triggers": trig,
            "counts": {s: sum(1 for f in allf if f.get("status") == s) for s in STATUSES}}


# ---------- report ----------

def _ow_call(ow):
    # a REST write has method + path; a CLI write has only the subcommand
    if ow.get("cli"):
        return "sentry " + ow["cli"]
    return "%s %s" % (ow.get("method"), ow.get("path"))


def report(root, plan):
    allf = load_all(root)
    cov = cov_load(root)
    out = ["# Sentry audit report", "", "_Generated %s by sentry-ctx. Three different states are never merged: **clean**, **n/a** and **UNVERIFIED**._" % util.now_iso(), ""]
    by_sev = {s: [f for f in allf if f.get("severity") == s and f.get("status") not in ("skipped",)] for s in SEVERITIES}
    out.append("## Summary")
    out.append("")
    out.append("| Severity | Open | Total |")
    out.append("|---|---|---|")
    for s in SEVERITIES:
        out.append("| %s | %d | %d |" % (s, sum(1 for f in by_sev[s] if f.get("status") in ("open", "approved")), len(by_sev[s])))
    out.append("")
    out.append("## Coverage")
    out.append("")
    units = sorted({k.split("/")[0] for k in cov["cells"]})
    for u in units:
        out.append("### %s" % u)
        out.append("")
        out.append("| Product | State | Detail |")
        out.append("|---|---|---|")
        for k in sorted(k for k in cov["cells"] if k.startswith(u + "/")):
            c = cov["cells"][k]
            prod = k.split("/", 1)[1]
            fl = [f for f in allf if f.get("unit") == u and f.get("product") == prod and f.get("status") not in ("skipped",)]
            state = c["state"]
            if state in ("clean", "pending", "findings") and fl:
                state = "findings (%d)" % len(fl)
            label = {"clean": "clean", "n/a": "n/a", "unverified": "**UNVERIFIED**", "pending": "**PENDING**"}.get(state, state)
            out.append("| %s | %s | %s |" % (prod, label, (c.get("reason") or c.get("note") or "").replace("|", "/")))
        out.append("")
    for s in ("P0", "P1"):
        if by_sev[s]:
            out.append("## %s findings" % s)
            out.append("")
            for f in sorted(by_sev[s], key=lambda x: x["id"]):
                out.append("### %s [%s/%s] %s" % (f["id"], f["unit"], f["product"], f.get("title", "")))
                out.append("")
                out.append("- check `%s`, kind `%s`, status `%s`, confidence %s" % (f["check"], f["kind"], f["status"], f.get("confidence")))
                out.append("- files: %s" % (", ".join(f.get("files", [])) or "none"))
                ev = f.get("evidence") or {}
                if ev:
                    out.append("- ran: `%s` / saw: `%s`" % (str(ev.get("ran", ""))[:140], str(ev.get("saw", ""))[:140]))
                if f.get("org_write"):
                    ow = f["org_write"]
                    out.append("- org write: `%s` (%s)" % (_ow_call(ow), ow.get("effect", "")))
                if f.get("docs"):
                    out.append("- docs: " + ", ".join(f["docs"]))
                out.append("")
    rest = [f for s in ("P2", "P3") for f in by_sev[s]]
    if rest:
        out.append("## P2 / P3 (counts per product)")
        out.append("")
        counts: dict = {}
        for f in rest:
            counts.setdefault(f["product"], {"P2": 0, "P3": 0})[f["severity"]] += 1
        out.append("| Product | P2 | P3 |")
        out.append("|---|---|---|")
        for p, c in sorted(counts.items()):
            out.append("| %s | %d | %d |" % (p, c["P2"], c["P3"]))
        out.append("")
        out.append("Details: `.sentry-plugin/findings/`.")
        out.append("")
    ow = [f for f in allf if f.get("kind") == "org-write" and f.get("status") in ("open", "approved")]
    if ow:
        out.append("## Org writes awaiting separate approval")
        out.append("")
        for f in ow:
            o = f["org_write"]
            out.append("- %s: `%s` : %s" % (f["id"], _ow_call(o), o.get("effect", "")))
        out.append("")
    text = "\n".join(out) + "\n"
    util.write_text(os.path.join(paths.state_dir(root), "report.md"), text)
    return text
