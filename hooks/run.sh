#!/usr/bin/env bash
# Hook entry. Cheap substring prefilters decide whether Python starts at all (a normal edit costs a few ms).
# Hosts: Claude Code (no second argument) or Codex (second argument "codex").
# Modes: CLAUDE_PLUGIN_OPTION_HOOK_MODE = on | quiet | off (absent = on); SENTRY_PLUGIN_HOOKS=off disables everything.
name="${1:-}"
[ -n "${2:-}" ] && export SENTRY_PLUGIN_HOST="$2"   # codex-hooks.json passes "codex"; Claude Code passes nothing
[ "${SENTRY_PLUGIN_HOOKS:-on}" = "off" ] && exit 0
[ "${CLAUDE_PLUGIN_OPTION_HOOK_MODE:-on}" = "off" ] && exit 0
input="$(cat)"
case "$name" in
  guard-write) case "$input" in *sntry*|*AUTH_TOKEN*|*authToken*|*auth_token*|*client_secret*|*sentry:auditor*|*run.json*) ;; *)
                 { [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && case "$input" in *"$CLAUDE_PLUGIN_ROOT"*) false;; *) true;; esac; } && exit 0;; esac;;
  gate-bash)   case "$input" in *[Ss]entry*|*SENTRY*|*sntry*|*run.json*) ;; *) exit 0;; esac;;
  stale-api)   case "$input" in *[Ss]entry*|*SENTRY*) ;; *) exit 0;; esac;;
  stop-gate)   [ -z "${CLAUDE_PROJECT_DIR:-}" ] || [ -f "$CLAUDE_PROJECT_DIR/.sentry-plugin/run.json" ] || exit 0;;   # Codex sets no project dir: the engine finds the root from the hook cwd
esac
here="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SENTRY_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-$here/..}}"
printf '%s' "$input" | exec python3 -I -S "$SENTRY_PLUGIN_ROOT/engine/run.py" hook "$name"
