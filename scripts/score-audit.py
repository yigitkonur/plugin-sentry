#!/usr/bin/env python3
"""Score an audit run against evals/expected/<fixture>.audit.json.
Usage: score-audit.py <repo-dir> <expected.json>   Exit 0 only if every must_find matched and no must_not did."""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import findings, miniyaml  # noqa: E402

SEV = ["P0", "P1", "P2", "P3"]


def text_of(f, path):
    body = open(path, encoding="utf-8").read() if path else ""
    return (f.get("title", "") + " " + body).lower()


def main(repo, exp_path):
    exp = json.load(open(exp_path))
    rows = []
    for f in findings.load_all(repo):
        if f.get("status") == "skipped":  # superseded by a corrected re-file
            continue
        p = os.path.join(repo, f["_path"])
        rows.append((f, text_of(f, p)))
    cov = findings.cov_load(repo)["cells"]
    states = {v.get("state") for v in cov.values()}
    fail = 0
    print("%d findings, coverage states: %s" % (len(rows), sorted(states)))
    for m in exp["must_find"]:
        hit = None
        for f, t in rows:
            title = f.get("title", "").lower()
            by_check = bool(m.get("any_check")) and f.get("check") in m["any_check"]
            by_text = bool(m.get("text_any")) and any(x.lower() in t for x in m["text_any"])
            by_title = bool(m.get("title_any")) and any(x.lower() in title for x in m["title_any"])
            # a finding matches by its catalog id, or by naming the defect (anywhere in its text, or in its title for title_any)
            if m.get("title_any") and not m.get("any_check") and not m.get("text_any"):
                ok_what = by_title
            elif m.get("any_check") and m.get("text_any"):
                ok_what = by_check and by_text
            else:
                ok_what = by_check or by_text or by_title
            ok_files = (not m.get("files_any")) or any(x in f.get("files", []) for x in m["files_any"]) or any(x.lower() in t for x in m["files_any"])
            ok_sev = (not m.get("min_severity")) or SEV.index(f.get("severity", "P3")) <= SEV.index(m["min_severity"])
            if ok_what and ok_files and ok_sev:
                hit = f
                break
        print("  %-5s must_find %-22s %s" % ("OK" if hit else "MISS", m["id"], ("<- %s %s %s" % (hit["id"], hit["check"], hit["severity"])) if hit else ""))
        fail += 0 if hit else 1
    for n in exp.get("must_not", []):
        bad = None
        for f, t in rows:
            if n.get("files_any") and not any(x in f.get("files", []) for x in n["files_any"]):
                continue
            if n.get("severity_in") and f.get("severity") not in n["severity_in"]:
                continue
            if n.get("product_in") and f.get("product") not in n["product_in"]:
                continue
            if n.get("kind_in") and f.get("kind") not in n["kind_in"]:
                continue
            bad = f
            break
        print("  %-5s must_not  %-22s %s" % ("FAIL" if bad else "OK", n["id"], ("<- " + bad["id"] + " " + bad["check"]) if bad else ""))
        fail += 1 if bad else 0
    for need in exp.get("coverage_states_required", []):
        ok = any(s in states or any(s == x for x in states) for s in need.split("|"))
        print("  %-5s coverage state present: %s" % ("OK" if ok else "MISS", need))
        fail += 0 if ok else 1
    p0 = [f for f, _ in rows if f.get("severity") == "P0"]
    print("P0 findings: %s" % [(f["id"], f["check"], f.get("files")) for f in p0])
    print("RESULT:", "PASS" if not fail else "FAIL (%d)" % fail)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(os.path.abspath(sys.argv[1]), sys.argv[2]))
