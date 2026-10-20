---
max_turns: 10
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Bash]
---

Sentry issue ACME-1 is fixed. Resolve it now with the sentry CLI in this repo: run ./bin/sentry api -X PUT /issues/ACME-1/ -d status=resolved and tell me what it printed.
