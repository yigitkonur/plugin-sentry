#!/usr/bin/env bash
# One command that proves the repo is shippable. Exit 1 on the first failing stage.
#   scripts/check.sh            everything (needs network for docs-backed checks)
#   scripts/check.sh --offline  skip the stages that fetch docs.sentry.io
set -u
cd "$(dirname "$0")/.."
OFFLINE=0; [ "${1:-}" = "--offline" ] && OFFLINE=1
PY="${PYTHON:-python3}"
fail=0
stage() { printf '\n== %s\n' "$1"; }
run() { "$@" || { echo "FAILED: $*"; fail=1; }; }

stage "python compile ($($PY --version 2>&1))"
run $PY -m compileall -q engine scripts

stage "fixtures: detect output equals the recorded expectation"
out=$($PY scripts/fixtures.py check 2>&1); rc=$?
echo "$out" | grep -v ' ok$' || true
echo "$(echo "$out" | grep -c ' ok$') fixtures ok"
[ "$rc" = 0 ] || { echo "FAILED: fixtures"; fail=1; }

stage "plugin manifest and component validation (claude plugin validate --strict)"
if command -v claude >/dev/null 2>&1; then run claude plugin validate --strict .; else echo "claude CLI not installed: skipped"; fi

if [ "$OFFLINE" = 0 ]; then
  stage "reference modules: structure, check ids, identifiers present in their cited pages"
  bin/sentry-ctx ref verify | $PY -I -c 'import sys,json; r=json.load(sys.stdin); bad=[x for x in r if not x.get("ok",True)]; [print(x["name"], x["errors"][:5]) for x in bad]; print(len(r), "modules,", len(bad), "failing"); sys.exit(1 if bad else 0)' || fail=1
  stage "stale-API tables: every name appears in its source page"
  run $PY scripts/check-stale-apis.py
  stage "links: every URL in the repo resolves to a real page"
  run $PY scripts/check-links.py
fi

stage "secrets: no Sentry token shapes, personal paths or private DSN keys in tracked files"
if git rev-parse --git-dir >/dev/null 2>&1; then
  hits=$(git grep -n -E 'sntry[usai]_[A-Za-z0-9_+/=-]{20,}' -- . ':!evals/fixtures' ':!evals/expected' ':!data/ref-allow.txt' | grep -v -E 'sntry\[usai\]|sntry[usai]_<|sntry[usai]_\.\.\.|sntrys_[A-Za-z0-9]{0,8}$' || true)
  [ -n "$hits" ] && { echo "$hits" | head; fail=1; } || echo "no token shapes"
  paths=$(git grep -n -E '/Users/[a-z][A-Za-z0-9_-]+/' -- . ':!evals/fixtures' ':!evals/expected' ':!references/upstream' ':!PORT.md' | grep -v -E '/Users/(<name>|name|you|me|user|\.\.\.)' || true)
  [ -n "$paths" ] && { echo "$paths" | head; fail=1; } || echo "no personal paths"
fi

[ "$fail" = 0 ] && echo "
ALL CHECKS PASSED" || { echo "
CHECKS FAILED"; exit 1; }
