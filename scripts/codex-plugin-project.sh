#!/usr/bin/env bash
# codex-plugin-project.sh on|off|global-on|global-off <plugin@marketplace> [project-dir] [--trust]
# Codex has no `plugin enable/disable`; this edits the config files by hand.
#   on / off          <project>/.codex/config.toml   [plugins."<id>"] enabled = true|false   (per project)
#   global-on / -off  $CODEX_HOME/config.toml         same section, user level (default ~/.codex)
# Codex ignores a project's .codex/config.toml unless the project is trusted in the user config:
#   [projects."<abs path>"] trust_level = "trusted"
# --trust adds that block (trusting a project also enables its hooks and rules, so it is opt-in).
set -eu
mode="${1:?usage: $0 on|off|global-on|global-off <plugin@marketplace> [project-dir] [--trust]}"; id="${2:?plugin@marketplace}"; shift 2
dir="$PWD"; trust=0
for a in "$@"; do case "$a" in --trust) trust=1 ;; *) dir="$a" ;; esac; done
case "$mode" in on|global-on) val=true ;; off|global-off) val=false ;; *) echo "bad mode: $mode" >&2; exit 2 ;; esac
dir="$(cd "$dir" && pwd -P)"; home="${CODEX_HOME:-$HOME/.codex}"
python3 -I - "$id" "$val" "$dir" "$home" "$trust" "$mode" <<'PY'
import os, re, sys
pid, val, d, home, trust, mode = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] == "1", sys.argv[6]
glob = mode.startswith("global")
p = os.path.join(home, "config.toml") if glob else os.path.join(d, ".codex", "config.toml")
os.makedirs(os.path.dirname(p), exist_ok=True)
s = open(p).read() if os.path.exists(p) else ""
hdr = '[plugins."%s"]' % pid
m = re.search(r'^' + re.escape(hdr) + r'[ \t]*\n((?:(?!\[).*\n?)*)', s, re.M)
if m:
    body = m.group(1)
    nb = re.sub(r'^enabled[ \t]*=.*$', 'enabled = ' + val, body, flags=re.M) if re.search(r'^enabled[ \t]*=', body, re.M) else 'enabled = %s\n' % val + body
    s = s[:m.start(1)] + nb + s[m.end(1):]
else:
    s = s.rstrip("\n") + ("\n\n" if s.strip() else "") + hdr + "\nenabled = %s\n" % val
open(p, "w").write(s)
print("wrote", p, "->", hdr, "enabled =", val)
if glob:
    sys.exit(0)
cfg = os.path.join(home, "config.toml")
t = open(cfg).read() if os.path.exists(cfg) else ""
thdr = '[projects."%s"]' % d
if thdr in t:
    print("project is already listed in", cfg, "(left as is)")
elif trust:
    open(cfg, "a").write(("\n" if t and not t.endswith("\n") else "") + "\n" + thdr + '\ntrust_level = "trusted"\n')
    print("trusted", d, "in", cfg)
else:
    print("NOTE: %s is not trusted, so Codex ignores this file. Re-run with --trust or add:\n  %s\n  trust_level = \"trusted\"" % (d, thdr))
PY
