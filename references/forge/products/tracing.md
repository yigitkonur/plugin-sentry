# Tracing (product id: tracing)

Concepts: references/upstream/concepts/tracing and references/upstream/concepts/reduce-volume (sampling is the main lever). Removed or renamed options are in `data/stale-apis/{js,python,cocoa}.tsv`; this module points to them and does not repeat them.

## Fit
- Propose when the unit is a frontend, backend, worker, serverless function or mobile app with request or job boundaries. Tracing is also what Sentry's performance issue detection needs.
- Strongest when a browser unit calls its own API (distributed trace) or when queues, caches and DB calls exist.
- Not worth proposing for a pure library or one-shot CLI with no request or job boundary.
- Never propose a flat 1.0 for production; the default proposal is a sampler or a low rate (see Properly configured).

## Properly configured
| SDK family (major) | Enable tracing | Per-trace decision | Propagation |
|---|---|---|---|
| JS v11 (browser, Node) | set `tracesSampleRate` or `tracesSampler` (one of the two is required) | `tracesSampler` wins if both are set | `tracePropagationTargets`; opt-in `propagateTraceparent` (since 10.10.0, default false) |
| Python 2.x (2.62.0+) / 3.0 alpha | `traces_sample_rate` or `traces_sampler` (default None) | sampler context keys may be missing in stream mode | `trace_propagation_targets` (default `['.*']`) |
| Go 0.50.0 | `EnableTracing` plus `TracesSampleRate` or `TracesSampler` | sampler wins | `TracePropagationTargets` (strings only, no regex); `PropagateTraceparent` |
| Java/Android 8.x | `tracesSampleRate` or `tracesSampler` | sampler wins | `tracePropagationTargets`; `propagateTraceparent` |
| Cocoa 9 | `tracesSampleRate` or `tracesSampler` | | `tracePropagationTargets` |
| .NET 6.x | `TracesSampleRate` or `TracesSampler` | | `PropagateTraceparent` |
| Ruby 7.x / PHP 4.x | `traces_sample_rate` or `traces_sampler` | | Ruby `trace_propagation_targets` |

Rules the auditor applies:
- **Sampling.** The decision is made at the head and propagates downstream. Precedence (JS): `tracesSampler`, else the parent decision, else `tracesSampleRate`; a sampler should return `inheritOrSampleWith(rate)` so parent decisions are kept. With `tracesSampleRate` at `0` no new trace starts and nothing downstream is sampled. Tracing is only off when neither option is defined; Python needs `traces_sample_rate=None`, and `0` still continues incoming traces.
- **Rate.** Docs show 1.0 as the setup and test value ("adjust in production"). Prod rate comes from traffic and the policy question on volume; health checks and other noise should be dropped by name in the sampler, critical routes (checkout, auth) kept at a higher rate.
- **Propagation.** Targets must list the API origins the frontend calls. JS browser: same-origin is propagated by default; the CORS page documents the default as `['localhost', /^\//]` (cross-origin API hosts must be added). JS Node and Python, Java, Cocoa, Ruby: all outgoing requests by default, so narrow it when third-party calls exist. JS v11 matches targets case-insensitively; the `g` and `y` regex flags are ignored.
- **CORS.** The API answering browser calls must allow `sentry-trace` and `baggage` in `Access-Control-Allow-Headers`, plus `traceparent` if `propagateTraceparent` is on.
- **JS v11 span streaming.** `traceLifecycle` defaults to `'stream'` (11.0.0); `'static'` restores transactions. In stream mode `beforeSendTransaction` and `ignoreTransactions` do nothing (inert entries in js.tsv); use `ignoreSpans` to drop and `beforeSendSpan` (modify only, guard on `is_segment`) to edit. Scope tags and extra no longer reach spans: use attributes (`setAttribute`). `ignoreSpans` is matched at span start in stream mode; narrow with the object form so child spans of the same name survive. Span ops were consolidated (dashboards, alerts, `ignoreSpans` ops must be rechecked).
- **Python.** 2.x: `trace_lifecycle` defaults to `"static"`, `"stream"` is opt-in, `ignore_spans` exists only in stream mode. 3.0 alpha: streaming only, the `trace_lifecycle` option no longer exists, `before_send_transaction`, `enable_tracing` and `propagate_traces` are removed (python.tsv).
- **Span names.** Low cardinality, templated (`GET /users/:id`); request-specific values go in attributes. JS v11 auto-instrumentation already emits low-cardinality names; `updateSpanName` is for overrides.

## Checks
| check id | read | passes when |
|---|---|---|
| trace.rate | init file(s) of every unit with tracing (`Sentry.init`, `sentry_sdk.init`, `sentry.Init`, `SentrySDK.start`); env-derived rates in config | A sampling option is set and is not a literal 1.0 on a high-volume prod unit unless a sampler or per-environment value lowers it; the sampler drops health checks and keeps critical routes; the sampler inherits the parent decision (JS: `inheritOrSampleWith`); `0` is not used to mean "off" |
| trace.propagation | frontend init (`tracePropagationTargets`), backend CORS middleware, reverse proxy / gateway header allow-lists | Every API origin the frontend calls is matched by `tracePropagationTargets`; backend CORS allows `sentry-trace` and `baggage` (and `traceparent` when `propagateTraceparent` is on); same-origin only apps are exempt |
| trace.v11-hooks | JS init files, installed major from lockfile (`sentry-ctx` detect) | On @sentry/* 11 no `beforeSendTransaction` / `ignoreTransactions` unless `traceLifecycle: 'static'` is set; filtering uses `ignoreSpans`; `beforeSendSpan` does not return null |
| trace.span-names | `startSpan`, `startSpanManual`, `startInactiveSpan`, `start_span`, `updateSpanName` call sites; sampler `name` tests | Names are templates or fixed verbs; no IDs, raw URLs, SQL values or emails interpolated; variable parts are attributes |
| trace.gaps | queue consumers/producers, cache clients, job runners, outbound HTTP wrappers next to the init | Queue and cache operations that dashboards need are covered by an integration (Redis with `cachePrefixes`, Java `enableCacheTracing` / `enableQueueTracing`) or by custom spans with the documented `op`; a trace continues across the queue message |

## Common mistakes
| Symptom | Cause | Fix (source) |
|---|---|---|
| Tracing "disabled" but spans still arrive | `tracesSampleRate: 0` (or Python `0`) keeps tracing on and still continues incoming traces | Omit both options; Python `None` (JS tracing page, Python options) |
| Filter on transactions silently does nothing after upgrade | JS v11 stream mode: no transaction events | Use `ignoreSpans` / `beforeSendSpan`, or `traceLifecycle: 'static'` (JS v10-to-v11 migration) |
| `beforeSendSpan` returns null and spans still ship | It can only modify spans | Use `ignoreSpans` (JS options) |
| Frontend and backend show as separate traces | Target does not match the API origin, or CORS blocks headers, or `traceparent` not allowed | Add origin to `tracePropagationTargets`; allow headers (CORS page) |
| Trace headers sent to third parties | Default targets are all outgoing requests on Node, Python, Java, Cocoa, Ruby | Set an explicit target list (options pages) |
| Sampler overrides upstream and traces fragment | Sampler returns a fixed rate, ignores the parent | `inheritOrSampleWith(rate)` (configure-sampling) |
| Span `ignoreSpans` rule never matches | Rule uses a name or attribute set after the span starts (stream mode) | Match on initial name/attributes; use debug logging to see initial names |
| Go requests with 404 never traced | `TraceIgnoreStatusCodes` ignores 404 by default | Set an empty slice to keep them (Go options) |
| Group explosion in Insights | IDs or SQL values in span names | Template names, move values to attributes (JS instrumentation, v10-to-v11 migration) |
| Python 3.0 alpha rejects `before_send_transaction` | Transactions removed | `before_send_span` (python.tsv) |

## Volume, cost and overhead
- Billing category: spans (pricing page "Tracing Pricing": tracing is billed in spans). Sampling is the main lever (concept reduce-volume); see products/quota for filters and rate limits.
- Typical rates: docs use 1.0 for verification and tell high-load backends to lower it or use a sampler; the plugin proposes a policy-derived rate and tells the user the number.
- JS v11 stream mode removes the 1000-span cap per transaction, so a deep trace can now ship fully; budget for that (inference from the migration page).
- Stream mode flushes every 5 seconds by default, or at 1,000 spans per trace buffer, or on `flush`/`close`; short-lived processes must flush (products/core).
- Runtime cost: instrumentation overhead rises with sampling and span count; Python docs advise testing high-throughput services before enabling.
- Tracing needs no pay-as-you-go budget to start, but overage on spans does (pricing page).

## Verify (R6)
1. Local run with the rate temporarily 1.0 (JS tracing page: use 1.0 while testing), hit one route, then:
   `sentry trace list <org>/<project> -t 1h --json` (expect at least one trace with the marker route) and `sentry explore <org>/<project> -d spans -F "count()" -t 1h`.
2. Distributed: open the trace with `sentry trace view <org>/<project>/<trace-id>`; spans from both frontend and backend project share one trace id. In the browser Network tab the API request carries `sentry-trace` and `baggage`; a CORS error there means the header allow-list is wrong.
3. JS v11 stream mode: span envelopes use content type `application/vnd.sentry.items.span.v2+json` in DevTools (streamed-spans page); `debug: true` prints warnings for callbacks that do not match the lifecycle.
4. Restore the production rate after the check.

## Sources
- references/upstream/concepts/tracing , references/upstream/concepts/reduce-volume
- https://docs.sentry.io/platforms/javascript/configuration/options/
- https://docs.sentry.io/platforms/javascript/tracing/
- https://docs.sentry.io/platforms/javascript/tracing/configure-sampling/
- https://docs.sentry.io/platforms/javascript/tracing/streamed-spans/
- https://docs.sentry.io/platforms/javascript/tracing/distributed-tracing/dealing-with-cors-issues/
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
- https://docs.sentry.io/platforms/javascript/configuration/filtering/
- https://docs.sentry.io/platforms/python/configuration/options/
- https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
- https://docs.sentry.io/platforms/go/configuration/options/
- https://docs.sentry.io/platforms/java/configuration/options/
- https://docs.sentry.io/pricing/
- https://cli.sentry.dev/commands/trace/ , https://cli.sentry.dev/commands/explore/

## Identifiers
```identifiers
tracesSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
tracesSampler | https://docs.sentry.io/platforms/javascript/configuration/options/
tracePropagationTargets | https://docs.sentry.io/platforms/javascript/configuration/options/
propagateTraceparent | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendSpan | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendTransaction | https://docs.sentry.io/platforms/javascript/configuration/options/
ignoreSpans | https://docs.sentry.io/platforms/javascript/configuration/options/
ignoreTransactions | https://docs.sentry.io/platforms/javascript/configuration/options/
traceLifecycle | https://docs.sentry.io/platforms/javascript/configuration/options/
inheritOrSampleWith | https://docs.sentry.io/platforms/javascript/configuration/options/
is_segment | https://docs.sentry.io/platforms/javascript/configuration/options/
updateSpanName | https://docs.sentry.io/platforms/javascript/tracing/instrumentation/
startSpan | https://docs.sentry.io/platforms/javascript/tracing/instrumentation/
startSpanManual | https://docs.sentry.io/platforms/javascript/tracing/instrumentation/
startInactiveSpan | https://docs.sentry.io/platforms/javascript/tracing/instrumentation/
start_span | https://docs.sentry.io/platforms/python/tracing/streamed-spans/
setAttribute | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
traces_sample_rate | https://docs.sentry.io/platforms/python/configuration/options/
traces_sampler | https://docs.sentry.io/platforms/python/configuration/options/
trace_lifecycle | https://docs.sentry.io/platforms/python/configuration/options/
ignore_spans | https://docs.sentry.io/platforms/python/configuration/options/
trace_propagation_targets | https://docs.sentry.io/platforms/python/configuration/options/
before_send_span | https://docs.sentry.io/platforms/python/configuration/options/
before_send_transaction | https://docs.sentry.io/platforms/python/configuration/options/
EnableTracing | https://docs.sentry.io/platforms/go/configuration/options/
TracesSampleRate | https://docs.sentry.io/platforms/go/configuration/options/
TracesSampler | https://docs.sentry.io/platforms/go/configuration/options/
TracePropagationTargets | https://docs.sentry.io/platforms/go/configuration/options/
PropagateTraceparent | https://docs.sentry.io/platforms/go/configuration/options/
TraceIgnoreStatusCodes | https://docs.sentry.io/platforms/go/configuration/options/
enableCacheTracing | https://docs.sentry.io/platforms/java/configuration/options/
enableQueueTracing | https://docs.sentry.io/platforms/java/configuration/options/
cachePrefixes | https://docs.sentry.io/platforms/javascript/guides/node/tracing/instrumentation/caches-module/
```

## Unconfirmed
- Go `EnableTracing`: the options page lists default `false` and says either sample option enables tracing, while the Go tracing page sets `EnableTracing: true`; follow the tracing page for the installed version and verify.
- Python 3.0 alpha `traces_sampler` context keys: docs say some keys may be unpopulated in stream mode; the list is on the streamed-spans migration guide, which was not fetched.
- Cocoa 9 and Android sampler/propagation defaults beyond the options page text were not checked on their tracing pages.
