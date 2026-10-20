#!/usr/bin/env bash
set -e
git init -q .
cat > package.json <<'JSON'
{"name":"demo","version":"1.0.0","private":true,"dependencies":{"next":"16.4.2","react":"19.3.0","react-dom":"19.3.0","@sentry/nextjs":"11.8.0"}}
JSON
cat > package-lock.json <<'JSON'
{"name":"demo","version":"1.0.0","lockfileVersion":3,"requires":true,"packages":{"":{"name":"demo","version":"1.0.0","dependencies":{"next":"16.4.2","@sentry/nextjs":"11.8.0"}},"node_modules/@sentry/nextjs":{"version":"11.8.0"},"node_modules/next":{"version":"16.4.2"}}}
JSON
cat > instrumentation-client.ts <<'TS'
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  tracesSampleRate: 0.1,
});
TS
git add -A && git -c user.name=t -c user.email=t@example.invalid commit -qm init
