"""Policy file (.sentry-plugin/policy.md): front matter holds the answers, the body holds free notes."""
from __future__ import annotations

import json
import os

from . import miniyaml, paths, util

DEFAULTS = {
    "privacy": {"preset": None, "ai_io": None, "replay_mask": None},
    "org_access": None, "environments": [], "volume": None, "release_owner": None,
    "products": {"include": [], "exclude": []},
}


def path(root):
    return os.path.join(paths.state_dir(root), "policy.md")


def load(root):
    p = path(root)
    if not os.path.isfile(p):
        return None
    fm, _ = miniyaml.split_front_matter(util.read_text(p))
    return fm or None


def save(root, answers: dict, notes: str = ""):
    fm = dict(answers)
    fm["updated_at"] = util.now_iso()
    util.write_text(path(root), miniyaml.join_front_matter(fm, notes or "## Notes\n\n(free text; edit freely)\n"))


def questions(detect: dict, plan: dict | None, prev: dict | None):
    """Questions relevant to the detected units, previous answer moved first and labelled."""
    spec = paths.load_json_data("policy_questions.json")
    sigs, products = set(), set()
    for u in detect["units"]:
        sigs |= set(u.get("signals", {}).keys())
    if plan:
        for u in plan["units"]:
            for pid, c in u["products"].items():
                if c["state"] == "applicable":
                    products.add(pid)
    out = []
    for q in spec["questions"]:
        w = q["when"]
        if w != "always":
            ok = False
            for alt in w.split("|"):
                k, _, v = alt.partition(":")
                vals = v.split(",")
                if k == "sig" and any(x in sigs for x in vals):
                    ok = True
                if k == "product" and any(x in products for x in vals):
                    ok = True
            if not ok:
                continue
        qq = json.loads(json.dumps(q))
        prev_val = _get(prev or {}, q["id"])
        if prev_val is not None:
            vals = prev_val if isinstance(prev_val, list) else [prev_val]
            if not q["multiSelect"]:
                for i, opt in enumerate(qq["options"]):
                    if opt["value"] == vals[0]:
                        opt = dict(opt, label=opt["label"] + " (previous)")
                        qq["options"] = [opt] + [o for j, o in enumerate(qq["options"]) if j != i]
                        break
            qq["previous"] = prev_val
        out.append(qq)
    return {"calls": {"A": [q for q in out if q["call"] == "A"], "B": [q for q in out if q["call"] == "B"]}}


def _get(d, dotted):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def set_dotted(d, dotted, value):
    parts = dotted.split(".")
    cur = d
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def from_answers(answers: dict) -> dict:
    """answers: flat {question id: value or list}. Produces the nested policy structure."""
    pol = json.loads(json.dumps(DEFAULTS))
    for k, v in answers.items():
        if k == "products":
            vals = v if isinstance(v, list) else [v]
            inc = [x.split(":", 1)[1] for x in vals if isinstance(x, str) and x.startswith("include:")]
            exc = [x.split(":", 1)[1] for x in vals if isinstance(x, str) and x.startswith("exclude:")]
            pol["products"] = {"include": inc, "exclude": exc}
        elif k in ("environments",):
            pol[k] = v if isinstance(v, list) else [v]
        else:
            set_dotted(pol, k, v)
    return pol
