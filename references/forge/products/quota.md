# Quota and volume control (product id: quota)

## Fit
Always audit when there is org access: every signal the repo emits bills somewhere. Evidence that raises priority: a flat 1.0 trace rate in production, logs or metrics on with free-form attributes, Session Replay or profiling enabled, attachments on (screenshots, minidumps), one DSN shared by prod and staging or CI, queue/retry code that captures an error per attempt.
Not worth proposing: no org access (the org rows are UNVERIFIED, never n/a; the SDK-side rows still run), a trial org (spike protection is not applied during trials, so "off" and "on" cannot be told apart), a repo with no Sentry SDK. Concept background: references/upstream/concepts/reduce-volume.

## Properly configured
Order of levers, cheapest and most precise first (same order as the docs): spike protection on, key rate limits as a ceiling, inbound filters for known noise, SDK sampling, SDK hooks, size bounds.

| Layer | Right | Applies to | Source |
|---|---|---|---|
| Spike protection | On for every production project; notification action added separately (enabling it does not notify) | errors, spans/transactions, attachments only | spike-protection page |
| Key rate limits | A minute-based ceiling per DSN key, derived from the 30-day key-usage graph; a second unlimited key for staging is the documented pattern; Business or Enterprise plan | errors (and attachments org-wide limit for stored crash reports) | manage-event-stream-guide |
| Inbound filters | Browser extensions, localhost, web crawlers, legacy browsers, health-check transactions toggled on where relevant; custom error-message / release filters need Business, Enterprise or Trial | see "Filters by signal" | filtering page |
| SDK sampling | JS v11 / Python 2.x / Cocoa 9: errors `sampleRate` (JS) / `sample_rate` (Python) / `sampleRate` (Cocoa) stay 1.0 unless a rate limit does not fit; traces use `tracesSampleRate` / `traces_sample_rate` or a sampler | errors, spans | key-terms sample rates |
| SDK hooks | `beforeSend` (errors), `beforeSendLog` / `before_send_log`, `beforeSendMetric` / `before_send_metric` drop at the source | errors, logs, metrics | quota pages |
| Dynamic sampling | Do not design around it: only orgs that already have it keep it; new customers use SDK sampling | spans, transactions (never errors) | dynamic-sampling page |

Filters by signal (what really applies, from the filtering page):

| Signal | Inbound filters that apply | Do not apply |
|---|---|---|
| Errors | extensions, localhost, crawlers, legacy browsers, hydration, ChunkLoadError, IP, error message, release | error-message filter never matches transactions or minidumps |
| Spans / transactions | health-check names (glob list on the page), release, IP | error-message filter |
| Replays | IP, releases, request URLs, user-agents | error message, extensions, crawlers, legacy browsers, hydration, ChunkLoadError, health checks |
| Logs | log message (glob), releases | everything else, including IP and user-agent |
| Metrics | metric name (glob), releases | everything else |
| Attachments | indirect: filtering the error filters its attachments | no direct attachment filter |

Allowed Domains only checks `Origin` or `Referer`; requests without them (server SDKs) always pass, so it is not a quota control for backends.

SDK-family notes (check the installed major, then `data/stale-apis/js.tsv`, `python.tsv`, `cocoa.tsv`):
- JS v11: `beforeSendTransaction` and `ignoreTransactions` are inert (span streaming default); drop spans with `ignoreSpans`, which in stream mode is evaluated at span start; `beforeSendSpan` can only modify spans, not drop them (options page). `enableLogs` and `enableMetrics` are removed in v11 (stale table), although the quota pages still show them in examples.
- Python 2.x: `before_send_log`, `before_send_metric`, `traces_sampler`; 3.0 alpha removed `enable_tracing`, `profiles_sample_rate` and `before_send_transaction` (stale table).
- Cocoa 9: `beforeSendLog`, `beforeSendMetric`, `tracesSampler`; `profilesSampleRate` removed (stale table).

## Checks
| check id | read | passes when |
|---|---|---|
| quota.controls | `sentry api -X GET /projects/<org>/<project>/` (project `options` key `quotas:spike-protection-disabled` false; `isDynamicallySampled`, `dynamicSamplingBiases`); `sentry api -X GET /projects/<org>/<project>/keys/` (`isActive`, `rateLimit`); `sentry api -X GET /projects/<org>/<project>/filters/` | Spike protection is not disabled on each production project; each active production key has a deliberate `rateLimit` (a recorded null is a decision, not an omission) or the plan cannot set one; the extension, localhost, crawler and health-check filters are active where the unit has that traffic; no SDK or doc text in the repo promises dynamic sampling to a new org (`isDynamicallySampled` false is expected there) |
| quota.size-billed | SDK init files for logs/metrics hooks (`beforeSendLog`, `before_send_log`, `beforeSendMetric`, `before_send_metric`); grep for log/metric calls that interpolate ids or bodies; Settings > Subscription is UI-only (ask the user, else UNVERIFIED); `sentry api -X GET "/organizations/<org>/stats_v2/?field=sum(quantity)&groupBy=category&groupBy=outcome&statsPeriod=30d"` | A pay-as-you-go budget exists (logs, metrics, profiling and extra monitors cannot be bought any other way); production log level is above debug; hooks drop known-chatty entries; attributes are bounded (no user ids, request ids, free text on metrics; no whole bodies on logs or attachments); the 30-day outcome totals show no unexplained `rate_limited` volume |

Org probes are GET-only. Writing a rate limit, filter or spike-protection toggle is shown as an exact manual step or an approved `sentry api` call, never auto-applied (`references/forge/fix-safety`).

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Quota still burns after muting or ignoring an issue | Events of resolved and ignored issues still count; only Delete & Discard (Business/Enterprise) stops counting future events | Filter in the SDK or an inbound filter; use Delete & Discard for a known-irrelevant issue | manage-event-stream-guide |
| Spike protection "on" but logs/replays/metrics spike | It covers errors, spans/transactions and attachments only | Per-signal levers: hooks, sampling, filters, PAYG budget | spike-protection page |
| Data vanishes mid-month, 429 in network tab | Reserved volume and PAYG budget exhausted: later data is dropped, not charged; SDKs get `Retry-After` and drop rather than retry | Raise PAYG budget for the rollout; fix volume at the source | pricing page, manage-event-stream-guide |
| Plan relies on dynamic sampling to cut span cost | Not offered to new customers; existing orgs only | SDK sampler that inherits the parent decision | dynamic-sampling page |
| Staging noise eats production quota | One key for all environments | Second key with its own limit, or separate project | manage-event-stream-guide |
| Rate limit constantly hit | Used as a throttle instead of a ceiling | Fix the source; set the limit above the 30-day maximum, per minute | manage-event-stream-guide |
| Error-message filter does not match ProGuard-obfuscated or minidump events | Deobfuscation happens after ingestion; minidumps are not matched | Filter in the SDK, or match the obfuscated name | filtering page |
| Health-check spans still billed | Filter matches transaction names only; custom paths not in the glob list; JS v11 streams spans | Add `ignoreSpans` (JS) or a sampler returning 0 | filtering page, options page |
| Allowed Domains "does not stop" backend traffic | Requests without `Origin`/`Referer` always pass | Key rate limit or network allowlist | filtering page |
| Replay or profile volume unexpected | Rate set to 1.0 in prod (`replaysSessionSampleRate`, `replaysOnErrorSampleRate`, `profileSessionSampleRate`) | Keep the sampled/on-error asymmetry | key-terms sample rates, options page |
| Logs billed far above event count | Billed in GB, not entries; long messages and many attributes | Level threshold, `beforeSendLog` drop, log-message inbound filter | manage-logs-quota |
| Metrics bill grows | High-cardinality attributes (user ids, request ids, free text) | Bounded attributes, `beforeSendMetric`, metric-name inbound filter | manage-application-metrics-quota |
| Attachments quota exhausted | Billed by size; screenshots, minidumps, request bodies attached | Truncate values, limit stored crash reports per issue (org Security & Privacy) | manage-attachments-quota |

## Volume, cost and overhead
| Category | Billed as | Included on paid plans (pricing page) | Beyond that |
|---|---|---|---|
| Errors | events | 50k | reserved or PAYG |
| Spans | spans | 5M | reserved or PAYG |
| Replays | replays | 50 | reserved or PAYG |
| Attachments | GB | 1GB | reserved or PAYG |
| Logs | GB | 5GB | PAYG only |
| Application Metrics | GB | 5GB | PAYG only |
| Profiling (continuous, UI) | profile hours | none | PAYG only |
| Cron / uptime monitors | monitors | 1 each | PAYG only |

- The PAYG budget is shared across categories, first come first served. Prices are on the pricing page; do not quote them from here (they change).
- Transactions as a unit apply only to older plans; new volume is counted in spans.
- Only accepted data counts. Usage Stats separates Accepted, Filtered, Rate Limited (reasons: DSN limit, quota, spike protection, internal limit), Invalid and Client Discard. SDK-side drops appear as Client Discard when client reports are on (`sendClientReports` default true in JS).
- Quota changes: increases are immediate; reserved-volume decreases land at the end of the billing period; PAYG decreases within 24 hours but not below usage so far. Billing or Owner role is needed (see `references/forge/ground-rules` for who may change it: the plugin never changes billing).
- Runtime cost of these controls is nil; sampling reduces SDK overhead too.

## Verify (R6)
Proof that a control works is an outcome count, not a setting:
1. `sentry api -X GET "/organizations/<org>/stats_v2/?field=sum(quantity)&groupBy=category&groupBy=outcome&statsPeriod=30d"` (observed on sentry v4 0.47.0): `groups[].by` holds `category` and `outcome`, `totals` the `sum(quantity)`. After a filter or limit change, `filtered` or `rate_limited` rises for that category while `accepted` falls.
2. Keys: `GET /projects/<org>/<project>/keys/` returns a list; the observed shape per key is `isActive` plus `rateLimit` null or `{window, count}`.
3. Filters: `GET /projects/<org>/<project>/filters/` returns `[{id, active}]` (observed ids: browser-extensions, filtered-transaction, legacy-browsers, localhost, web-crawlers; legacy-browsers can carry a list).
4. Project detail: `GET /projects/<org>/<project>/` returns `options` with `quotas:spike-protection-disabled` (observed false on a live project).
Record each as C evidence; anything only visible in the UI (budget, notification actions) is UNVERIFIED unless the user confirms.

## Sources
- https://docs.sentry.io/pricing/quotas/
- https://docs.sentry.io/pricing/quotas/spike-protection/
- https://docs.sentry.io/pricing/quotas/manage-event-stream-guide/
- https://docs.sentry.io/pricing/quotas/manage-transaction-quota/
- https://docs.sentry.io/pricing/quotas/manage-logs-quota/
- https://docs.sentry.io/pricing/quotas/manage-application-metrics-quota/
- https://docs.sentry.io/pricing/quotas/manage-attachments-quota/
- https://docs.sentry.io/concepts/data-management/filtering/
- https://docs.sentry.io/organization/dynamic-sampling/
- https://docs.sentry.io/pricing/ , https://docs.sentry.io/product/stats/
- https://docs.sentry.io/concepts/key-terms/sample-rates/
- https://docs.sentry.io/platforms/javascript/configuration/options/ , https://docs.sentry.io/platforms/python/configuration/options/ , https://docs.sentry.io/platforms/apple/configuration/options/
- https://docs.sentry.io/api/projects/list-a-projects-client-keys/ , https://docs.sentry.io/api/projects/list-a-projects-data-filters/ , https://docs.sentry.io/api/projects/retrieve-a-project/ , https://docs.sentry.io/api/organizations/retrieve-event-counts-for-an-organization-v2/
- Vendored: references/upstream/concepts/reduce-volume, references/upstream/concepts/tracing

## Identifiers
```identifiers
sampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
tracesSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
tracesSampler | https://docs.sentry.io/platforms/javascript/configuration/options/
ignoreSpans | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendSpan | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendTransaction | https://docs.sentry.io/platforms/javascript/configuration/options/
ignoreTransactions | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendLog | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendMetric | https://docs.sentry.io/platforms/javascript/configuration/options/
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
sendClientReports | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSend | https://docs.sentry.io/platforms/javascript/configuration/options/
sample_rate | https://docs.sentry.io/platforms/python/configuration/options/
traces_sample_rate | https://docs.sentry.io/platforms/python/configuration/options/
traces_sampler | https://docs.sentry.io/platforms/python/configuration/options/
before_send_log | https://docs.sentry.io/platforms/python/configuration/options/
before_send_metric | https://docs.sentry.io/pricing/quotas/manage-application-metrics-quota/
beforeSendLog | https://docs.sentry.io/platforms/apple/configuration/options/
beforeSendMetric | https://docs.sentry.io/platforms/apple/configuration/options/
isActive | https://docs.sentry.io/api/projects/list-a-projects-client-keys/
rateLimit | https://docs.sentry.io/api/projects/list-a-projects-client-keys/
isDynamicallySampled | https://docs.sentry.io/api/projects/retrieve-a-project/
dynamicSamplingBiases | https://docs.sentry.io/api/projects/retrieve-a-project/
rate_limited | https://docs.sentry.io/api/organizations/retrieve-event-counts-for-an-organization-v2/
groupBy | https://docs.sentry.io/api/organizations/retrieve-event-counts-for-an-organization-v2/
statsPeriod | https://docs.sentry.io/api/organizations/retrieve-event-counts-for-an-organization-v2/
```

## Unconfirmed
- stats_v2 categories for spans and logs: the documented `category` choices (error, transaction, attachment, replay, profile variants, monitor) do not list spans or logs; verified on 2026-10-20 only that the endpoint answers for errors. Use Usage Stats in the UI for those, and report UNVERIFIED.
- Whether a project-level read of "spike protection enabled" is the `options` key alone: the retrieve-a-project page shows the key; the GET-only audit relies on it, but the page does not describe its semantics.
