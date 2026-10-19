"""Product applicability per unit from data/signals.tsv. The report keeps three different states:
audited-clean, n/a (with reason) and UNVERIFIED (could not look)."""
from __future__ import annotations

import os

from . import paths, util

SERVICE_ROLES = {"backend", "fullstack", "frontend", "worker", "serverless"}
SERVERLESS_DEPLOY = ("vercel", "netlify", "cloudflare", "aws-sam", "serverless-framework")


def load_table():
    rows = []
    with open(paths.data_path("signals.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            p = line.rstrip("\n").split("\t")
            while len(p) < 5:
                p.append("")
            rows.append({"product": p[0], "mode": p[1], "group": p[2], "when": p[3], "na_reason": p[4]})
    return rows


def _ecos():
    return paths.load_json_data("detect", "ecosystems.json")


def _term(term: str, unit: dict, ctx: dict):
    """Return (bool, evidence) for one key[:values] term (already stripped of '!')."""
    key, _, vals = term.partition(":")
    want = [v for v in vals.split(",") if v]
    if key == "always":
        return True, "always"
    if key == "notlib":
        return unit["role"] != "library", "role=%s" % unit["role"]
    if key == "role":
        return unit["role"] in want, "role=%s" % unit["role"]
    if key == "eco":
        return unit["ecosystem"] in want, "eco=%s" % unit["ecosystem"]
    if key == "fw":
        fws = [unit.get("framework")] + list(unit.get("overlays", []))
        return any(w in fws for w in want), "framework=%s" % unit.get("framework")
    if key == "platform":
        pl = unit.get("platforms") or []
        return any(w in pl for w in want), "platforms=%s" % ",".join(pl)
    if key == "sig":
        have = unit.get("signals", {})
        hit = [have[w][0] for w in want if have.get(w)]
        if not hit and ctx.get("repo_sig"):
            hit = [ctx["repo_sig"][w][0] for w in want if ctx["repo_sig"].get(w)]
        return bool(hit), "signal %s=%s" % (",".join(want), hit[0] if hit else "none")
    if key == "build":
        spec = _ecos().get(unit["ecosystem"], {})
        return bool(spec.get("bundled")), "bundled=%s" % bool(spec.get("bundled"))
    if key == "compiled":
        spec = _ecos().get(unit["ecosystem"], {})
        return bool(spec.get("compiled")), "compiled=%s" % bool(spec.get("compiled"))
    if key == "client":
        return unit["role"] in ("frontend", "mobile", "fullstack", "desktop"), "role=%s" % unit["role"]
    if key == "serverless":
        deploy = " ".join(unit.get("signals", {}).get("deploy", []))
        is_sl = unit["role"] == "serverless" or "cloudflare" in unit.get("overlays", []) or any(d in deploy for d in SERVERLESS_DEPLOY)
        return is_sl, "deploy=%s" % (deploy or "none")
    if key == "deploy":
        deploy = " ".join(unit.get("signals", {}).get("deploy", [])) + " " + " ".join(ctx.get("repo_deploy", []))
        return any(w in deploy for w in want), "deploy=%s" % (deploy.strip() or "none")
    if key == "org":
        return ctx.get("org_access", "none") != "none", "org_access=%s" % ctx.get("org_access", "none")
    if key == "url":
        urls = unit.get("signals", {}).get("public_url", [])
        return bool(urls), "public_url=%s" % (urls[0] if urls else "none")
    if key == "policy":
        inc = (ctx.get("policy", {}).get("products", {}) or {}).get("include", []) or []
        return any(w in inc for w in want), "policy include=%s" % ",".join(inc)
    return False, "unknown-key:%s" % key


def evaluate(expr: str, unit: dict, ctx: dict):
    expr = (expr or "").strip()
    if not expr:
        return True, ["(no condition)"]
    evid = []
    for alt in expr.split("|"):
        ok_all, ev = True, []
        for t in alt.split("&"):
            t = t.strip()
            neg = t.startswith("!")
            ok, e = _term(t.lstrip("!"), unit, ctx)
            ok = (not ok) if neg else ok
            ev.append(("not " if neg else "") + e)
            if not ok:
                ok_all = False
                break
        if ok_all:
            return True, ev
        evid = ev
    return False, evid


def plan(detect: dict, policy: dict | None, org_access: str) -> dict:
    table = load_table()
    policy = policy or {}
    repo_deploy = [d["value"] for d in (detect.get("ci") or {}).get("deploy", [])]
    ctx = {"policy": policy, "org_access": org_access, "repo_sig": {}, "repo_deploy": repo_deploy}
    prod_pol = policy.get("products") or {}
    excl = set(prod_pol.get("exclude") or [])
    incl = set(prod_pol.get("include") or [])
    units_out = []
    for u in detect["units"]:
        cells = {}
        for row in table:
            if row["mode"] == "org":
                continue
            pid = row["product"]
            if pid in excl:
                cells[pid] = {"state": "n/a", "group": row["group"], "reason": "excluded by policy"}
                continue
            if pid in incl and row["mode"] == "cond":
                cells[pid] = {"state": "applicable", "group": row["group"], "evidence": ["included by policy"]}
                continue
            ok, ev = evaluate(row["when"], u, ctx)
            if ok:
                cells[pid] = {"state": "applicable", "group": row["group"], "evidence": ev}
            elif pid == "uptime" and u["role"] in SERVICE_ROLES:
                cells[pid] = {"state": "unknown", "group": row["group"], "reason": row["na_reason"]}
            else:
                cells[pid] = {"state": "n/a", "group": row["group"], "reason": row["na_reason"] or ("; ".join(ev))}
        mods = []
        if u["ecosystem"] == "apple":
            pl = u.get("platforms") or []
            if "macos" in pl:
                mods.append("platforms/apple-macos")
            if any(x in pl for x in ("ios", "tvos", "visionos", "watchos")) or not pl:
                mods.append("platforms/apple-ios")
        elif u.get("framework_module"):
            mods.append(u["framework_module"])
        mods.append("platforms/" + u["ecosystem"])
        for pid, c in cells.items():
            if c["state"] == "applicable":
                mods.append("products/" + pid)
        from . import refs
        seen, ordered, missing = set(), [], []
        for m in mods:
            if m in seen:
                continue
            seen.add(m)
            (ordered if refs._resolve(m) else missing).append(m)
        units_out.append({
            "id": u["id"], "root": u["root"], "role": u["role"], "ecosystem": u["ecosystem"], "framework": u.get("framework"),
            "sentry_status": u["sentry"]["status"], "library": u["library"], "products": cells, "modules": ordered, "modules_missing": missing,
        })
    org_cells = {}
    for row in table:
        if row["mode"] != "org":
            continue
        ok, ev = evaluate(row["when"], {"role": "backend", "ecosystem": "", "signals": {}}, ctx)
        org_cells[row["product"]] = {"state": "applicable", "group": "org", "evidence": ev} if ok else {"state": "unverified", "group": "org", "reason": row["na_reason"]}
    return {"schema": 1, "org_access": org_access, "units": units_out, "org": org_cells}


def baseline_extras(detect_unit: dict) -> dict:
    """Init flow: which applicable products form the pre-selected base set vs proposed extras."""
    base = {"core", "errors", "releases", "privacy", "debug-artifacts", "tracing"}
    return {"base": sorted(base)}
