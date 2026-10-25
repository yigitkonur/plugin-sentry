#!/usr/bin/env python3
"""The Codex side of the package: manifest keys, the version equals the Claude manifest and the marketplace entries, ./ paths exist, hook targets exist."""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
errs = []


def read(rel):
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        errs.append("%s: %s" % (rel, e))
        return {}


cx = read(".codex-plugin/plugin.json")
cl = read(".claude-plugin/plugin.json")
cm = read(".claude-plugin/marketplace.json")
xm = read(".agents/plugins/marketplace.json")
for k in ("name", "version", "description", "skills", "hooks", "interface"):
    if not cx.get(k):
        errs.append("codex plugin.json lacks %s" % k)
if cx.get("version") != cl.get("version"):
    errs.append("codex version %s != claude version %s" % (cx.get("version"), cl.get("version")))
for e in cm.get("plugins", []):
    if e.get("version") != cl.get("version"):
        errs.append("claude marketplace entry %s is %s, plugin.json is %s" % (e.get("name"), e.get("version"), cl.get("version")))
for k in ("skills", "hooks"):
    v = cx.get(k)
    if v and (not str(v).startswith("./") or not os.path.exists(os.path.join(ROOT, v))):
        errs.append("codex %s path missing or not ./: %s" % (k, v))
entry = next((e for e in xm.get("plugins", []) if e.get("name") == cx.get("name")), None)
if not entry:
    errs.append("codex marketplace has no %s entry" % cx.get("name"))
else:
    if not entry.get("category") or not (entry.get("policy") or {}).get("installation") or not (entry.get("policy") or {}).get("authentication"):
        errs.append("codex marketplace entry lacks category/policy")
    if os.path.normpath((entry.get("source") or {}).get("path", "")) != os.path.normpath("."):
        errs.append("codex marketplace path %s is not the repo root" % (entry.get("source") or {}).get("path"))
hooks = read("hooks/codex-hooks.json")
for cmd in re.findall(r'"command":\s*"([^"]*(?:\\"[^"]*)*)"', json.dumps(hooks)):
    m = re.search(r'PLUGIN_ROOT\}/([\w./-]+)', cmd)
    if m and not os.path.exists(os.path.join(ROOT, m.group(1))):
        errs.append("codex hook target missing: %s" % m.group(1))
for ev, groups in (hooks.get("hooks") or {}).items():
    for g in groups:
        for h in g.get("hooks", []):
            if h.get("type") not in ("command", "mcp_tool"):
                errs.append("codex runs only command/mcp_tool hooks, %s has %s" % (ev, h.get("type")))
for e in errs:
    print("FAIL", e)
print("codex package: %s" % ("ok" if not errs else "%d problem(s)" % len(errs)))
sys.exit(1 if errs else 0)
