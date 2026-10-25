#!/usr/bin/env bash
# Vendor Sentry's own reference docs from getsentry/sentry-for-ai (MIT) into references/upstream/ at a pinned commit.
#   scripts/sync-upstream.sh            re-vendor at the pinned SHA below
#   scripts/sync-upstream.sh --latest   vendor origin/main and print the new SHA (review the diff, then update PIN)
# Content is copied verbatim; nothing under references/upstream/ is edited by hand. NOTICE carries the attribution.
set -euo pipefail

PIN="224af963a2bc17c455a368bfaaa5b570dcd6822f"
REPO="https://github.com/getsentry/sentry-for-ai.git"
here="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"
dest="$root/references/upstream"
# what we vendor: slow-changing concepts and procedures. Per-platform setup and span conventions are fetched live.
INCLUDE=(concepts debug-artifacts releases first-error-setup.md new-project.md sdk-docs.md auth-token.md search-query-language.md setup-verification.md)

ref="$PIN"
[ "${1:-}" = "--latest" ] && ref="HEAD"

tmp="$(mktemp -d)"          # fresh directory for the downloaded content; scripts live elsewhere
trap 'rm -rf "$tmp"' EXIT
git clone -q --filter=blob:none --no-checkout --depth 1 "$REPO" "$tmp/up"
cd "$tmp/up"
if [ "$ref" != "HEAD" ]; then git fetch -q --depth 1 origin "$ref"; fi
git sparse-checkout init --cone >/dev/null 2>&1 || true
git sparse-checkout set src/references >/dev/null
git checkout -q "$( [ "$ref" = HEAD ] && echo FETCH_HEAD || echo "$ref" )" 2>/dev/null || git checkout -q "$ref"
sha="$(git rev-parse HEAD)"
date="$(git log -1 --format=%cI)"

rm -rf "$dest"
mkdir -p "$dest"
for item in "${INCLUDE[@]}"; do
  if [ -e "src/references/$item" ]; then
    mkdir -p "$dest/$(dirname "$item")"
    cp -R "src/references/$item" "$dest/$item"
  else
    echo "warning: src/references/$item not found upstream" >&2
  fi
done
git show "$sha:LICENSE" > "$dest/LICENSE"
cat > "$dest/UPSTREAM.json" <<EOF
{
  "repo": "https://github.com/getsentry/sentry-for-ai",
  "sha": "$sha",
  "commit_date": "$date",
  "license": "MIT",
  "path": "src/references",
  "included": $(printf '%s\n' "${INCLUDE[@]}" | python3 -c 'import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))')
}
EOF
n="$(find "$dest" -name '*.md' | wc -l | tr -d ' ')"
echo "vendored $n markdown files from sentry-for-ai@$sha ($date) into references/upstream/"
[ "$ref" = HEAD ] && echo "NEW SHA: $sha  (update PIN in this script after reviewing the diff)" || true
