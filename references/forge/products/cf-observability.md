# Cloudflare observability next to Sentry (product id: cf-observability)

Cloudflare Workers has its own Logs, Traces and Issues. Workers Logs is on by default for newly created Workers; Traces and Issues are opt-in. Sentry reports the same Worker. This module decides which system owns which signal, so nothing is stored, billed or paged twice by accident. The owner is a policy answer (`cloudflare.owner`: `split`, `sentry`, `both`, `otlp`); an unset answer is a decision finding, never a guess.

## Fit
Applies to units with the Cloudflare overlay (`data/signals.tsv` row `cf-observability`, `fw:cloudflare`): Workers, Pages, and frameworks deployed on Workers (Astro, Hono, SvelteKit).

| Repo evidence | Where to look | What it means |
|---|---|---|
| `observability` block | `wrangler.jsonc`, `wrangler.json`, `wrangler.toml` (also under `env.<name>`) | Workers Logs (`enabled`), `logs`, `traces`, `issues`. The Logs page shows `observability` per environment; it does not show that for traces or issues |
| `destinations` under `observability.logs` or `.traces` | same file | OpenTelemetry export; a Sentry destination exists only in the Cloudflare dashboard, so UI-only: ask, else UNVERIFIED |
| `consoleLoggingIntegration(`, `Sentry.logger.` | the Worker entry or `instrument.server.*` | Sentry Logs fed from `console.*` or called directly |
| `tracesSampleRate`, `tracesSampler` | Sentry options callback | Sentry tracing on |
| no `observability` key | wrangler config | The file does not say whether Workers Logs writes (the Logs page: add the setting to write logs); UNVERIFIED without account access |

Worth auditing whenever a Cloudflare unit has Sentry plus any Cloudflare observability, and in baseline mode (Sentry absent) so the init respects the owner. Not worth a finding: a Cloudflare unit with no Sentry and policy `split` that only needs errors and traces added.

## Properly configured
Rule: one store per signal, chosen by the policy answer. Cloudflare facts come from its docs; Sentry facts from the Cloudflare SDK pages.

| `cloudflare.owner` | wrangler `observability` | Sentry init | Source |
|---|---|---|---|
| `split` (recommended) | `enabled: true` keeps Workers Logs; no `traces`, no `issues` | tracing set; no `consoleLoggingIntegration`; `Sentry.logger` not used for lines Workers Logs already keep | Workers Logs page; Sentry Cloudflare Logs page |
| `sentry` | `enabled` false or absent, no `traces`, no `issues` | tracing plus `consoleLoggingIntegration` or `Sentry.logger` | same |
| `both` | any | any | cost and alert ownership only (checks `cf.export-persist`, `cf.issues-alerts`) |
| `otlp` | `logs` and `traces` list the Sentry destination names in `destinations`; `persist` set on purpose | no Sentry tracing in the Worker (two trace systems otherwise); the SDK still reports errors | Cloudflare OpenTelemetry export; Cloudflare Export to Sentry |

- Sentry Logs on Cloudflare: enabled by default from SDK 10.71.0 (`enableLogs` below that, removed in v11; see `data/stale-apis/js.tsv`). The Sentry page shows `consoleLoggingIntegration` as the way to capture `console.*` calls as Sentry Logs, so double capture of console output needs that integration (or a direct `Sentry.logger` call).
- Workers Logs: "All newly created Workers will come with the observability setting enabled by default". `head_sampling_rate` (0 to 1, default 1) samples whole requests; `invocation_logs` false drops the per-request invocation log.
- Workers tracing is a separate, automatic system: `observability.traces.enabled`. The tracing page says `observability.enabled` alone does not turn it on while it is in early beta.
- OpenTelemetry export covers Workers traces and logs (incl. `console.log()`), not metrics. A destination does nothing until the Worker's wrangler config names it and is redeployed; data takes minutes.
- Sentry endpoints (Cloudflare page): the paths `/api/<PROJECT_ID>/integration/otlp/v1/traces` and `/logs` on your Sentry host, custom header `x-sentry-auth: sentry sentry_key=<SENTRY_PUBLIC_KEY>`, configured in the Cloudflare dashboard only.

## Checks
| check id | read | passes when |
|---|---|---|
| cf.logs-owner | wrangler `observability.enabled` and `.logs`; Worker entry and options callback for `consoleLoggingIntegration`, `Sentry.logger`; the policy `cloudflare.owner` | Console output goes where the policy says. `split`: no Sentry console integration. `sentry`: Cloudflare logs off. `both`: any. Policy unset: file one decision finding listing both settings |
| cf.traces-owner | wrangler `observability.traces`; Sentry `tracesSampleRate` or `tracesSampler`; `destinations` | `split`: Cloudflare traces off, Sentry tracing on. `sentry`: Cloudflare traces off. `otlp`: Worker Sentry tracing off, export on. `both`: any |
| cf.export-persist | `observability.logs.persist` and `.traces.persist` next to `destinations` | `persist` is written down on purpose. Sentry as the only wanted store means false; the default stores in Cloudflare and counts toward its usage from 2026-12-01 |
| cf.issues-alerts | wrangler `observability.issues`; Sentry alert rules (org probe `alerting`, else UNVERIFIED) | One paging owner for Worker errors unless the policy says `both` |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Same line in Workers Logs and Sentry Logs | `consoleLoggingIntegration` on while `observability.enabled` | Pick the owner; remove the integration (`split`) or turn Cloudflare logs off (`sentry`) | Sentry Cloudflare Logs, Console Integration; Workers Logs |
| Every request has a Cloudflare trace and a Sentry trace | `observability.traces.enabled` plus a Sentry sample rate | One tracing system per path | Workers tracing; Sentry Cloudflare guide |
| Sentry destination created, nothing arrives | Creating a destination does not start export | Name it in `destinations` in wrangler config, redeploy, wait minutes | Cloudflare Export to Sentry, step 4 |
| Data stored and counted in Cloudflare although exported | `persist` defaults to true | `persist: false` when Sentry is the only store | Cloudflare OpenTelemetry export |
| Sentry metrics empty after moving to export | Cloudflare lists metrics as not exportable over OpenTelemetry | Use the SDK for Sentry metrics | Cloudflare OpenTelemetry export, Known limitations |
| Worker errors page twice | Cloudflare Issues automation and a Sentry alert both fire | One paging owner | Workers Issues |
| Exported traces do not join SDK errors | The pages fetched do not describe linking for Workers | Do not promise it; mark UNVERIFIED and test (Verify 4) | Unconfirmed |

## Volume, cost and overhead
- Cloudflare: persisted logs and traces count toward Cloudflare Observability ingestion and storage from 2026-12-01 (OpenTelemetry export page); `head_sampling_rate` bounds it on both sides.
- Sentry log volume and billing: see the `quota` module. Console capture of a chatty `console.log` adds to it, which is why `split` keeps console output in Cloudflare.
- Overhead: no figure is on the pages fetched.

## Verify (R6)
1. `split`: deploy to a test Worker, hit a route that logs one line and one that throws. `npx wrangler tail` shows both; `sentry log list <org>/<project> -q "<marker text>" --period 1h` returns nothing; the error is a Sentry issue with a trace.
2. `sentry`: the same line appears in `sentry log list`, and Workers Logs holds none (dashboard, UI-only: UNVERIFIED unless the user reads it).
3. `otlp`: after redeploy, wait several minutes, then `sentry log list` shows the marked line. Remove the marked routes afterwards.
4. Linking exported traces to SDK errors is untested in these pages: record the result, do not assume it.

## Sources
- https://developers.cloudflare.com/workers/observability/
- https://developers.cloudflare.com/workers/observability/logs/workers-logs/
- https://developers.cloudflare.com/workers/observability/logs/real-time-logs/
- https://developers.cloudflare.com/workers/observability/traces/
- https://developers.cloudflare.com/workers/observability/issues/
- https://developers.cloudflare.com/workers/observability/opentelemetry-export/
- https://developers.cloudflare.com/observability/export/opentelemetry/sentry/
- https://docs.sentry.io/platforms/javascript/guides/cloudflare/logs/
- https://docs.sentry.io/concepts/otlp/

## Identifiers
```identifiers
head_sampling_rate | https://developers.cloudflare.com/workers/observability/logs/workers-logs/
invocation_logs | https://developers.cloudflare.com/workers/observability/logs/workers-logs/
persist | https://developers.cloudflare.com/workers/observability/opentelemetry-export/
destinations | https://developers.cloudflare.com/workers/observability/opentelemetry-export/
consoleLoggingIntegration | https://docs.sentry.io/platforms/javascript/guides/cloudflare/logs/
enableLogs | https://docs.sentry.io/platforms/javascript/guides/cloudflare/logs/
```

## Unconfirmed
- `tracesSampleRate`, `tracesSampler`: named from the Cloudflare module (`platforms/cloudflare`), which declares them with their page.
- Whether traces exported by Cloudflare link to errors the SDK reports for the same request: no fetched page says. Test it (Verify 4).
- Cloudflare Observability prices after 2026-12-01: the pricing page was not fetched.
