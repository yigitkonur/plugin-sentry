# Node.js servers: Express, Fastify, Koa (module: platforms/node)

`@sentry/node` 11.8.0 (v10 still patched). Node.js >= 20.19.0 for v11 (22 needs >= 22.12, 23 needs >= 23.2). Shared JS rules and the
stale-API table: `platforms/js`. NestJS, Hono, Bun and Deno get their own modules; the shared Node rules below apply to them.

## Detect
| look at | meaning |
|---|---|
| `@sentry/node` + `express` / `fastify` / `koa` / `@hapi/hapi` in deps | server unit; installed major from the lockfile |
| `instrument.(js\|mjs\|ts)` at the project root | the init file; read it first |
| start command: `package.json` scripts, `Dockerfile` CMD, Procfile, PM2/systemd | must contain `node --import ./instrument.(js\|mjs)`; `--require` fails the check on v11 |
| `Sentry.init` inline in the server entry, after other imports | too late: libraries imported earlier may not be instrumented |
| `setupExpressErrorHandler`, `setupFastifyErrorHandler`, `setupKoaErrorHandler`, `setupHapiErrorHandler` calls | v11: deprecated, remove (duplicates risk); v10: required |
| custom `onUncaughtException`-style handlers next to the SDK | check `core.double-handlers` |
| `@sentry/tracing`, `raven`, a 7.x `@sentry/node` | pre-v8 setup: migrate stepwise with `.../guides/express/migration/v7-to-v8`, then v8-to-v9, v9-to-v10, v10-to-v11 |
| Fastify < 3.21 | v11 unsupported (3.0 through 3.20 dropped) |

## Install route
No wizard route for plain Node: manual from `sentry-ctx docs page platforms/javascript/guides/express` (or `.../fastify`, `.../koa`, `.../node`).
`npx @sentry/wizard@latest -i sourcemaps` only handles source maps, interactively. Install variants: `.../guides/node/install` (bundler plugin with a
top-level import; late initialization; deferred entrypoint; single executable apps). Other runtimes: `.../guides/nestjs`, `.../guides/hono`,
`.../guides/bun` (`--preload`), `.../guides/deno` (needs `--allow-env`).

## Init placement
Create `instrument.(js|mjs)` in the project root with `Sentry.init`, and start the app with `node --import ./instrument.js app.js` (works for ESM and
CommonJS). It must run before any module the SDK should wrap loads. v11 specifics:
- `--require` preloading is unsupported: the SDK skips init on its loader thread and warns. Use `--import`.
- The `init`, `preload` and `loader` entry points and `preloadOpenTelemetry()` are removed; `node --import @sentry/node/import main.mjs` then
  `Sentry.init()` later is the late-initialization route.
- `registerEsmLoaderHooks` is gone; instrumentation runs through diagnostics channels, with runtime hooks controlled by `enableRuntimeChannelInjection`
  (since 11.0.0, default true; `false` only when everything is instrumented at build time).
- Bundled servers: bundler plugin plus a top-level `import "./instrument.mjs"`; without a bundler a top-level import is not equivalent to `--import`
  because ESM evaluates all imports first.
- Next.js, SvelteKit: separate modules; do not apply this file.

## Options by SDK major
| option / API | v10 | v11 | note |
|---|---|---|---|
| `setupExpressErrorHandler(app)` etc. | required | deprecated, removal planned for v12 | errors are captured by the integrations |
| `shouldHandleError` | option of the `setup*ErrorHandler` call | option of `expressIntegration()` / `fastifyIntegration()` | Express default: 5xx and no-status errors, not 3xx/4xx; `false` = capture yourself |
| `trackIncomingRequestsAsSessions` | works | `sessions` | `httpIntegration`; see stale-API table |
| `maxIncomingRequestBodySize` | works | `maxRequestBodySize` | values `'none'`, `'small'`, `'medium'` (default, 10,000 bytes), `'always'` |
| `ignoreIncomingRequestBody`, `incomingRequestSpanHook` | works | `ignoreRequestBody`, `onSpanCreated` | |
| `instrumentation.requestHook` / `responseHook` / `applyCustomAttributesOnSpan` | works | removed | incoming spans: `onSpanCreated`; outgoing: `outgoingRequestHook` |
| `dropSpansForIncomingRequestStatusCodes` | works | `ignoreStatusCodes`, deprecated, only with `traceLifecycle: 'static'` | in stream mode use `ignoreIncomingRequests`, `tracesSampler` or `ignoreSpans` |
| `skipOpenTelemetrySetup` | works | `enableOpenTelemetrySetup` (default false) | SDK no longer registers a tracer provider; spans from `@opentelemetry/api` are ignored unless true |
| `otlpIntegration()` (node-core) | `@sentry/node-core/light/otlp` | `openTelemetryIntegration()` in `@sentry/node` | no exporter; `getOtlpTracesEndpoint()` builds the Sentry OTLP URL |
| `captureWorkerErrors` | on `childProcessIntegration` | removed | `workerThreadsIntegration()` is a separate default integration |
| `honoIntegration` | works | the guide says removed; 11.8.0 still exports it | use the `@sentry/hono` SDK (Hono guide) |
| `sendDefaultPii`, `enableLogs`, `beforeSendTransaction`, `profilesSampleRate` | | see stale-API table | |
Own OpenTelemetry pipeline on v11: leave `enableOpenTelemetrySetup` off, leave `tracesSampleRate` unset, add `openTelemetryIntegration()`; `SentryContextManager`,
`SentrySampler` and `SentrySpanProcessor` no longer exist, and `OTEL_SERVICE_NAME`/`OTEL_RESOURCE_ATTRIBUTES` are no longer read.

## Product support matrix
| product | supported | notes |
|---|---|---|
| errors | yes | v11 Express/Fastify/Koa/Hapi automatic; Fastify default captures 5xx and 2xx-and-below (not 3xx/4xx); Koa registers its own handler |
| tracing | yes | `tracesSampleRate` in `instrument`; HTTP, DB and framework spans are automatic; stream mode default |
| profiling | yes | `@sentry/profiling-node`, `nodeProfilingIntegration()`, `profileSessionSampleRate`; `profileLifecycle` default `"manual"` (start/stop calls), `"trace"` needs tracing and caps at 5 min per root span |
| logs, metrics | yes | `Sentry.logger.*`, `consoleLoggingIntegration()`, `Sentry.metrics.*`; no enabling option on v11 |
| crons | yes | `Sentry.withMonitor`, `Sentry.captureCheckIn` |
| replay, feedback | no | browser only |
| AI integrations | yes (server) | v11 traces model invocations, tool calls and agent invocations only |

## Release and artifacts
Server release: `release` option or `SENTRY_RELEASE` env on the running process (the SDK reads it); `environment` from `SENTRY_ENVIRONMENT` or the option.
Source maps are needed only when the process runs transpiled or bundled code (`dist/`): upload the maps of the output that runs, via the bundler plugin or
`sentry sourcemap inject` + `upload` (see `platforms/js`). Release name must match what CI created.

## Privacy
v11 defaults collect request headers, cookies, bodies, URL query params and user IP, and database query data (`databaseQueryData`). Set `dataCollection`
explicitly. `httpIntegration`'s `maxRequestBodySize` (default `'medium'`) limits body size; `includeLocalVariables` defaults false.

## Verify recipe
Temporary route (`GET /debug-<random>`) that throws an Error carrying the marker, hit once against the real server started with the real `--import` flag; for
a script or cron run, call `await Sentry.flush(2000)` before the marker run ends. Remove the route afterwards. Do not verify from a separate script: it
bypasses the init under test.

## Gotchas
| trap | fix | source |
|---|---|---|
| `--require ./instrument.js` | `--import`; v11 skips init and warns | Node migration page |
| process exits before events leave (CLI, cron, serverless) | `await Sentry.flush(timeout)`, or `Sentry.close(timeout)` right before exit; `shutdownTimeout` defaults to 2000 ms | Node APIs and options pages |
| custom `onUncaughtException` handler plus SDK | since v8 the SDK no longer exits when other handlers exist (`exitEvenIfOtherHandlersAreRegistered`); decide who exits | v7-to-v8 Node page |
| error handler call kept on v11 plus own `captureException` in middleware | duplicates: remove the call, or `shouldHandleError: false` | Express page |
| 4xx never appear | default skips 3xx/4xx; widen with `shouldHandleError` | Express, Fastify pages |
| Fastify error callback signature | `shouldHandleError(error, request, reply)` | Fastify error-handler page |
| `ignoreStatusCodes` expected to drop spans in stream mode | it does nothing there | HTTP integration page |
| Node 18 in Dockerfile (`FROM node:18`) | raise to a supported range | Node migration page |

## Sources
- https://docs.sentry.io/platforms/javascript/guides/node.md
- https://docs.sentry.io/platforms/javascript/guides/node/install.md
- https://docs.sentry.io/platforms/javascript/guides/express.md
- https://docs.sentry.io/platforms/javascript/guides/fastify.md
- https://docs.sentry.io/platforms/javascript/guides/fastify/features/error-handler.md
- https://docs.sentry.io/platforms/javascript/guides/koa.md
- https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11.md
- https://docs.sentry.io/platforms/javascript/guides/node/migration/v7-to-v8.md
- https://docs.sentry.io/platforms/javascript/guides/node/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/node/configuration/apis.md
- https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/http.md

## Identifiers
```identifiers
shouldHandleError | https://docs.sentry.io/platforms/javascript/guides/express/
setupKoaErrorHandler | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
setupHapiErrorHandler | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
sessions | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/http/
maxRequestBodySize | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/http/
ignoreRequestBody | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/http/
onSpanCreated | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/http/
outgoingRequestHook | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
ignoreStatusCodes | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/http/
ignoreIncomingRequests | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/http/
ignoreIncomingRequestBody | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
incomingRequestSpanHook | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
applyCustomAttributesOnSpan | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
enableOpenTelemetrySetup | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
skipOpenTelemetrySetup | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
enableRuntimeChannelInjection | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
captureWorkerErrors | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
SentryContextManager | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
SentrySampler | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
SentrySpanProcessor | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
databaseQueryData | https://docs.sentry.io/platforms/javascript/configuration/options/
dataCollection | https://docs.sentry.io/platforms/javascript/configuration/options/
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
profileLifecycle | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
includeLocalVariables | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
shutdownTimeout | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
exitEvenIfOtherHandlersAreRegistered | https://docs.sentry.io/platforms/javascript/guides/node/migration/v7-to-v8/
onUncaughtException | https://docs.sentry.io/platforms/javascript/guides/node/migration/v7-to-v8/
httpIntegration | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/http/
responseHook | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
childProcessIntegration | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
captureException | https://docs.sentry.io/platforms/javascript/guides/node/configuration/apis/
stackFrameVariables | https://docs.sentry.io/platforms/javascript/configuration/options/
traceLifecycle | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
tracesSampler | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
ignoreSpans | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
```

## Unconfirmed
- `includeLocalVariables`: default false on the Node options page, while the `dataCollection` category `stackFrameVariables` defaults true; the pages do not say how they combine. Set both when local variables matter.
- Source maps for Node servers: no Node-specific official source map page was fetched; the generic bundler/CLI route from `platforms/js` is assumed.
