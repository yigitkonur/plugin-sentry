# OpenTelemetry and OTLP (product id: otlp)

## Fit
Propose only when the repo has an OpenTelemetry signal. `data/signals.tsv` row `otlp` applies on `sig:otel`; without it the row reads "no OpenTelemetry detected" and nothing is proposed.

| Repo evidence | Where to look | What it means |
|---|---|---|
| OTel packages | `package.json` (`@opentelemetry/*`), `pyproject.toml` or `requirements*.txt` (`opentelemetry-*`), `go.mod` (`go.opentelemetry.io/otel`), `pom.xml` or `build.gradle*` (`io.opentelemetry`) | Service already instruments with OTel |
| Own tracer provider with an OTLP exporter | Entry file: Node `NodeTracerProvider` or NodeSDK with `OTLPTraceExporter`; Go global tracer-provider setter; Python and Java OTel setup | Span-ownership question (see Properly configured) |
| Sentry init in the same process | The file that calls the Sentry init | Highest-risk case: duplicate capture |
| Collector or forwarder config | `otel-collector*.yaml`, Vector or Fluent Bit config | Forwarding direction (`concepts/otlp/forwarding`) |
| Managed-platform drain | `vercel.json`, `wrangler.toml` or `wrangler.jsonc`, `Procfile`. The drain itself is configured in the platform, not the repo | Log and trace drains; confirm only with platform access |

Worth proposing when:
- The repo has OTel and a Sentry SDK, or the team wants Sentry as the trace backend. The span owner must be chosen.
- OTel traces exist but errors and logs do not link to them in Sentry. The error-only pattern (Node `openTelemetryIntegration`) or the OTLP Integration fixes that.
- Infrastructure or a managed platform already ships logs or traces. Forwarding or drains are the route, and an SDK is still needed for errors.

NOT worth proposing:
- No OTel signal in the repo.
- Browser or mobile only. The OTLP Integration list (`concepts/otlp/sentry-with-otel`) names Python, Node.js, Java, .NET, Go, Ruby, PHP, Laravel and Symfony, with no browser or mobile entry. Browser and mobile use `propagateTraceparent` instead, which links traces and adds no exporter.
- The OTel exporter sends spans to another backend and the team has not asked for Sentry spans. At most the error-only pattern applies.
- Drain settings cannot be seen (they live in the platform UI). Mark UNVERIFIED, not n/a.

## Properly configured
Rule: each service has exactly one span owner, either Sentry tracing or the OTel provider. The other is explicitly off.

| SDK family | Right | Source |
|---|---|---|
| Node, OTel owns spans | One tracer provider. Its span processor is `BatchSpanProcessor` wrapping `OTLPTraceExporter(getOtlpTracesEndpoint(dsn))`, added through `spanProcessors`. Init sets `enableOpenTelemetrySetup: false`, puts `openTelemetryIntegration` in `integrations`, and leaves `tracesSampleRate` and `tracesSampler` unset. OTel is initialised before the Sentry init. | Node integration page; Node custom-setup |
| Node, errors only | Keep the existing exporter and omit the Sentry exporter. Sentry init is unchanged. `openTelemetryIntegration` links errors to the active trace without sending spans. | Node custom-setup, "Use Sentry for Error Monitoring Only" |
| Node sampling | `tracesSampleRate` and `tracesSampler` do not control OTLP spans. The sampler goes on the OTel provider. | Node custom-setup, "Configure Sampling" |
| Python | `OTLPIntegration` sets the exporter from the DSN, adds a Sentry propagator, and links errors, logs and metrics to the trace. Do not set `traces_sample_rate` or `traces_sampler`. The page states no SDK major. | Python OTLP, Behavior |
| Java | The Sentry propagator inherits the sampling flag from the incoming `sentry-trace` header. With no flag it samples. Deferred sampling needs a custom OpenTelemetry Sampler. Install and Dependency Alignment sections were not fetched. | Java OTLP, Sampling |
| Go, .NET, Ruby, PHP | Per-platform OTLP pages linked from the OTLP Integration list. Not fetched for this module; read them before proposing. | `concepts/otlp/sentry-with-otel` |
| Frontend SDK in front of an OTel backend | `propagateTraceparent` in the frontend init. If a collector runs tail-based sampling, set `OTEL_TRACES_SAMPLER` to `always_on` on the backend: the default `parentbased_always_on` honours the frontend decision and skips the tail sampler. | `concepts/otlp/sentry-with-otel` |
| Log and trace drains | No SDK config. Errors still need the SDK; drains carry logs and traces only. | `product/drains` |

Environment, release and PII for OTLP-delivered data are not covered by the pages fetched. Take them from the platform module, and mark OTLP-side values UNVERIFIED.

## Checks
`sentry-ctx checks --product otlp` lists no rows for this product, so every row uses an x.<slug> id.

| check id | read | passes when |
|---|---|---|
| x.otlp-span-owner | Dependency manifests (`package.json`, `pyproject.toml`, `requirements*.txt`, `go.mod`, `pom.xml`, `build.gradle*`) for the Sentry SDK and OTel packages; the init files that call the Sentry init and register an OTel provider | Per service exactly one span owner: Sentry tracing set, or an OTel provider with an OTLP exporter. Never both. |
| x.otlp-single-provider | Grep the repo for tracer-provider registration calls and for `enableOpenTelemetrySetup`, `openTelemetryIntegration`, `OTLPIntegration` | One provider per process. Node sets `enableOpenTelemetrySetup: false` when the app owns its provider. The provider is initialised before the Sentry init. |
| x.otlp-sampling | Init files and env files (`.env*`, deployment manifests) for `tracesSampleRate`, `tracesSampler`, `traces_sample_rate`, `traces_sampler`, `OTEL_TRACES_SAMPLER` | Where OTLP export is on, the Sentry trace settings are unset (Node, Python). The OTel sampler is set on purpose. `always_on` appears only where a collector does tail sampling behind a `propagateTraceparent` frontend. |
| x.otlp-error-only | Grep `getOtlpTracesEndpoint` and `OTLPTraceExporter` per service | A service that keeps its own trace pipeline does not also export spans to Sentry, and (Node) uses `openTelemetryIntegration` so its errors still link. |
| x.otlp-endpoint-source | Grep for hand-written OTLP URLs or auth headers; read the DSN in config | Endpoint and auth come from the DSN: `getOtlpTracesEndpoint` (Node) or `OTLPIntegration` (Python). A hand-built URL, or a DSN from another project, fails. |
| x.otlp-frontend-propagation | Frontend init files for `propagateTraceparent` | Set in the frontend SDK init when requests reach an OTel-instrumented backend. |
| x.otlp-drain-scope | Platform files in the repo (`vercel.json`, `wrangler.toml` or `wrangler.jsonc`, `Procfile`). Drain settings are UI-only: ask the user, else UNVERIFIED | Every app with a drain also has an SDK for errors. No one expects metrics through a drain (not supported). |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Traces duplicated or split into two roots | Sentry tracing on (`tracesSampleRate`, `traces_sample_rate` or a sampler) and an OTel exporter both active | Unset the Sentry trace settings where OTLP export is on; one span owner per service | Node integration page; Python OTLP, Behavior |
| Sentry sample rate has no effect on OTel spans | `tracesSampleRate` and `tracesSampler` do not control OTLP spans | Sampler on the OTel provider | Node custom-setup, "Configure Sampling" |
| Errors not linked to the OTel trace | Sentry init runs before OTel is initialised | Initialise OTel first, then Sentry init. Where a framework has its own entry point, do both there in that order | Node integration page |
| Spans split or missing after a second provider is added | Two providers registered in one process | One provider; add the exporter to the existing one through `spanProcessors` | Node custom-setup |
| Frontend and backend traces do not join | `propagateTraceparent` off in the frontend, or a `parentbased_*` backend sampler drops what the collector would keep | Enable `propagateTraceparent`; `always_on` on the backend when a tail sampler is in use | `concepts/otlp/sentry-with-otel` |
| No spans after a JS v11 upgrade in a repo that relied on the SDK's OTel setup | v11: "The SDK no longer takes over your OpenTelemetry setup" | Explicit provider and exporter, `enableOpenTelemetrySetup: false`, `openTelemetryIntegration` | JS v10-to-v11 migration page |
| App behind a drain shows logs and traces but no errors | Drains carry logs and traces only | Add the SDK for errors | `product/drains`, Limitations |
| Metrics expected through a drain | Drains do not support metrics | Send metrics through an SDK | `product/drains`, Limitations |
| Java sampling differs from the upstream service | Sentry propagator inherits the `sentry-trace` flag; with no flag it samples | Custom OpenTelemetry Sampler for deferred sampling | Java OTLP, Sampling |

## Volume, cost and overhead
- Billing category for OTLP-delivered spans and logs: not stated on the pages fetched. Confirm after a test export, using the outcome totals by category from the `quota` module's Verify section.
- Logs beyond the included GB need pay-as-you-go (`quota` module, Volume table). Drains carry no metrics, so metrics volume comes only from SDKs.
- Runtime: the OTel side batches through `BatchSpanProcessor` (Node example). No overhead figure is on the pages fetched.
- Sampling on the OTel provider decides which spans are exported at all. Sentry-side sample rates do not.

## Verify (R6)
1. Span ownership: send one request through an OTel-instrumented route in staging. It appears once in Sentry Traces, with OTel spans and no separate Sentry-SDK root span for the same request. UI-only: UNVERIFIED unless the user confirms.
2. Error linking: throw a marked error in that route, then remove it. The issue's trace matches the trace id in the OTel exporter output.
3. Sampler: set the OTel sampler to `always_on`, send 5 marked requests, and expect 5 marked traces. Then restore the sampler.
4. Outcome: the org outcome totals by category (`quota` module, Verify step 1) show accepted spans rising by the test count and no rate-limited spans.
5. Drains: one log line sent through the platform appears in Sentry Logs, and no error arrives through the drain. UI-only.
6. Remove the marked route, error and sampler change after the checks.

## Sources
- https://docs.sentry.io/concepts/otlp/
- https://docs.sentry.io/concepts/otlp/sentry-with-otel/
- https://docs.sentry.io/concepts/otlp/forwarding/
- https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
- https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/opentelemetry/
- https://docs.sentry.io/platforms/python/integrations/otlp/
- https://docs.sentry.io/platforms/java/opentelemetry/setup/otlp/
- https://docs.sentry.io/product/drains/
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/

## Identifiers
```identifiers
enableOpenTelemetrySetup | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/opentelemetry/
getOtlpTracesEndpoint | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/opentelemetry/
openTelemetryIntegration | https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
spanProcessors | https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
tracesSampler | https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
OTLPTraceExporter | https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
BatchSpanProcessor | https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
NodeTracerProvider | https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
@opentelemetry/exporter-trace-otlp-http | https://docs.sentry.io/platforms/javascript/guides/node/opentelemetry/custom-setup/
propagateTraceparent | https://docs.sentry.io/concepts/otlp/sentry-with-otel/
OTEL_TRACES_SAMPLER | https://docs.sentry.io/concepts/otlp/sentry-with-otel/
always_on | https://docs.sentry.io/concepts/otlp/sentry-with-otel/
parentbased_always_on | https://docs.sentry.io/concepts/otlp/sentry-with-otel/
OTLPIntegration | https://docs.sentry.io/platforms/python/integrations/otlp/
traces_sample_rate | https://docs.sentry.io/platforms/python/integrations/otlp/
traces_sampler | https://docs.sentry.io/platforms/python/integrations/otlp/
sentry-trace | https://docs.sentry.io/platforms/java/opentelemetry/setup/otlp/
```

## Unconfirmed
- `otlpIntegration`: `data/stale-apis/js.tsv` says it was renamed to `openTelemetryIntegration` in JS v11, citing the Node v10-to-v11 path. That path returned no text containing the name, and the Browser v10-to-v11 page does not name it either. Verify before proposing any rename.
- `o<id>.ingest.de.sentry.io`: EU ingest host from the research notes (product map, deployment section); not on a fetched page. Verify against the data-storage-location page before use.
