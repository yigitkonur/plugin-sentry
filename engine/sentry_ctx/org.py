"""Org-side probes and approved org writes.

Every probe is GET-only by construction: the only HTTP method this module ever builds for a probe is GET (`_get`), through
`sentry api` with SENTRY_NO_CACHE=1, so the stored CLI login is reused and never read. Probes return observations and
*candidate* findings; the auditor judges them and records findings. Writes live in `apply_write` and run only for a call the
user approved in the current run (runstate approved_writes).

Payloads are not stored raw: each probe keeps a small normalized summary under .sentry-plugin/evidence/ (masked).
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse

from . import cli_tools, paths, runstate, tokens, util

EXIT_UNVERIFIED = {10: "auth: the CLI login is missing or expired", 11: "auth: the CLI login is missing or expired",
                   12: "auth: the CLI login is missing or expired", 13: "host trust: the CLI refused to route to this host"}

ROWS = [
    (1, "identity", "_org/org", "Organization, region, projects", ["org.projects", "core.dsn-region"]),
    (2, "keys", "_org/quota", "Client keys (DSNs) and rate limits", ["quota.controls"]),
    (3, "filters", "_org/quota", "Inbound filters", ["err.noise", "quota.controls"]),
    (4, "scrubbing", "_org/org", "Server-side data scrubbing", ["priv.server-scrub"]),
    (5, "spike", "_org/quota", "Spike protection and sampling mode", ["quota.controls"]),
    (6, "alerting", "_org/alerts", "Detectors and workflows (alerts)", ["alert.coverage"]),
    (7, "monitors", "_org/alerts", "Cron and uptime monitors", ["cron.coverage", "uptime.fit"]),
    (8, "releases", "_org/org", "Releases, commits, deploys, SCM", ["rel.commits-deploys", "err.ownership"]),
    (9, "artifacts", "_org/org", "Source maps and debug files uploaded", ["rel.sourcemaps", "rel.debug-files"]),
    (10, "stacktraces", "_org/org", "Stack-trace health on recent events", ["rel.resolve"]),
    (11, "ownership", "_org/org", "Ownership rules and code owners", ["err.ownership"]),
    (12, "event-sanity", "_org/org", "Environment, release and SDK mix on recent events", ["core.environment", "core.release"]),
    (13, "usage", "_org/quota", "30-day usage and dropped outcomes", ["quota.size-billed"]),
    (14, "seer", "_org/seer", "Seer prerequisites and settings", ["seer.prereq"]),
    (15, "replays", "_org/org", "Replay inventory", ["replay.rates"]),
    (16, "flags", "_org/org", "Feature-flag log (webhook coverage)", ["flags.integration"]),
    (17, "integrations", "_org/org", "Installed integrations", ["org.projects"]),
]
ROW_BY_KEY = {}
for _r in ROWS:
    ROW_BY_KEY[str(_r[0])] = _r
    ROW_BY_KEY[_r[1]] = _r

BROWSER_ROLES = ("frontend", "fullstack")
NATIVE_PLATFORMS = ("apple", "cocoa", "ios", "macos", "android", "native", "unity", "unreal", "dotnet-maui", "flutter", "dart", "react-native", "java-android")


# ---------------------------------------------------------------- plumbing
def _get(path, fields=None):
    """GET through `sentry api`. Returns (state, data, reason): state in ok | unverified | na."""
    if not cli_tools.sentry_bin():
        return "unverified", None, "no sentry v4 CLI installed"
    r = None
    for _ in range(2):  # one retry on a transient API failure (exit 31)
        full = path
        if fields:
            full += ("&" if "?" in path else "?") + urllib.parse.urlencode(fields, doseq=True)
        r = cli_tools.api(full, "GET")
        if r["rc"] != 31:
            break
    if r["rc"] == 0:
        return "ok", r["data"], ""
    text = (r.get("err") or "") + " " + (r.get("raw") or "")
    m = re.search(r"HTTP (\d{3})", text)
    code = m.group(1) if m else None
    if r["rc"] in EXIT_UNVERIFIED:
        return "unverified", None, EXIT_UNVERIFIED[r["rc"]]
    if code == "403":
        need = re.search(r"scope[^\"\n]{0,60}", text)
        return "unverified", None, "403: the login lacks permission for GET %s%s" % (path.split("?")[0], (" (" + need.group(0).strip() + ")") if need else "")
    if code == "404":
        return "na", None, "404: GET %s is not available on this org/plan" % path.split("?")[0]
    return "unverified", None, "exit %s%s: %s" % (r["rc"], " HTTP " + code if code else "", tokens.clip(text.strip(), 160))


def _list(path, fields=None):
    f = dict(fields or {})
    f.setdefault("per_page", "100")
    st, data, why = _get(path, f)
    trunc = st == "ok" and isinstance(data, list) and len(data) >= int(f["per_page"])
    return st, data, why, trunc


class Ctx:
    def __init__(self, root, org=None, projects=None):
        self.root = root
        self.saved = util.read_json(os.path.join(paths.state_dir(root), "org.json"), {}) or {}
        self.detect = util.read_json(os.path.join(paths.state_dir(root), "detect.json"), {}) or {}
        if not self.detect.get("units"):
            try:
                from .detect import core
                self.detect = core.detect(root)
            except Exception:
                self.detect = {}
        self.policy = {}
        try:
            from . import policy as _p
            self.policy = _p.load(root) or {}
        except Exception:
            pass
        self.org = org or self.saved.get("org")
        self.want_projects = projects or self.saved.get("projects") or []
        self.org_obj = None
        self.projects_all = None
        self.focus = None
        self.focus_how = ""
        self.evidence = {}

    # ---- org + projects
    def resolve_org(self):
        if self.org:
            return None
        st = cli_tools.auth_status()
        orgs = st.get("orgs") or []
        if len(orgs) == 1:
            self.org = orgs[0]
            return None
        return "no organization chosen: pass --org <slug> (logged-in orgs: %s)" % (", ".join(orgs) or "none")

    def load_org(self):
        if self.org_obj is None:
            st, data, why = _get("/organizations/%s/" % self.org)
            self.org_obj = {"state": st, "data": data if isinstance(data, dict) else {}, "why": why}
        return self.org_obj

    def load_projects(self):
        if self.projects_all is None:
            st, data, why, trunc = _list("/organizations/%s/projects/" % self.org)
            self.projects_all = {"state": st, "data": data if isinstance(data, list) else [], "why": why, "truncated": trunc}
        return self.projects_all

    def resolve_focus(self):
        """The projects that belong to this repo: explicit, else matched from DSN literals in the code."""
        if self.focus is not None:
            return self.focus
        pa = self.load_projects()
        self.focus = []
        if pa["state"] != "ok":
            self.focus_how = "project list unavailable: %s" % pa["why"]
            return self.focus
        by_slug = {p.get("slug"): p for p in pa["data"]}
        by_id = {str(p.get("id")): p for p in pa["data"]}
        if self.want_projects:
            for s in self.want_projects:
                p = by_slug.get(s) or by_id.get(str(s))
                if p:
                    self.focus.append(p)
            self.focus_how = "explicit (%s)" % ",".join(self.want_projects)
            return self.focus
        ids = []
        for u in self.detect.get("units", []):
            for d in (u.get("sentry") or {}).get("dsn_literals", []):
                if d.get("project_id"):
                    ids.append(str(d["project_id"]))
        for i in dict.fromkeys(ids):
            if i in by_id:
                self.focus.append(by_id[i])
        if self.focus:
            self.focus_how = "matched %d project(s) from DSN literals in the repo" % len(self.focus)
            return self.focus
        # `init` names the project after the unit directory, so a project with the unit's id (or the repo name) as slug is this app's
        names = [u.get("id") for u in self.detect.get("units", [])] + [(self.detect.get("repo") or {}).get("name")]
        for n in dict.fromkeys(x for x in names if x):
            if n in by_slug and by_slug[n] not in self.focus:
                self.focus.append(by_slug[n])
        self.focus_how = ("matched project(s) %s by the unit/repo name (DSNs in this repo come from the environment)" % ",".join(p["slug"] for p in self.focus)) if self.focus else \
            "no project could be matched (no DSN literal in the repo, no project named like the unit): pass --project <slug>"
        return self.focus

    def dsn_hosts(self):
        out = []
        for u in self.detect.get("units", []):
            for d in (u.get("sentry") or {}).get("dsn_literals", []):
                out.append((u.get("id"), d.get("host"), d.get("region")))
        return out

    def roles(self):
        return {u.get("id"): u.get("role") for u in self.detect.get("units", [])}

    def preset(self):
        return ((self.policy.get("privacy") or {}).get("preset")) or None


def _row(n, key, cell, title, checks):
    return {"row": n, "id": key, "cell": cell, "title": title, "checks": checks, "state": "clean", "reason": "", "observations": [], "candidates": []}


def _cand(row, check, severity, title, saw, ran, fix, kind="manual", docs=None, org_write=None):
    c = {"check": check, "severity": severity, "title": title, "kind": kind, "evidence": {"ran": ran, "saw": tokens.clip(saw, 400)}, "fix": fix, "docs": docs or []}
    if org_write:
        c["org_write"] = org_write
    row["candidates"].append(c)


def _finish(row):
    if row["state"] == "clean" and row["candidates"]:
        row["state"] = "findings"
    return row


def _need_org(ctx, row):
    why = ctx.resolve_org()
    if why:
        row.update(state="unverified", reason=why)
        return False
    return True


def _need_focus(ctx, row):
    if not _need_org(ctx, row):
        return None
    f = ctx.resolve_focus()
    if not f:
        row.update(state="unverified", reason=ctx.focus_how)
        return None
    return f


def _fail(row, st, why):
    row["state"] = st
    row["reason"] = why
    return _finish(row)


GEO_RULE = "sentry_plugin_remove_geo"


def _geo_rule_config(existing):
    """The project's advanced data scrubbing config with a rule that removes $user.geo added, everything already there kept."""
    try:
        cfg = json.loads(existing) if existing else {}
        if not isinstance(cfg, dict):
            cfg = {}
    except ValueError:
        cfg = {}
    cfg.setdefault("rules", {})[GEO_RULE] = {"type": "anything", "redaction": {"method": "remove"}}
    names = cfg.setdefault("applications", {}).setdefault("$user.geo.**", [])
    if GEO_RULE not in names:
        names.append(GEO_RULE)
    return json.dumps(cfg, sort_keys=True)


# ---------------------------------------------------------------- probes
def p_identity(ctx):
    row = _row(*ROWS[0])
    if not _need_org(ctx, row):
        return row
    o = ctx.load_org()
    if o["state"] != "ok":
        return _fail(row, o["state"], o["why"])
    d = o["data"]
    region = (d.get("links") or {}).get("regionUrl")
    row["observations"].append("org %s (%s), region %s, %d feature flags" % (d.get("name"), d.get("slug"), region, len(d.get("features") or [])))
    pa = ctx.load_projects()
    if pa["state"] != "ok":
        row["observations"].append("project list unavailable: " + pa["why"])
    else:
        plats = {}
        for p in pa["data"]:
            plats[p.get("platform") or "unset"] = plats.get(p.get("platform") or "unset", 0) + 1
        row["observations"].append("%d projects%s; platforms: %s" % (len(pa["data"]), " (list truncated at 100)" if pa["truncated"] else "", ", ".join("%s x%d" % kv for kv in sorted(plats.items(), key=lambda kv: -kv[1])[:8])))
    for p in ctx.resolve_focus():
        flags = [k[3].lower() + k[4:] for k in p if k.startswith("has") and p.get(k) is True and not k.startswith("hasInsights") and k not in ("hasAccess",)]
        row["observations"].append("project %s: platform %s, firstEvent %s, has: %s" % (p.get("slug"), p.get("platform"), p.get("firstEvent") or "never", ",".join(flags) or "nothing yet"))
        if not p.get("firstEvent"):
            _cand(row, "org.projects", "P2", "Project %s has never received an event" % p.get("slug"),
                  "firstEvent is null on %s" % p.get("slug"), "GET /organizations/%s/projects/ (firstEvent)" % ctx.org,
                  "Either the SDK is not initialized in a deployed build or the DSN points elsewhere; run the verify flow for this project.")
    row["observations"].append("focus: " + ctx.focus_how)
    if region:
        host = urllib.parse.urlparse(region).hostname or ""
        for unit, dh, dr in ctx.dsn_hosts():
            want = "de" if host.startswith("de.") else ("us" if host in ("us.sentry.io", "sentry.io") else None)
            if want and dr and dr != want:
                _cand(row, "core.dsn-region", "P1", "DSN host region (%s) does not match the org region (%s) in unit %s" % (dr, want, unit),
                      "DSN host %s, org regionUrl %s" % (dh, region), "GET /organizations/%s/ (links.regionUrl) vs DSN literal in code" % ctx.org,
                      "Use the DSN of a project in this org (`sentry dsn list %s/<project>`); events sent to the wrong region are dropped or land in another org." % ctx.org)
    ctx.evidence[1] = {"org": d.get("slug"), "region": region, "projects": len((pa["data"] if pa["state"] == "ok" else [])), "focus": [p.get("slug") for p in ctx.resolve_focus()]}
    return _finish(row)


def p_keys(ctx):
    row = _row(*ROWS[1])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    ev = {}
    for p in focus:
        st, data, why, _ = _list("/projects/%s/%s/keys/" % (ctx.org, p["slug"]))
        if st != "ok":
            return _fail(row, st, why)
        act = [k for k in data if k.get("isActive")]
        lim = [(k.get("rateLimit") or {}) for k in act]
        ev[p["slug"]] = {"keys": len(data), "active": len(act), "rate_limited_keys": sum(1 for x in lim if x.get("count"))}
        row["observations"].append("%s: %d key(s), %d active, %d with a rate limit" % (p["slug"], len(data), len(act), ev[p["slug"]]["rate_limited_keys"]))
        if not act:
            _cand(row, "quota.controls", "P1", "Project %s has no active client key: every event is rejected" % p["slug"], "0 active keys of %d" % len(data),
                  "GET /projects/%s/%s/keys/" % (ctx.org, p["slug"]), "Enable or create a client key (`sentry dsn list` shows them).")
        elif len(act) > 1 and not any(x.get("count") for x in lim):
            row["observations"].append("%s: several active keys and none rate limited (a second key for staging with its own limit is the documented pattern)" % p["slug"])
    ctx.evidence[2] = ev
    return _finish(row)


def p_filters(ctx):
    row = _row(*ROWS[2])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    roles = set(ctx.roles().values())
    browser = bool(roles & set(BROWSER_ROLES))
    ev = {}
    for p in focus:
        st, data, why, _ = _list("/projects/%s/%s/filters/" % (ctx.org, p["slug"]))
        if st != "ok":
            return _fail(row, st, why)
        state = {f.get("id"): (bool(f.get("active")) if not isinstance(f.get("active"), dict) else bool(f["active"])) for f in data}
        ev[p["slug"]] = state
        row["observations"].append("%s: %s" % (p["slug"], ", ".join("%s=%s" % (k, "on" if v else "off") for k, v in sorted(state.items())) or "no filters returned"))
        want = ["localhost"] + (["browser-extensions", "web-crawlers"] if browser else [])
        for fid in want:
            if fid in state and not state[fid]:
                _cand(row, "err.noise", "P3", "Inbound filter %s is off on %s" % (fid, p["slug"]), "%s active=false" % fid,
                      "GET /projects/%s/%s/filters/" % (ctx.org, p["slug"]),
                      "Turn it on in Project Settings > Inbound Filters (or PUT /projects/%s/%s/filters/%s/ after approval)." % (ctx.org, p["slug"], fid),
                      docs=["https://docs.sentry.io/concepts/data-management/filtering/"])
    ctx.evidence[3] = ev
    return _finish(row)


def p_scrubbing(ctx):
    row = _row(*ROWS[3])
    if not _need_org(ctx, row):
        return row
    o = ctx.load_org()
    if o["state"] != "ok":
        return _fail(row, o["state"], o["why"])
    d = o["data"]
    keys = ("dataScrubber", "dataScrubberDefaults", "scrubIPAddresses", "storeCrashReports", "enhancedPrivacy")
    row["observations"].append("org: " + ", ".join("%s=%s" % (k, d.get(k)) for k in keys) + ", sensitiveFields=%d, safeFields=%d, relayPiiConfig %s" % (
        len(d.get("sensitiveFields") or []), len(d.get("safeFields") or []), "set" if d.get("relayPiiConfig") else "empty"))
    strict = ctx.preset() in ("strict", "standard")
    if d.get("dataScrubber") is False:
        _cand(row, "priv.server-scrub", "P1", "Organization-wide server-side data scrubbing is off", "dataScrubber=false", "GET /organizations/%s/" % ctx.org,
              "Enable 'Require Data Scrubber' in Organization Settings > Security & Privacy (needs org:write; the default CLI login does not carry it).")
    if d.get("dataScrubberDefaults") is False:
        _cand(row, "priv.server-scrub", "P1", "Organization-wide default scrubbers are off", "dataScrubberDefaults=false", "GET /organizations/%s/" % ctx.org,
              "Enable 'Use Default Scrubbers' in Organization Settings > Security & Privacy (org:write).")
    if strict and d.get("scrubIPAddresses") is False:
        _cand(row, "priv.server-scrub", "P2", "Organization does not scrub IP addresses although the policy is %s" % ctx.preset(), "scrubIPAddresses=false",
              "GET /organizations/%s/" % ctx.org, "Enable 'Prevent Storing of IP Addresses' (org:write), or per project.")
    for p in ctx.resolve_focus():
        st, pd, why = _get("/projects/%s/%s/" % (ctx.org, p["slug"]))
        if st != "ok":
            row["observations"].append("project %s: %s" % (p["slug"], why))
            continue
        row["observations"].append("project %s: " % p["slug"] + ", ".join("%s=%s" % (k, pd.get(k)) for k in ("dataScrubber", "dataScrubberDefaults", "scrubIPAddresses")) + ", sensitiveFields=%d" % len(pd.get("sensitiveFields") or []))
        if ctx.preset() in ("strict", "standard"):
            body, why = {}, []
            if pd.get("scrubIPAddresses") is not True and d.get("scrubIPAddresses") is not True:
                body["scrubIPAddresses"] = True
                why.append("IP addresses are stored (scrubIPAddresses=%s)" % pd.get("scrubIPAddresses"))
            if "$user.geo" not in (pd.get("relayPiiConfig") or ""):
                body["relayPiiConfig"] = _geo_rule_config(pd.get("relayPiiConfig"))
                why.append("no advanced data scrubbing rule removes $user.geo (geography is derived from the connecting IP even when IP storage is off)")
            if body:
                _cand(row, "priv.server-scrub", "P2" if ctx.preset() == "strict" else "P3", "Project %s keeps IP addresses and/or geography although the policy is %s" % (p["slug"], ctx.preset()), "; ".join(why),
                      "GET /projects/%s/%s/ (scrubIPAddresses, relayPiiConfig)" % (ctx.org, p["slug"]),
                      "Turn on 'Prevent Storing of IP Addresses' and add the Advanced Data Scrubbing rule [Remove] [Anything] from [$user.geo.**] (Project Settings > Security & Privacy). Project config reaches Relay within about two minutes: send the next marker event after that.",
                      kind="org-write", org_write={"method": "PUT", "path": "/projects/%s/%s/" % (ctx.org, p["slug"]), "body": body,
                                                   "effect": "stop storing client IP addresses and remove user.geo on this project only", "docs": ["https://docs.sentry.io/security-legal-pii/scrubbing/server-side-scrubbing/"]},
                      docs=["https://docs.sentry.io/security-legal-pii/scrubbing/server-side-scrubbing/"])
    ctx.evidence[4] = {k: d.get(k) for k in keys}
    return _finish(row)


def p_spike(ctx):
    row = _row(*ROWS[4])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    for p in focus:
        st, pd, why = _get("/projects/%s/%s/" % (ctx.org, p["slug"]))
        if st != "ok":
            return _fail(row, st, why)
        opts = pd.get("options") or {}
        off = bool(opts.get("quotas:spike-protection-disabled"))
        row["observations"].append("%s: spike protection %s, isDynamicallySampled=%s, %d dynamic-sampling bias entries" % (p["slug"], "OFF" if off else "on", pd.get("isDynamicallySampled"), len(pd.get("dynamicSamplingBiases") or [])))
        if off:
            _cand(row, "quota.controls", "P2", "Spike protection is disabled on %s" % p["slug"], "options[quotas:spike-protection-disabled]=true",
                  "GET /projects/%s/%s/" % (ctx.org, p["slug"]), "Enable spike protection (Organization Settings > Spike Protection) and add a notification action separately.",
                  docs=["https://docs.sentry.io/pricing/quotas/spike-protection/"])
    ctx.evidence[5] = {"checked": [p["slug"] for p in focus]}
    return _finish(row)


def p_alerting(ctx):
    row = _row(*ROWS[5])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    ev = {}
    for p in focus:
        st, det, why, _ = _list("/organizations/%s/detectors/" % ctx.org, {"project": p["id"]})
        if st != "ok":
            return _fail(row, st, why)
        st2, wf, why2, _ = _list("/organizations/%s/workflows/" % ctx.org, {"project": p["id"]})
        if st2 != "ok":
            return _fail(row, st2, why2)
        types = {}
        for d in det:
            types[d.get("type")] = types.get(d.get("type"), 0) + 1
        connected = [d for d in det if d.get("workflowIds")]
        enabled_wf = [w for w in wf if w.get("enabled")]
        with_actions = [w for w in enabled_wf if any((af.get("actions") for af in (w.get("actionFilters") or [])))]
        ev[p["slug"]] = {"detectors": types, "workflows": len(wf), "enabled_workflows": len(enabled_wf), "with_actions": len(with_actions)}
        row["observations"].append("%s: %d detector(s) %s, %d workflow(s) (%d enabled, %d with an action); %d detector(s) connected to a workflow" % (
            p["slug"], len(det), json.dumps(types, sort_keys=True), len(wf), len(enabled_wf), len(with_actions), len(connected)))
        if not connected or not with_actions:
            _cand(row, "alert.coverage", "P2", "Nobody is notified about new or failing issues in %s" % p["slug"],
                  "%d detectors, %d connected to a workflow, %d enabled workflows with an action" % (len(det), len(connected), len(with_actions)),
                  "GET /organizations/%s/detectors/?project=%s ; GET /organizations/%s/workflows/?project=%s" % (ctx.org, p["id"], ctx.org, p["id"]),
                  "Create a workflow that notifies a real destination for the project's error detector (use Sentry's own `sentry-create-alert` skill or the UI); the plugin proposes it as an approved org write only when asked.",
                  docs=["https://docs.sentry.io/product/monitors-and-alerts/"])
    ctx.evidence[6] = ev
    return _finish(row)


def p_monitors(ctx):
    row = _row(*ROWS[6])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    st, mons, why, trunc = _list("/organizations/%s/monitors/" % ctx.org)
    if st != "ok":
        return _fail(row, st, why)
    ids = {str(p["id"]) for p in focus}
    slugs = {p["slug"] for p in focus}
    mine = [m for m in mons if (m.get("project") or {}).get("slug") in slugs or str((m.get("project") or {}).get("id")) in ids]
    never = []
    for m in mine:
        envs = m.get("environments") or []
        if not envs or all(not e.get("lastCheckIn") for e in envs):
            never.append(m.get("slug"))
    row["observations"].append("%d cron monitor(s) for the repo's projects%s; %d never checked in; %d muted" % (len(mine), " (org list truncated)" if trunc else "", len(never), sum(1 for m in mine if m.get("isMuted"))))
    confirmed = []
    for s in never:
        st_c, ci, _w = _get("/organizations/%s/monitors/%s/checkins/" % (ctx.org, s), {"per_page": "1"})
        if st_c == "ok" and isinstance(ci, list) and not ci:
            confirmed.append(s)
            _cand(row, "cron.coverage", "P2", "Cron monitor %s has never received a check-in" % s, "monitor list shows no environment with lastCheckIn and the check-in list is empty",
                  "GET /organizations/%s/monitors/ ; GET /organizations/%s/monitors/%s/checkins/" % (ctx.org, ctx.org, s),
                  "Add the check-in to the job (`sentry-ctx ref products/crons`) or delete the unused monitor.")
        else:
            row["observations"].append("monitor %s looked unused but the check-in list could not confirm it (%s)" % (s, _w or "non-empty"))
    never = confirmed
    up = 0
    for p in focus:
        st2, det, why2, _ = _list("/organizations/%s/detectors/" % ctx.org, {"project": p["id"], "query": "type:uptime_domain_failure"})
        if st2 == "ok":
            up += sum(1 for d in det if d.get("type") == "uptime_domain_failure")
        else:
            row["observations"].append("uptime detectors for %s: %s" % (p["slug"], why2))
    row["observations"].append("%d uptime monitor(s) (detectors of type uptime_domain_failure)" % up)
    urls = []
    for u in ctx.detect.get("units", []):
        urls += (u.get("signals") or {}).get("public_url", [])
    if up == 0 and urls:
        p0 = focus[0]
        _cand(row, "uptime.fit", "P2", "The repo declares a public URL (%s) but no uptime monitor watches it" % urls[0], "0 uptime detectors, public_url=%s" % urls[0],
              "GET /organizations/%s/detectors/?project=%s&query=type:uptime_domain_failure" % (ctx.org, p0["id"]),
              "Create an uptime monitor for the URL (needs your approval; billed per monitor).", kind="org-write",
              org_write={"method": "POST", "path": "/organizations/%s/projects/%s/detectors/" % (ctx.org, p0["slug"]),
                         "body": {"type": "uptime_domain_failure", "name": "uptime %s" % urls[0], "dataSources": [{"url": urls[0], "intervalSeconds": 300, "timeoutMs": 5000, "method": "GET"}],
                                  "config": {"environment": "production", "recoveryThreshold": 1, "downtimeThreshold": 2}},
                         "effect": "create an uptime monitor for %s (billed per monitor)" % urls[0]})
    ctx.evidence[7] = {"cron_monitors": len(mine), "never_checked_in": never, "uptime": up}
    return _finish(row)


def p_releases(ctx):
    row = _row(*ROWS[7])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    st, repos, why, trunc = _list("/organizations/%s/repos/" % ctx.org)
    if st == "ok":
        row["observations"].append("%d repositor%s linked to the org%s" % (len(repos), "y" if len(repos) == 1 else "ies", " (list truncated)" if trunc else ""))
    else:
        row["observations"].append("repos: " + why)
    ev = {}
    for p in focus:
        st, rel, why, _ = _list("/organizations/%s/releases/" % ctx.org, {"project": p["id"], "per_page": "10"})
        if st != "ok":
            return _fail(row, st, why)
        if not rel:
            row["observations"].append("%s: no releases at all" % p["slug"])
            _cand(row, "rel.commits-deploys", "P2", "Project %s has no releases: regressions and suspect commits cannot work" % p["slug"], "0 releases",
                  "GET /organizations/%s/releases/?project=%s" % (ctx.org, p["id"]), "Create a release per deploy in CI (`sentry release create`, `release set-commits --auto`, `release deploy`).")
            continue
        latest = rel[0]
        no_commits = not latest.get("commitCount")
        no_deploy = not latest.get("lastDeploy") and not latest.get("deployCount")
        ev[p["slug"]] = {"latest": latest.get("version"), "commits": latest.get("commitCount"), "deploys": latest.get("deployCount")}
        row["observations"].append("%s: latest release %s, %s commit(s), %s deploy(s)" % (p["slug"], latest.get("version"), latest.get("commitCount"), latest.get("deployCount")))
        if no_commits:
            _cand(row, "rel.commits-deploys", "P2", "Latest release of %s has no commits associated" % p["slug"], "commitCount=0 on %s" % latest.get("version"),
                  "GET /organizations/%s/releases/?project=%s" % (ctx.org, p["id"]), "Run `sentry release set-commits <org>/<version> --auto` after `release create` (needs a full git checkout in CI).")
        if no_deploy:
            _cand(row, "rel.commits-deploys", "P3", "Latest release of %s has no deploy recorded" % p["slug"], "deployCount=0 on %s" % latest.get("version"),
                  "GET /organizations/%s/releases/?project=%s" % (ctx.org, p["id"]), "Run `sentry release deploy <org>/<version> <environment>` when the release ships.")
    ctx.evidence[8] = ev
    return _finish(row)


def p_artifacts(ctx):
    row = _row(*ROWS[8])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    ev = {}
    for p in focus:
        plat = (p.get("platform") or "").lower()
        native = any(plat.startswith(n) or n in plat for n in NATIVE_PLATFORMS)
        js = plat.startswith("javascript") or plat in ("node", "react", "vue", "angular") or "javascript" in plat
        st_b, bundles, why_b, _ = _list("/projects/%s/%s/files/artifact-bundles/" % (ctx.org, p["slug"]))
        st_d, dsyms, why_d, _ = _list("/projects/%s/%s/files/dsyms/" % (ctx.org, p["slug"]))
        nb = len(bundles) if st_b == "ok" else None
        nd = len(dsyms) if st_d == "ok" else None
        ev[p["slug"]] = {"platform": plat, "artifact_bundles": nb, "debug_files": nd}
        row["observations"].append("%s (%s): artifact bundles %s, debug files %s" % (p["slug"], plat or "unset", nb if nb is not None else "unavailable (%s)" % why_b, nd if nd is not None else "unavailable (%s)" % why_d))
        if native and nd == 0:
            _cand(row, "rel.debug-files", "P1", "No debug files uploaded for %s (%s): crash stacks stay unsymbolicated" % (p["slug"], plat), "0 debug files",
                  "GET /projects/%s/%s/files/dsyms/" % (ctx.org, p["slug"]), "Upload dSYMs/ProGuard mappings/native symbols in the release build (`sentry debug-files upload`, the Gradle plugin, or the Xcode build phase).")
        if js and nb == 0:
            _cand(row, "rel.sourcemaps", "P1", "No source map bundles uploaded for %s" % p["slug"], "0 artifact bundles",
                  "GET /projects/%s/%s/files/artifact-bundles/" % (ctx.org, p["slug"]), "Upload source maps with Debug IDs in the production build (bundler plugin or `sentry sourcemap inject` + `upload`).")
    ctx.evidence[9] = ev
    return _finish(row)


def _frames(ev):
    out = []
    for ent in ev.get("entries") or []:
        if ent.get("type") == "exception":
            for ex in (ent.get("data") or {}).get("values") or []:
                out += (ex.get("stacktrace") or {}).get("frames") or []
    return out


def p_stacktraces(ctx):
    row = _row(*ROWS[9])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    ev = {}
    for p in focus:
        st, pd, why = _get("/projects/%s/%s/" % (ctx.org, p["slug"]))
        if st != "ok":
            return _fail(row, st, why)
        mini = bool(pd.get("hasMinifiedStackTrace"))
        st2, evs, why2, _ = _list("/projects/%s/%s/events/" % (ctx.org, p["slug"]), {"per_page": "3"})
        total = bad = 0
        if st2 == "ok":
            for e in evs[:3]:
                eid = e.get("eventID") or e.get("id")
                st3, full, _w = _get("/projects/%s/%s/events/%s/" % (ctx.org, p["slug"], eid))
                if st3 != "ok" or not isinstance(full, dict):
                    continue
                for fr in _frames(full):
                    if not fr.get("inApp"):
                        continue
                    total += 1
                    fn = fr.get("filename") or fr.get("absPath") or ""
                    if re.search(r"\.min\.js|/_next/static/chunks/[a-f0-9]+\.js", fn) or (not fr.get("context") and not fr.get("function")) or (fr.get("lineNo") == 1 and (fr.get("colNo") or 0) > 500):
                        bad += 1
        ev[p["slug"]] = {"hasMinifiedStackTrace": mini, "in_app_frames": total, "unreadable": bad}
        row["observations"].append("%s: hasMinifiedStackTrace=%s; sampled %d in-app frame(s) from recent events, %d look unreadable%s" % (
            p["slug"], mini, total, bad, "" if st2 == "ok" else " (events unavailable: %s)" % why2))
        if mini and not total:
            row["observations"].append("%s: hasMinifiedStackTrace is a sticky project flag (set once a minified trace was ever seen); no recent event could confirm it today" % p["slug"])
            _cand(row, "rel.resolve", "P3", "Project %s once received minified stack traces; no recent event confirms they are readable now" % p["slug"],
                  "hasMinifiedStackTrace=true, 0 in-app frames sampled", "GET /projects/%s/%s/ ; GET /projects/%s/%s/events/" % (ctx.org, p["slug"], ctx.org, p["slug"]),
                  "Emit a marked event from a production-like build and read its frames (the verify flow, rung R4).")
        elif total and bad * 2 >= total:
            _cand(row, "rel.resolve", "P1", "Stack traces for %s are not readable (minified or unsymbolicated frames)" % p["slug"],
                  "hasMinifiedStackTrace=%s, %d of %d sampled in-app frames unreadable" % (mini, bad, total),
                  "GET /projects/%s/%s/ ; GET /projects/%s/%s/events/ (3 newest, frames only)" % (ctx.org, p["slug"], ctx.org, p["slug"]),
                  "Upload source maps/debug files for the release that produced these events; check the release string matches (`sentry-ctx ref products/debug-artifacts`).")
    ctx.evidence[10] = ev
    return _finish(row)


def p_ownership(ctx):
    row = _row(*ROWS[10])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    ev = {}
    for p in focus:
        st, ow, why = _get("/projects/%s/%s/ownership/" % (ctx.org, p["slug"]))
        if st != "ok":
            return _fail(row, st, why)
        raw = (ow or {}).get("raw") or ""
        rules = len([ln for ln in raw.splitlines() if ln.strip() and not ln.strip().startswith("#")])
        ev[p["slug"]] = {"rules": rules, "fallthrough": ow.get("fallthrough"), "autoAssignment": ow.get("autoAssignment"), "codeownersAutoSync": ow.get("codeownersAutoSync")}
        row["observations"].append("%s: %d ownership rule(s), autoAssignment=%s, codeownersAutoSync=%s" % (p["slug"], rules, ow.get("autoAssignment"), ow.get("codeownersAutoSync")))
        if rules == 0:
            _cand(row, "err.ownership", "P3", "No ownership rules on %s: issues have no owner" % p["slug"], "ownership raw is empty",
                  "GET /projects/%s/%s/ownership/" % (ctx.org, p["slug"]), "Add ownership rules or sync CODEOWNERS (Project Settings > Issue Owners); only if the team works with owners.")
    ctx.evidence[11] = ev
    return _finish(row)


def p_event_sanity(ctx):
    row = _row(*ROWS[11])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    ev = {}
    for p in focus:
        base = {"dataset": "errors", "project": p["id"], "statsPeriod": "7d"}
        st, tot, why = _get("/organizations/%s/events/" % ctx.org, dict(base, field="count()"))
        if st != "ok":
            return _fail(row, st, why)
        total = int(((tot.get("data") or [{}])[0] or {}).get("count()", 0))
        counts = {"total": total}
        for key, q in (("no_environment", "!has:environment"), ("no_release", "!has:release")):
            st2, r2, _w = _get("/organizations/%s/events/" % ctx.org, dict(base, field="count()", query=q))
            counts[key] = int(((r2.get("data") or [{}])[0] or {}).get("count()", 0)) if st2 == "ok" else None
        st3, envs, _w = _get("/organizations/%s/events/" % ctx.org, dict(base, field=["environment", "count()"], sort="-count()", per_page="8"))
        st4, sdks, _w4 = _get("/organizations/%s/events/" % ctx.org, dict(base, field=["sdk.name", "count()"], sort="-count()", per_page="5"))
        env_names = [d.get("environment") or "(none)" for d in (envs.get("data") or [])] if st3 == "ok" else []
        sdk_names = [d.get("sdk.name") for d in (sdks.get("data") or [])] if st4 == "ok" else []
        ev[p["slug"]] = dict(counts, environments=env_names, sdks=sdk_names)
        row["observations"].append("%s (7d): %d error event(s); %s without environment, %s without release; environments %s; sdks %s" % (
            p["slug"], total, counts["no_environment"], counts["no_release"], env_names or "n/a", sdk_names or "n/a"))
        if total >= 5:
            if counts["no_environment"] and counts["no_environment"] / total > 0.05:
                _cand(row, "core.environment", "P1", "%d of %d recent events of %s carry no environment" % (counts["no_environment"], total, p["slug"]),
                      "query !has:environment -> %d of %d" % (counts["no_environment"], total), "GET /organizations/%s/events/?dataset=errors&query=!has:environment&statsPeriod=7d" % ctx.org,
                      "Set `environment` in the SDK init (or SENTRY_ENVIRONMENT) for every deployed process.")
            if counts["no_release"] and counts["no_release"] / total > 0.05:
                _cand(row, "core.release", "P1", "%d of %d recent events of %s carry no release" % (counts["no_release"], total, p["slug"]),
                      "query !has:release -> %d of %d" % (counts["no_release"], total), "GET /organizations/%s/events/?dataset=errors&query=!has:release&statsPeriod=7d" % ctx.org,
                      "Set `release` in the SDK init (or SENTRY_RELEASE) to the same string CI uses for the release object.")
    ctx.evidence[12] = ev
    return _finish(row)


def p_usage(ctx):
    row = _row(*ROWS[12])
    if not _need_org(ctx, row):
        return row
    st, data, why = _get("/organizations/%s/stats_v2/" % ctx.org, {"field": "sum(quantity)", "groupBy": ["category", "outcome"], "statsPeriod": "30d"})
    if st != "ok":
        return _fail(row, st, why)
    cat = {}
    for g in data.get("groups") or []:
        by = g.get("by") or {}
        q = ((g.get("totals") or {}).get("sum(quantity)")) or 0
        c = cat.setdefault(by.get("category"), {})
        c[by.get("outcome")] = c.get(by.get("outcome"), 0) + q
    for c, outs in sorted(cat.items(), key=lambda kv: -sum(kv[1].values()))[:10]:
        row["observations"].append("%s: %s" % (c, ", ".join("%s=%d" % kv for kv in sorted(outs.items(), key=lambda kv: -kv[1]))))
        tot = sum(outs.values())
        rl = outs.get("rate_limited", 0) + outs.get("cardinality_limited", 0)
        if tot and rl / tot > 0.02:
            _cand(row, "quota.size-billed", "P2", "%d%% of the %s volume was dropped by rate limits in the last 30 days" % (100 * rl // tot, c), "rate_limited+cardinality_limited=%d of %d" % (rl, tot),
                  "GET /organizations/%s/stats_v2/?field=sum(quantity)&groupBy=category&groupBy=outcome&statsPeriod=30d" % ctx.org,
                  "Raise the budget or cut volume at the source (sampling, filters); see `sentry-ctx ref products/quota`.")
    if not cat:
        row["observations"].append("no usage in the last 30 days")
    ctx.evidence[13] = {c: o for c, o in cat.items()}
    return _finish(row)


def p_seer(ctx):
    row = _row(*ROWS[13])
    if not _need_org(ctx, row):
        return row
    o = ctx.load_org()
    if o["state"] != "ok":
        return _fail(row, o["state"], o["why"])
    d = o["data"]
    keys = ("hideAiFeatures", "genAIConsent", "aggregatedDataConsent", "enableSeerCoding", "autoEnableCodeReview", "defaultAutofixAutomationTuning")
    row["observations"].append("org: " + ", ".join("%s=%s" % (k, d.get(k)) for k in keys))
    st, ints, why, _ = _list("/organizations/%s/integrations/" % ctx.org, {"providerKey": "github"})
    row["observations"].append("GitHub integration: %s" % (("%d installed" % len(ints)) if st == "ok" else why))
    row["observations"].append("Seer is billed per use and is never started by this plugin without an explicit request.")
    ctx.evidence[14] = {k: d.get(k) for k in keys}
    return _finish(row)


def p_replays(ctx):
    row = _row(*ROWS[14])
    focus = _need_focus(ctx, row)
    if focus is None:
        return row
    ev = {}
    for p in focus:
        st, rp, why = _get("/organizations/%s/replays/" % ctx.org, {"project": p["id"], "statsPeriod": "7d", "field": "id", "per_page": "100"})
        if st != "ok":
            return _fail(row, st, why)
        n = len((rp or {}).get("data") or [])
        ev[p["slug"]] = n
        row["observations"].append("%s: %s replay(s) in 7 days%s (masking is configured in the SDK, not in Sentry)" % (p["slug"], n, "+" if n >= 100 else ""))
    ctx.evidence[15] = ev
    return _finish(row)


def p_flags(ctx):
    row = _row(*ROWS[15])
    if not _need_org(ctx, row):
        return row
    st, data, why = _get("/organizations/%s/flags/logs/" % ctx.org, {"per_page": "10"})
    if st != "ok":
        return _fail(row, st, why)
    n = len((data or {}).get("data") or [])
    row["observations"].append("%d recent flag-change log entr%s (webhook coverage)" % (n, "y" if n == 1 else "ies"))
    ctx.evidence[16] = {"entries": n}
    return _finish(row)


def p_integrations(ctx):
    row = _row(*ROWS[16])
    if not _need_org(ctx, row):
        return row
    st, ints, why, _ = _list("/organizations/%s/integrations/" % ctx.org)
    if st != "ok":
        return _fail(row, st, why)
    bad = []
    for i in ints:
        prov = (i.get("provider") or {}).get("key")
        stat = i.get("organizationIntegrationStatus") or i.get("status")
        row["observations"].append("%s (%s): %s%s" % (i.get("name"), prov, stat, ", out of date" if i.get("outOfDate") else ""))
        if str(stat).lower() not in ("active", "enabled") or i.get("outOfDate"):
            bad.append((i.get("name"), stat))
    for name, stat in bad:
        _cand(row, "org.projects", "P3", "Integration %s is %s" % (name, stat), "organizationIntegrationStatus=%s" % stat, "GET /organizations/%s/integrations/" % ctx.org,
              "Reinstall or repair the integration in Organization Settings > Integrations; it is a UI/OAuth flow.")
    if not ints:
        row["observations"].append("no integrations installed")
    ctx.evidence[17] = {"count": len(ints)}
    return _finish(row)


PROBES = [p_identity, p_keys, p_filters, p_scrubbing, p_spike, p_alerting, p_monitors, p_releases, p_artifacts, p_stacktraces,
          p_ownership, p_event_sanity, p_usage, p_seer, p_replays, p_flags, p_integrations]


# ---------------------------------------------------------------- entry points
def focus_cmd(root, org=None, projects=None):
    ctx = Ctx(root, org, projects)
    if org or projects:
        saved = {"org": org or ctx.saved.get("org"), "projects": projects if projects is not None else ctx.saved.get("projects", [])}
        os.makedirs(paths.state_dir(root), exist_ok=True)
        util.write_json(os.path.join(paths.state_dir(root), "org.json"), saved)
        ctx = Ctx(root)
    why = ctx.resolve_org()
    out = {"org": ctx.org, "projects_requested": ctx.want_projects}
    if why:
        out["error"] = why
        return out
    f = ctx.resolve_focus()
    out["focus"] = [{"slug": p.get("slug"), "id": p.get("id"), "platform": p.get("platform")} for p in f]
    out["how"] = ctx.focus_how
    return out


def probe(root, which="all", org=None, projects=None):
    ctx = Ctx(root, org, projects)
    sel = []
    if which in (None, "", "all"):
        sel = list(range(len(ROWS)))
    else:
        for w in str(which).split(","):
            r = ROW_BY_KEY.get(w.strip())
            if not r:
                raise util.EngineError("unknown probe row %r (1-17 or: %s)" % (w, ", ".join(x[1] for x in ROWS)))
            sel.append(r[0] - 1)
    rows = []
    ev_dir = os.path.join(paths.state_dir(root), "evidence")
    os.makedirs(ev_dir, exist_ok=True)
    for i in sel:
        try:
            row = PROBES[i](ctx)
        except util.EngineError:
            raise
        except Exception as e:  # a probe bug must not silently pass as clean
            row = _row(*ROWS[i])
            row.update(state="unverified", reason="probe error: %s: %s" % (type(e).__name__, tokens.clip(str(e), 160)))
        row = tokens.mask_deep(row)
        n = ROWS[i][0]
        evidence = tokens.mask_deep({"row": row["row"], "id": row["id"], "state": row["state"], "reason": row["reason"], "observations": row["observations"], "summary": ctx.evidence.get(n)})
        p = os.path.join(ev_dir, "org-%02d-%s.json" % (n, ROWS[i][1]))
        util.write_json(p, evidence)
        row["evidence_file"] = os.path.relpath(p, root)
        rows.append(row)
    return {"org": ctx.org, "focus": [p.get("slug") for p in (ctx.focus or [])], "focus_how": ctx.focus_how, "rows": rows,
            "states": {s: sum(1 for r in rows if r["state"] == s) for s in ("clean", "findings", "unverified", "n/a")}}


def record(root, result):
    """Turn probe candidates into open `_org` findings and set the `_org/*` coverage cells. A cell is `findings` when any of its rows
    produced one, `clean` only when every row of the cell was read successfully, otherwise `unverified` with the rows' reasons."""
    from . import findings
    plan = util.read_json(os.path.join(paths.state_dir(root), "plan.json"), {}) or {}
    units = {u["id"] for u in plan.get("units", [])}
    added, skipped = [], []
    for row in result["rows"]:
        for c in row["candidates"]:
            f = {"unit": "_org", "check": c["check"], "severity": c["severity"], "confidence": 0.9, "kind": c["kind"], "title": c["title"],
                 "files": [], "evidence": c["evidence"], "what": c["title"] + ".", "fix": c["fix"], "docs": c.get("docs", []),
                 "verify": {"rung": "R3", "how": "rerun `sentry-ctx org probe %s` after the change" % row["id"], "expect": "the candidate no longer appears"}}
            if c.get("org_write"):
                f["org_write"] = c["org_write"]
            try:
                added.append(findings.add(root, f, units)["id"])
            except util.EngineError as e:
                skipped.append("%s: %s" % (c["title"][:60], e))
            except findings.Invalid as e:
                skipped.append("%s: %s" % (c["title"][:60], "; ".join(e.errors)))
    cells = {}
    for row in result["rows"]:
        cells.setdefault(row["cell"], []).append(row)
    cov = findings.cov_load(root)["cells"]
    set_cells = {}
    for cell, rows in cells.items():
        if cell not in cov:
            continue
        unit, product = cell.split("/", 1)
        note = "; ".join("%s=%s" % (r["id"], r["state"]) for r in rows)
        if any(r["state"] == "findings" for r in rows):
            state, kw = "findings", {"note": note}
        elif any(r["state"] == "unverified" for r in rows):
            state, kw = "unverified", {"reason": "; ".join("%s: %s" % (r["id"], r["reason"]) for r in rows if r["state"] == "unverified")[:600]}
        elif all(r["state"] == "n/a" for r in rows):
            state, kw = "n/a", {"reason": "; ".join("%s: %s" % (r["id"], r["reason"]) for r in rows)[:300]}
        else:
            state, kw = "clean", {"note": "read: " + note}
        try:
            findings.cov_set(root, unit, product, state, **kw)
            set_cells[cell] = state
        except util.EngineError as e:
            set_cells[cell] = "not set (%s)" % e
    return {"findings_added": added, "skipped": skipped, "coverage": set_cells}


def render(result):
    lines = ["org %s | focus: %s (%s)" % (result["org"], ", ".join(result["focus"]) or "none", result["focus_how"] or "-")]
    for r in result["rows"]:
        lines.append("%2d %-12s %-11s %s" % (r["row"], r["id"], r["state"].upper() if r["state"] in ("unverified", "findings") else r["state"], r["reason"] or "; ".join(r["observations"][:1])))
        for o in r["observations"][1:3]:
            lines.append("   %s" % o)
        for c in r["candidates"]:
            lines.append("   -> candidate %s %s: %s" % (c["severity"], c["check"], c["title"]))
    lines.append("states: " + ", ".join("%s=%d" % kv for kv in result["states"].items()))
    return "\n".join(lines)


# ---------------------------------------------------------------- approved writes
ORG_SCOPE_RULES = [  # (method, path regex) -> scope the login must carry
    ("PUT", r"^/organizations/[^/]+/?$", "org:write"),
    ("POST", r"^/organizations/[^/]+/(?!projects/|detectors|workflows|monitors|teams/)[^/]+/?$", "org:write"),
    ("DELETE", r"^/organizations/[^/]+/?$", "org:admin"),
]
DRY_RUN_CLI = ("project create", "release create", "release deploy", "release finalize", "release set-commits", "monitor run")


def _missing_scope(method, path):
    need = None
    for m, rx, sc in ORG_SCOPE_RULES:
        if m == method and re.match(rx, path.split("?", 1)[0]):
            need = sc
    if not need:
        return None
    have = cli_tools.scopes()
    if have is None:
        return None  # cannot tell: let the API answer
    return need if need not in have else None


def apply_write(root, finding_id, run=False):
    """Show (dry run) or perform the org write recorded on an approved org-write finding. Performs it only if the exact call was
    approved in this run (`run approve-write`). The engine's own subprocess is not seen by the Bash gate, so it enforces approval itself."""
    from . import findings
    p = findings.find_path(root, finding_id)
    if not p:
        raise util.EngineError("no such finding: " + finding_id)
    fm, _body = findings._load_file(p)
    ow = fm.get("org_write")
    if fm.get("kind") != "org-write" or not isinstance(ow, dict):
        raise util.EngineError("%s is not an org-write finding" % finding_id)
    if fm.get("status") not in ("approved", "applied"):
        raise util.EngineError("%s is %s: approve the finding first" % (finding_id, fm.get("status")))
    st = runstate.load(root)
    out = {"finding": finding_id, "effect": ow.get("effect")}
    if ow.get("cli"):
        import shlex
        args = shlex.split(ow["cli"])
        sub = " ".join(args[:2])
        approved = runstate.cli_approved_for(st, ow["cli"], finding_id, runstate.current_session(root), ow)
        out.update(cli="sentry " + ow["cli"], approved_in_run=approved)
        binary = cli_tools.sentry_bin()
        if not binary:
            raise util.EngineError("no sentry v4 CLI installed", 3)
        if sub in DRY_RUN_CLI and "--dry-run" not in args:
            rc, o, e = util.run([binary, *args, "--dry-run"], timeout=90, env=cli_tools.env())
            out["dry_run"] = {"rc": rc, "output": tokens.clip((o or e).strip(), 700)}
        if not run:
            out["next"] = "the user approves it (a permission prompt shows the command): sentry-ctx run approve-write --cli \"%s\" --finding %s ; then rerun with --run" % (ow["cli"], finding_id)
            return tokens.mask_deep(out)
        if not approved:
            raise util.EngineError("`sentry %s` was not approved in this run: ask the user, then `sentry-ctx run approve-write --cli \"%s\" --finding %s`" % (sub, sub, finding_id), 5)
        rc, o, e = util.run([binary, *args], timeout=180, env=cli_tools.env())
        out["result"] = {"rc": rc, "summary": tokens.clip((o or e).strip(), 500)}
        if rc == 0:
            findings.set_status(root, finding_id, "applied")
        return tokens.mask_deep(out)
    method, path = str(ow["method"]).upper(), re.sub(r"^/api/0(?=/)", "", ow["path"])
    if method not in ("POST", "PUT", "PATCH", "DELETE"):
        raise util.EngineError("org_write.method must be POST|PUT|PATCH|DELETE")
    body = ow.get("body")
    approved = runstate.write_is_approved(st, method, path, runstate.current_session(root), finding_id, ow)
    dry = cli_tools.api(path, method, body=body, dry_run=True)
    out.update(method=method, path=path, approved_in_run=approved,
               dry_run={"rc": dry["rc"], "output": tokens.clip(json.dumps(dry["data"]) if dry["data"] is not None else (dry["raw"] or dry.get("err") or ""), 700)})
    miss = _missing_scope(method, path)
    if miss:
        out["preflight"] = "the CLI login does not carry the %s scope this call needs: it will be refused. Do it in the UI (Organization Settings), or `sentry auth login` again with that scope, or mark the finding skipped." % miss
    if not run:
        out["next"] = "approve with: sentry-ctx run approve-write --method %s %s --finding %s ; then rerun with --run" % (method, path, finding_id)
        return tokens.mask_deep(out)
    if not approved:
        raise util.EngineError("%s %s was not approved in this run: ask the user, then `sentry-ctx run approve-write --method %s %s --finding %s`" % (method, path, method, path, finding_id), 5)
    if miss:
        raise util.EngineError(out["preflight"], 5)
    r = cli_tools.api(path, method, body=body)
    out["result"] = {"rc": r["rc"], "label": r["label"], "summary": tokens.clip(json.dumps(r["data"]) if r["data"] is not None else (r["raw"] or r.get("err") or ""), 500)}
    if r["rc"] == 0:
        findings.set_status(root, finding_id, "applied")
    return tokens.mask_deep(out)
