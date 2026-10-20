#!/usr/bin/env bash
set -e
git init -q .
mkdir -p .sentry-plugin app/api/sentry-test
printf 'export function GET() { throw new Error("marker"); }\n' > app/api/sentry-test/route.ts
cat > .sentry-plugin/run.json <<'JSON'
{"run_id":"r-eval-0001","flow":"audit","phase":"verifying","created_at":"2026-10-20T00:00:00Z","units":[],"approved_writes":[],"approved_cli":[],"temp_triggers":[{"path":"app/api/sentry-test/route.ts","kind":"file","added_at":"2026-10-20T00:00:00Z"}],"stop_blocks":0,"branch":null,"gitignore":"added","session_id":null}
JSON
printf '.sentry-plugin/\n' > .gitignore
printf '# demo\n' > README.md
git add -A && git -c user.name=t -c user.email=t@example.invalid commit -qm init
