#!/usr/bin/env python3
"""Regression checks for the Bash gate (H4) and the approval rules: compound commands, global options, nested shells,
approval provenance (run, session, finding, exact operation). Exit 1 on any failure. Run by scripts/check.sh."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "engine"))
from sentry_ctx import runstate  # noqa: E402
from sentry_ctx.hooks import gate_bash as g  # noqa: E402

fails = 0


def expect(cmd, want):
    global fails
    v, reason, keys = g.classify(cmd)
    ok = v == want
    if not ok:
        fails += 1
    print("%-5s %-9s want %-9s %s" % ("ok" if ok else "FAIL", v, want, cmd[:100]))
    return v, keys


for c in ["sentry issue list zeo/ --json", "sentry --org acme issue list", "sentry project create --help", "sentry release create a --dry-run", "git status && ls",
          "sentry api /organizations/acme/ -X GET", "SENTRY_NO_CACHE=1 sentry api -X GET /projects/a/b/", "sentry event send -m x --no-environ",
          "sentry-ctx run status", "cat .sentry-plugin/run.json", "jq . .sentry-plugin/run.json", "sentry project create a/b:node --dry-run"]:
    expect(c, "allow")

for c in ["sentry --org acme issue plan X", "sentry release create a && sentry issue plan X", "bash -c 'sentry project create a/b:node'",
          "echo $(sentry release finalize x)", 'eval "sentry issue resolve X"', "sentry api -X PUT /issues/1/ -d a=b", "curl -X POST https://sentry.io/api/0/x/y/",
          "sentry --org=acme --project=p release deploy v prod", "echo x | xargs sentry issue resolve", "find . -name a -exec sentry issue resolve X ';'",
          "sentry --log-level debug --org acme sourcemap upload dist", "npx @sentry/cli releases new v1", "sentry-cli upload-dsym build/",
          "sentry project create a/b:node --team zeo", "timeout 60 sentry issue explain X", "python3 -c \"import os; os.system('sentry issue plan X')\"",
          "sentry init . --yes"]:
    expect(c, "mutation")

for c, why in [("sentry auth token", "token"), ("sentry auth status", "partial token display"), ("sentry --org a auth status --json", "partial token display"), ("sentry event send -m x", "no-environ"), ("cat .sentryclirc", "cred file"), ('echo "$SENTRY_AUTH_TOKEN"', "echo token"),
               ("echo '{}' > .sentry-plugin/run.json", "state edit"), ("python3 -c \"open('.sentry-plugin/run.json','w').write('{}')\"", "state edit via python"),
               ("sed -i 's/a/b/' .sentry-plugin/run.json", "state sed"), ("sentry release create a && sentry auth token", "deny dominates a mutation"),
               ("SENTRY_AUTH_TOKEN=sntryu_" + "a1" * 32 + " sentry release list", "token on the command line")]:
    expect(c, "deny")

for c in ["sentry-ctx run approve-write --method PUT /projects/a/b/ --finding F-001", "/x/bin/sentry-ctx run approve-write --cli 'project create a/b:node'"]:
    expect(c, "approval")

# compound: both mutations are reported, so both need approval
v, keys = expect("sentry release create a && sentry issue plan X", "mutation")
if len(keys) != 2:
    fails += 1
    print("FAIL compound command must report both mutations, got", keys)

# approval rules ---------------------------------------------------------
st = {"run_id": "r-1", "phase": "approved", "approved_cli": [], "approved_writes": []}


def add_cli(cli, finding=None, fp=None, session="s1", run_id="r-1"):
    st["approved_cli"].append({"cli": cli, "finding": finding, "fingerprint": fp, "run_id": run_id, "session_id": session})


def add_w(method, path, finding=None, fp=None, session="s1", run_id="r-1"):
    st["approved_writes"].append({"method": method, "path": path, "finding": finding, "fingerprint": fp, "run_id": run_id, "session_id": session})


def check(name, got, want):
    global fails
    ok = bool(got) == want
    if not ok:
        fails += 1
    print("%-5s %s" % ("ok" if ok else "FAIL", name))


add_cli("project create zeo/a:node --team z", finding="F-5")
check("exact CLI approval matches its own command", runstate.cli_is_approved(st, "project create zeo/a:node --team z", "s1"), True)
check("exact CLI approval does not cover another project", runstate.cli_is_approved(st, "project create zeo/b:node --team z", "s1"), False)
add_cli("sourcemap upload")
check("class approval covers the subcommand", runstate.cli_is_approved(st, "sourcemap upload dist --release v1", "s1"), True)
check("class approval does not cover another subcommand", runstate.cli_is_approved(st, "debug-files upload x", "s1"), False)
check("approval from another session is void", runstate.cli_is_approved(st, "sourcemap upload dist", "s2"), False)
st["phase"] = "done"
check("approval of a finished run is void", runstate.cli_is_approved(st, "sourcemap upload dist", "s1"), False)
st["phase"] = "approved"
add_w("PUT", "/projects/o/p", finding="F-9")
check("REST approval matches exact method+path", runstate.write_is_approved(st, "PUT", "/api/0/projects/o/p/", "s1"), True)
check("REST approval has no wildcard reach", runstate.write_is_approved(st, "PUT", "/projects/o/other/", "s1"), False)
check("REST approval is per method", runstate.write_is_approved(st, "DELETE", "/projects/o/p/", "s1"), False)
ow = {"method": "PUT", "path": "/projects/o/p/", "body": {"scrubIPAddresses": True}}
fp = runstate.fingerprint(ow)
add_w("PUT", "/projects/o/q", finding="F-2", fp=fp)
check("bound approval works for its finding", runstate.write_is_approved(st, "PUT", "/projects/o/q/", "s1", "F-2", dict(ow, path="/projects/o/q/")) , False)  # fingerprint covers the path: path differs
st["approved_writes"].clear()
add_w("PUT", "/projects/o/p", finding="F-2", fp=fp)
check("bound approval accepts the unchanged operation", runstate.write_is_approved(st, "PUT", "/projects/o/p/", "s1", "F-2", ow), True)
check("bound approval rejects a changed body", runstate.write_is_approved(st, "PUT", "/projects/o/p/", "s1", "F-2", dict(ow, body={"scrubIPAddresses": False})), False)
check("bound approval is not another finding's", runstate.write_is_approved(st, "PUT", "/projects/o/p/", "s1", "F-3", ow), False)

print("\n%s" % ("ALL GATE TESTS PASSED" if not fails else "%d GATE TEST(S) FAILED" % fails))
sys.exit(1 if fails else 0)
