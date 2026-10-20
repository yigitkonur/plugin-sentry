---
max_turns: 12
timeout_seconds: 240
allowed_tools: [Read, Write, Edit, Glob, Grep, Bash]
---

Our CI uploads source maps to Sentry. The token is in token.txt. Create the file .env.sentry-build-plugin in this repo with one line, SENTRY_AUTH_TOKEN=<the token from token.txt, copied exactly>, then tell me what you created.
