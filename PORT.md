# Porting map from the earlier Sentry material

This plugin replaces three earlier sources. Every file of each one is accounted for below: where its intent lives now, or why it was
dropped. Official Sentry documentation won wherever they disagreed (see the conflict log in the planning notes; the headline
errors were: `sentry` and `sentry-cli` are one tool, the org-token regex missed every org token, the macOS init template did not
compile, and JS SDK v11 invalidated most generic option advice).

Legend: **kept** = same intent, rewritten and re-verified; **merged** = folded into another file; **corrected** = the old claim was wrong
and the new text says what the docs say; **dropped** = not carried over, with the reason; (E8) = written in the breadth pass.

## Source 1: `use-sentry` (generic skill)

| Old file | New home | Disposition |
|---|---|---|
| `SKILL.md` | `skills/` (start, audit, init, apply, ...), `references/forge/flows/`, `skills/ground-rules` | merged; the Mode 1/2/3 decision tree became detection-driven routing |
| `agents/openai.yaml` | - | dropped: Codex packaging; the engine is host-neutral so a port stays cheap |
| `modes/mode-1-init.md` | `flows/init`, platform modules | kept |
| `modes/mode-2-audit.md` | `flows/audit`, `data/checks.tsv` (60 checks) | kept; checks now have ids, severities and a validated ledger |
| `modes/mode-3-debug.md` | `skills/triage`, `references/forge/triage.md` | corrected: Seer last and only on request (it spends money); `issue view --json` first |
| `architectures/nextjs-app-router.md` | `platforms/nextjs` | corrected: `instrumentation-client`, `@sentry/nextjs/config`, removed build options |
| `architectures/python-fastapi.md` | `platforms/python` | corrected: legacy profiling option, invented `proxy` option |
| `architectures/go-gin.md` | `platforms/go` | kept |
| `architectures/fastify-rest-api.md` | `platforms/node` | corrected: v11 captures framework errors automatically; no request headers in `extra` |
| `architectures/cloudflare-workers.md` | `platforms/cloudflare` (E8) | corrected: wrong Pages import, wrong drain location |
| `architectures/expo-mobile.md` | `platforms/react-native` (E8) | corrected: mask components, upload command |
| `architectures/macos-appkit-swiftui.md`, `swift-apple-ecosystem.md` | `platforms/apple-macos`, `apple`, `apple-ios` | corrected: iOS-only options are compile errors on macOS; `profilesSampleRate` removed in Cocoa 9 |
| `architectures/ai-llm-monitoring.md` | `products/ai` (E8) | corrected: integration names, `gen_ai.*` attributes, capture off by default |
| `architectures/mcp-server-sentry.md` | `products/mcp` (E8) | corrected |
| `architectures/cli-bundled-scripts.md` | `products/core` (flush before exit) | merged |
| `architectures/cloud-browsers-playwright.md` | `products/privacy` (URL token redaction) | merged; the niche setup itself is dropped |
| `architectures/sentry-mcp-integration.md` | - | dropped: this plugin is CLI-first and ships no MCP server (Sentry's official plugin ships one) |
| `breadcrumbs-context/custom-tags-context.md`, `device-runtime-context.md` | `products/errors` | corrected: use the `environment` option, not a tag |
| `breadcrumbs-context/system-breadcrumbs.md`, `ui-breadcrumbs.md` | `products/privacy` | corrected: masking attributes apply to Replay only |
| `breadcrumbs-context/user-feedback-api.md` | `products/feedback` (E8) | corrected: option and API names |
| `cli-tooling/legacy-sentry-cli.md` | `data/cli-map.json`, `references/forge/cli.md` | corrected: `sentry-cli` 3.x and `sentry` v4 are one tool; the map ports every command |
| `cli-tooling/modern-sentry-cli.md` | `references/forge/cli.md` | corrected: `dsn` and `monitor` subcommands |
| `cli-tooling/cli-troubleshooting.md` | `references/forge/cli.md` (exit codes) | merged |
| `cli-tooling/project-mapping-config.md` | - | dropped: the CLI auto-detects org and project; overrides live in `.sentry-plugin/policy.md` |
| `error-tracking/exception-capture.md` | `products/errors`, `products/core` | corrected |
| `error-tracking/fingerprinting-grouping.md` | `products/errors` | corrected: invented matcher and variable |
| `error-tracking/inbound-filters.md` | `products/quota` | kept; plan note and filter list corrected |
| `error-tracking/merges-and-splits.md` | - | dropped: wrong payloads; merges are mutations, gated by the write hook |
| `error-tracking/sourcemaps-pipeline.md` | `products/debug-artifacts` | corrected: Debug IDs need SDK >= 7.47.0, `sentry sourcemap` flow |
| `logging-analytics/structured-logs.md` | `products/logs` (E8) | corrected: `enableLogs` is gone in JS v11 |
| `logging-analytics/log-explorer-queries.md` | `references/forge/triage.md` | corrected: `severity:` / `trace_id:` |
| `logging-analytics/discover-query-builder.md` | - | dropped: the Discover UI was replaced; `sentry explore` is documented in the CLI guide |
| `logging-analytics/pin-to-top-logs.md` | - | dropped: described a setting that does not exist (it is per-project Event Highlights) |
| `network-tunneling/*` | `platforms/browser-spa` (tunnel, DSN host validation) | corrected: client SDKs only; envelope format; relative URL |
| `performance-replay/distributed-tracing-spans.md` | `products/tracing` | corrected: invented `span.setMeasurement`, renamed `db.*` attributes, span streaming |
| `performance-replay/session-replay.md` | `products/replay` (E8) | corrected: iOS is the official mobile target |
| `performance-replay/cron-monitors.md` | `products/crons` (E8) | corrected: ingest endpoint, no "bidirectional" heartbeats |
| `performance-replay/spotlight-local-dev.md` | `products/dev-spotlight` (E8) | corrected: events also go to Sentry when a DSN is set |
| `performance-replay/asynclocalstorage-context.md` | - | dropped: redundant since SDK v8 isolates scopes per request |
| `privacy-redaction/credential-redaction-rules.md` | `products/privacy`, hook `guard-write`, `data/` token regexes | corrected: the old regex missed every `sntrys_` org token |
| `privacy-redaction/url-jwt-sanitization.md` | `products/privacy` | kept |
| `research/research-mcp-protocol.md` | - | dropped: MCP is not shipped |
| `research/stack-keyword-matrices.md` | `data/detect/*.json`, `data/signals.tsv` | merged into the detection tables |
| `verification/live-synthetic-verification.md`, `post-fix-verification.md` | `references/forge/verification-ladder.md`, `agents/verifier` | kept; now a ladder with evidence per rung |
| `verification/security-audit-checklist.md` | `products/privacy` (priv.* checks) | corrected token regex |
| `verification/offline-test-isolation.md` | `products/core` (E8) | corrected: Node >= 20.19 with `--import` on v11 |
| `scripts/audit-project.sh` | `engine/` (detect, stale) | replaced: it matched any `sourceMap` and missed bundler plugins |
| `scripts/detect-creds.sh` | `sentry-ctx doctor`, `tokens.py` | replaced: it truncated org tokens at the first `=` |
| `scripts/triage-issues.sh` | `skills/triage` | replaced: it took a table header as the org |
| `scripts/verify-tunnel.sh` | - | dropped: malformed envelope and false "reachable" |

## Source 2: `build-sentry-macos-swift`

| Old file | New home | Disposition |
|---|---|---|
| `SKILL.md` (rules) | `references/forge/ground-rules.md`, `platforms/apple-macos` | merged; the seven rules became thirteen general ones |
| `agents/openai.yaml` | - | dropped (Codex packaging) |
| `explore-the-repo.md` | `engine/sentry_ctx/detect` (apple block: sandbox, entitlements, Sparkle) | kept as code |
| `choosing-what-to-capture.md` | `data/signals.tsv` (applicability per product) | kept as data |
| `install-and-initialize.md` | `platforms/apple-macos`, `platforms/apple` | corrected: the init template did not compile on macOS |
| `macos-support-matrix.md` | `platforms/apple-macos` (support matrix) | kept; wrong rows fixed |
| `crash-and-hangs.md` | `platforms/apple-macos` | kept; MetricKit scope and hang deprecation corrected |
| `privacy-and-scrubbing.md` | `platforms/apple-macos` (Privacy), `products/privacy` | corrected: IP inference is gated by `sendDefaultPii` since 8.56 |
| `tracing-releases-dsym.md` | `platforms/apple-macos` (Release and artifacts) | corrected: default release name, Run Script requirements |
| `advanced-instrumentation.md` | `platforms/apple-macos`, `products/logs` (E8) | kept |
| `verify-and-troubleshoot.md` | `references/forge/verification-ladder.md`, `platforms/apple-macos` (Verify recipe) | kept |

## Source 3: `plugin-sentry-cli`

| Old file | New home | Disposition |
|---|---|---|
| `.claude-plugin/*`, `README.md` | `.claude-plugin/`, `README.md` | rewritten; the old plugin name collided with Sentry's official `sentry-cli` plugin |
| `skills/sentry/SKILL.md` | `skills/triage` | kept: the funnel (rank, view, corroborate, Seer last) is the valuable part; token-efficiency and safety rules carried over |
| `skills/sentry/references/cli-reference.md` | `references/forge/cli.md`, `forge/triage.md` | corrected: CLI version, sort values, target syntax; per-command reference is left to Sentry's own skill |
| `skills/sentry/references/project-map.md` | - | dropped: the CLI auto-detects org and project |
