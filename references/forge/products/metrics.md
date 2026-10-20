# Metrics (product id: metrics)

## Fit
Application Metrics are numeric health values and business KPIs, emitted from code as `count`, `gauge` or `distribution`, and linked to traces. The `metrics` row in data/signals.tsv applies when a metrics client is detected (signal sig:metrics) or the user opts in (policy:metrics); otherwise it is N/A with "no metrics client detected". Propose it only when the repo shows a number the team reads that Errors and Traces do not already show.

Worth proposing when the repo shows:

| Repo evidence | Where to look | Why it fits |
|---|---|---|
| Success/failure counters: orders, signups, checkout or payment failures, retries that give up | handlers, services, job runners | "Good candidates": business KPIs tied to code execution, success/failure rates (product page, When to Use) |
| Saturation gauges: queue depth, pool size, open connections, cache size | worker, client and pool setup files | "Resource utilization tracking" (product page); "Resource usage" under When to Instrument (getting-started) |
| Hand-rolled counters or timers feeding a StatsD or Prometheus client, or log lines that only count events | grep for statsd, prom-client, prometheus and counting log calls | Logs are for aggregation and Metrics for numeric health (product page). The old beta API is gone, so port by rewrite (v8-to-v9 page) |
| Sizes or durations measured by hand | payload-size checks, timing wrappers | Distributions give percentiles (Python page, Choosing a metric type) |

Not worth proposing when:
- The only questions are error rates or request latency. The product page sends those to Traces (request tracing) and Logs (aggregation).
- The only dimensions available are user IDs, request IDs or free text, with no bounded field to group by (see Properly configured).
- There is no pay-as-you-go budget and the emit sits on a per-request path with no filter. The policy question's "Low traffic, no budget" answer is to skip metrics unless free quota covers them (data/policy_questions.json).
- The pinned SDK is below the platform minimum and no upgrade is planned, or the platform is not in the Supported SDKs list on the getting-started page.
- The repo has old beta calls and no plan to rewrite them. Do not "fix" them by adding the product.

## Properly configured
Minimum SDK versions are in each platform page's Requirements section. Python 2.44.0 is verified there; other minimums are in Unconfirmed.

| SDK family | Enabling | Emit | Filter and flush |
|---|---|---|---|
| JavaScript v11 (browser, Node, frameworks) | No flag. Metrics are sent only when `Sentry.metrics.count` (or `gauge`, `distribution`) is called | `Sentry.metrics.count("orders_created", 1)`; `Sentry.metrics.distribution("api_latency", 187, { unit: "millisecond" })` | `beforeSendMetric` returning null drops a metric; `await Sentry.flush()` before exit |
| JavaScript below v11 | `enableMetrics: false` in `Sentry.init` disables metrics (the page says this applies below 11.0.0) | same | same |
| Python 2.44+ | Enabled by default | `sentry_sdk.metrics.count(name, value, attributes=...)`; `gauge(..., unit="byte")` | `before_send_metric` returning None drops a metric |
| Apple (Cocoa) | Enabled by default but not collected automatically; call `SentrySDK.metrics`. `options.enableMetrics = false` disables | `SentrySDK.metrics.count` with keyword arguments key, value, unit, attributes | `beforeSendMetric` callback (Filtering and Modifying Metrics) |
| Java | Available after SDK init through `Sentry.metrics()` | `Sentry.metrics().count("button_click", 1.0)` | `getMetrics().setBeforeSend`; returning null drops |

Rules for every SDK:
- Names: dot-separated, purpose first, e.g. `checkout.failed`, `queue.depth`. Not `metric1`, `counter` or `x` (getting-started, Naming Conventions).
- Type by question: `count` answers how many; `gauge` is the current level and has no percentiles; `distribution` is a set of observations with percentiles (Python and Apple pages).
- Units on `gauge` and `distribution`: millisecond, second, byte, kilobyte, megabyte (JS page, Units).
- Attributes stay bounded: environment, region, plan tier, endpoint template. No user IDs, request IDs or free text (quota page, Best Practices). `Sentry.setAttributes` (JS 10.61.0+) applies to metrics and logs alike, so per-user values do not belong there (JS page, Shared Attributes).
- Each metric is limited to 2 KB; a larger metric is dropped (JS page, Filtering and Grouping).
- Sensitive attributes can be removed in the callback: `beforeSendMetric` (JS), `before_send_metric` (Python), the Cocoa and Java callbacks (Apple and Java pages).
- Sampling: the metric carries an optional client sample rate field. The fetched pages show no sampling option for metrics; do not invent one.
- Releases and environments: filter by release in Inbound Filters (quota page); environment is a bounded attribute.

## Checks
| check id | read | passes when |
|---|---|---|
| metric.migration | grep -rnE "metrics\.(increment\|set\|timing)\(" over the source tree, skipping dependency folders (node_modules, vendor, Pods, .build). Then the SDK pin: the @sentry packages in package.json, sentry-sdk in requirements or pyproject.toml, sentry-cocoa in Package.swift or Podfile.lock, sentry-java in build.gradle or pom.xml | No old beta call sites in files that import a Sentry SDK. New calls use `count`, `gauge` or `distribution` on `Sentry.metrics`, `sentry_sdk.metrics`, `SentrySDK.metrics` or `Sentry.metrics()`. The pinned SDK is at or above the minimum in the platform page's Requirements section (the old API is removed from the JS SDK in v9) |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Old beta calls (increment, set, timing) fail or send nothing after an upgrade | The previous metrics API was removed from the JS SDK in v9 | Rewrite to `count`, `gauge` or `distribution` | JS v8-to-v9 page |
| No metric in Sentry and no error in the app | SDK below the platform minimum, or a `beforeSendMetric` / `before_send_metric` hook returns null for every metric | Check the pinned version against Requirements; read the hook | JS page; Python page |
| Metrics from a short-lived JS script are lost | Metrics are buffered and sent periodically | `await Sentry.flush()` before the process exits | JS page |
| Metric volume grows and one name dominates | User IDs, request IDs or free text in attributes | Bounded attributes; drop in the hook; metric-name inbound filter | quota page, Best Practices |
| A metric disappears with no error | More than 2 KB per metric; the SDK drops it | Shorten attributes; split the metric | JS page |
| No percentile on a gauge | Gauges cannot produce percentiles | Use `distribution` | Python page; Apple page |
| Chart values have no unit | Unit not set on a gauge or distribution | Set `unit` (millisecond, byte, ...) | JS page |
| JS v11 code sets `enableMetrics: false` and metrics still flow | The flag applies only below 11.0.0; v11 has no flag | Return null from `beforeSendMetric` to stop sending | JS page |
| Source conflict: user IDs on metrics | JS page example attaches `user_id` and `order_id`; quota page warns against user IDs for volume | Follow the quota page for cost; keep per-user values in traces or logs | JS page vs quota page |
| Source conflict: high cardinality | Vendored upstream concept calls high cardinality a benefit; billing guidance says it inflates volume | Use bounded attributes for cost; the billing guidance wins for this audit | vendored upstream/concepts/metrics vs quota page |

## Volume, cost and overhead
- Category: billed to the Application Metrics quota. The unit is GB according to the quota product module and research notes; the pricing page was not fetched in this pass, so do not quote figures (see Unconfirmed).
- Included quota, then PAYG: when the quota is used up, new metric events are not sent until the budget is raised. Only Billing- or Owner-level members can set it, and Owners get notification emails as the quota approaches its limit (quota page, Adjusting PAYG Budget).
- Biggest lever: SDK hooks (`beforeSendMetric`, `before_send_metric`) drop metrics before they leave the app. The quota page calls this the most effective way to cut usage. Inbound filters by metric name (glob) and by release stop filtered metrics from counting against quota (quota page, Application Metrics Filtering).
- Size: each metric is capped at 2 KB and attributes drive its bytes. Because billing is per GB, bounded attributes are the main cost control.
- Usage: check Usage Stats and set quota notifications (quota page, Monitoring Your Application Metrics Usage).
- Runtime overhead: the fetched pages give no figure. Do not quote one.

## Verify (R6)
1. Emit one probe with a unique name (for example `verify.probe`) and a unit, from the code path the feature uses, inside an active span. In JS, call `await Sentry.flush()` afterwards, because metrics are buffered and sent periodically (JS page).
2. Open the Application Metrics explorer (product page, "Viewing and Exploring Application Metrics") and search the probe name. Expect the kind, unit and value, and a sample linked to the trace through the trace and span fields listed in Metric Attributes.
3. Open Usage Stats (linked from the quota page). The accepted count for metrics rises by the number of probe emits, and no rate-limited rows appear. The category-breakdown API probe in the quota module is an observed endpoint, not a documented one.
4. If a `beforeSendMetric` or `before_send_metric` hook exists, emit a second probe name that the hook drops. It must not appear in the explorer, because the drop happens in the SDK.
5. Remove the probe calls and confirm the name stops receiving new samples.

## Sources
- https://docs.sentry.io/product/metrics.md
- https://docs.sentry.io/product/metrics/getting-started.md
- https://docs.sentry.io/platforms/javascript/metrics.md
- https://docs.sentry.io/platforms/python/metrics.md
- https://docs.sentry.io/platforms/apple/metrics.md
- https://docs.sentry.io/platforms/java/metrics.md
- https://docs.sentry.io/pricing/quotas/manage-application-metrics-quota.md
- https://docs.sentry.io/platforms/javascript/migration/v8-to-v9.md
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md

## Identifiers
```identifiers
Sentry.metrics.count | https://docs.sentry.io/platforms/javascript/metrics.md
Sentry.metrics.gauge | https://docs.sentry.io/platforms/javascript/metrics.md
Sentry.metrics.distribution | https://docs.sentry.io/platforms/javascript/metrics.md
Sentry.metrics() | https://docs.sentry.io/platforms/java/metrics.md
sentry_sdk.metrics | https://docs.sentry.io/platforms/python/metrics.md
SentrySDK.metrics | https://docs.sentry.io/platforms/apple/metrics.md
Sentry.init | https://docs.sentry.io/platforms/javascript/metrics.md
Sentry.flush | https://docs.sentry.io/platforms/javascript/metrics.md
Sentry.setAttributes | https://docs.sentry.io/platforms/javascript/metrics.md
enableMetrics | https://docs.sentry.io/platforms/javascript/metrics.md
options.enableMetrics | https://docs.sentry.io/platforms/apple/metrics.md
beforeSendMetric | https://docs.sentry.io/platforms/javascript/metrics.md
before_send_metric | https://docs.sentry.io/platforms/python/metrics.md
getMetrics().setBeforeSend | https://docs.sentry.io/platforms/java/metrics.md
user_id | https://docs.sentry.io/platforms/javascript/metrics.md
order_id | https://docs.sentry.io/platforms/javascript/metrics.md
```

## Unconfirmed
- `trace_metric` and `trace_metric_byte`: envelope category names from research notes; not on any fetched page.
- `nodeRuntimeMetricsIntegration`: opt-in auto-emitted metrics named in research notes; not on any fetched page.
- `_experiments.enableMetrics`: called a removed leftover in the quota module; the v10-to-v11 page does not mention it.
- Billing unit (GB) and included amounts: from the quota module and research notes; the pricing page was not fetched.
- Minimum SDK versions other than Python 2.44.0: JS 10.25, Java/Android 8.34, Cocoa 9.12, React Native 7.8, Flutter 9.11, .NET 6.1, Go 0.42, PHP 4.19, Ruby 6.3, Elixir 13.0, Unity 4.2, Native 0.12.6 (research matrix). Rust is 0.48 in the matrix but "Upcoming" on the setup list; conflict unresolved.
- Browser CDN bundles: research says only `*.logs.metrics` bundles include metrics; not checked on a fetched page.
- Metrics pages for Android, Go, Ruby, PHP, .NET, Elixir, Unity, Native and Rust: not fetched in this pass.
