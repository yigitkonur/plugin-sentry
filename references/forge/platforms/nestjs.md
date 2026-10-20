# NestJS (module: platforms/nestjs)

## Detect

| Signal | Where | Means |
|---|---|---|
| `@nestjs/core` | package.json | NestJS app (engine id `nestjs`, role backend); outranks plain Node |
| `@sentry/nestjs` | package.json, lockfile | SDK installed; the lockfile gives the major (v10 or v11) |
| `@sentry/node` and no `@sentry/nestjs` | package.json | the guide installs `@sentry/nestjs`; a Nest app on `@sentry/node` alone is a finding |
| `instrument.ts` | project root | the init file the guide prescribes |
| `SentryModule.forRoot()` | root module imports | Sentry module wiring |
| `SentryGlobalFilter`, `SentryExceptionCaptured` | `APP_FILTER` providers, filter `catch()` | error capture route |
| `@Cron`, `@Interval`, `@OnEvent`, BullMQ `@Processor()` | services, processors | background jobs: need `withIsolationScope` |
| `@WebSocketGateway`, `@nestjs/microservices` | gateways, RPC handlers | need their own filters (Gotchas) |

## Install route

- SDK: manual from the live page, `sentry-ctx docs page platforms/javascript/guides/nestjs --section Install`. Package `@sentry/nestjs`; `@sentry/profiling-node` only for profiling.
- Source maps, automatic: `npx @sentry/wizard@latest -i sourcemaps` (guide, Configure). Manual `tsc` route: `sentry-ctx docs page platforms/javascript/guides/nestjs/sourcemaps/uploading/typescript`.
- No other CLI init is documented for NestJS. Never paste install steps from memory.

## Init placement

| Requirement | Right | Finding |
|---|---|---|
| File | `instrument.ts` at project root calls `Sentry.init` | `Sentry.init` inside `AppModule` or a provider |
| Order | `import "./instrument";` is the first import of the entry file | any Nest or app import above it |
| Module | `SentryModule.forRoot()` in the root module's imports | missing from the root module |
| Filter | `SentryGlobalFilter` as an `APP_FILTER` provider, listed first | another filter listed before it |

The guide's comment in `instrument.ts`: "Ensure to call this before requiring any other modules!"

## Options by SDK major

v10 = 10.x; v11 = 11.x (current major, prefer it).

| option | v10 | v11 | note |
|---|---|---|---|
| `dataCollection` | defaults apply only when set (since 10.57.0) | defaults always apply | set every category from the privacy answers |
| `sendDefaultPii` | controls collection while `dataCollection` is unset | removed | use `dataCollection` |
| `tracesSampleRate` | 0 to 1; tracing needs it or `tracesSampler` | same | the guide's `1.0` is a demo value |
| `beforeSendTransaction`, `ignoreTransactions` | transaction hooks | replaced by `beforeSendSpan` (guard on `is_segment`) and `ignoreSpans` | migration page, Tracing |
| `beforeSendSpan` | span hook | changes spans, cannot drop them | drop spans with `ignoreSpans` |
| legacy per-transaction profiling options | present | removed | `profileSessionSampleRate` with `profileLifecycle` `'trace'` or `'manual'` |

## Product support matrix

| product | supported | notes |
|---|---|---|
| Errors | yes | catch-all filter or `@SentryExceptionCaptured()`; `HttpException` not captured by default |
| Tracing | yes | `tracesSampleRate` or `tracesSampler`; automatic instrumentation page |
| Profiling | yes | `@sentry/profiling-node`, `nodeProfilingIntegration()` in `integrations`, `profileSessionSampleRate` |
| Replay | no | browser-only product; no Node replay page in the platform matrix |
| Logs | yes | `Sentry.logger.info`, `.warn`, `.error` (guide, Verify) |
| Metrics | yes | enabled by default (guide, Verify) |
| Crons | yes | `@SentryCron` below `@Cron` (since v8.16.0); `Sentry.cron` for `cron`, `node-cron`, `node-schedule` |
| Feedback | unconfirmed | no NestJS page checked |
| AI monitoring | yes | Agent Tracing page: server-side auto-instrumentation tied to tracing |
| Flags | unconfirmed | no NestJS page checked |

## Release and artifacts

- `release`: env `SENTRY_RELEASE`, read by the server SDK when the option is unset (options page). The same string must reach the source map upload. The NestJS pages give no git fallback (Unconfirmed).
- `environment`: env `SENTRY_ENVIRONMENT`. The options table says default `production`; its text says `development` or `production` depending on packaging. Set it per deploy.
- Source maps, `tsc` route (typescript page):
  1. tsconfig: `sourceMap: true`, `inlineSources: true`, `sourceRoot: "/"`.
  2. `sentry-cli sourcemaps inject <dir>`: debug IDs. Check `//# debugId=` in the JS and `debug_id` in each `.map`.
  3. `sentry-cli sourcemaps upload <dir>`; verify under Project Settings > Source Maps > Artifact Bundles.
  4. Optional: associate `release` with the bundle (same page).
- Other bundlers are under `sourcemaps/uploading`. The NestJS pages cover JavaScript source maps only; no native symbol route is documented there.
- CI: the wizard configures the CI upload step (typescript page, Automatic Setup).

## Privacy

| Data | Default (v11) | Control (all under `dataCollection`) |
|---|---|---|
| user id, email, username, IP | sent | `userInfo` |
| cookies, HTTP headers | sent; sensitive values `[Filtered]` | `cookies`, `httpHeaders` |
| HTTP bodies, URL query parameters | sent | `httpBodies`, `urlQueryParams` |
| GraphQL document and variables; AI inputs and outputs | sent | `graphQL`, `genAI` |
| local variables; DB bound parameters and results | sent | `stackFrameVariables`, `databaseQueryData` |

The built-in denylist (`auth`, `token`, `secret`, `password`, ...) always scrubs matching values (options page, `dataCollection`).

## Verify recipe

Trigger through the real HTTP path, not a unit test. Add a temporary route to an existing controller (the guide's sample; needs `import * as Sentry from "@sentry/nestjs";`):

```typescript
@Get("/debug-sentry")
getError() {
  return Sentry.startSpan({ op: "test", name: "My First Test Span" }, () => {
    throw new Error("My first Sentry error!");
  });
}
```

1. Start the app and run `curl -i http://localhost:<port>/debug-sentry`, with the port passed to `app.listen()`. The response is the framework's error response.
2. Expect an issue "My first Sentry error!" under Issues, and a trace with the span "My First Test Span". The span needs `tracesSampleRate` above 0.
3. Remove: delete the route method and the Sentry import it added. `grep -rn "debug-sentry" <repo>/src` must return nothing.

## Gotchas

| Trap | Source |
|---|---|
| The guide sample sets `tracesSampleRate: 1.0` and `profileSessionSampleRate: 1.0` with an "adjust in production" comment. Flat `1.0` in production is a finding. | guide, Configure |
| `HttpException` and subclasses are not captured by default. A specific filter hides errors unless its `catch()` calls `Sentry.captureException()`. | guide, Capture Errors |
| `APP_FILTER` filters do not reach WebSocket gateways. Add `@UseFilters(new SentryGlobalFilter())` on each gateway class. | guide, Capture Errors |
| `SentryGlobalFilter` does not extend the Nest RPC base filter. Microservice handlers need their own `RpcExceptionFilter`; call `Sentry.captureException()` if the error should reach Sentry. | guide, Capture Errors |
| Background jobs share the isolation scope with HTTP requests, so breadcrumbs leak into request errors. Wrap handlers in `Sentry.withIsolationScope()`. The research note said cron needs filters; the page says isolation. The page wins. | async-context page |
| `@SentryCron` must sit below `@Cron`, or the instrumentation does not work. | crons page |
| Generated `.js.map` files can expose source. Deny `.js.map` at the server or delete them before deploy. | typescript page, step 1 |
| v11 removes `sendDefaultPii` and the transaction hooks; `beforeSendSpan` and `ignoreSpans` replace them. | migration page |

## Sources

- https://docs.sentry.io/platforms/javascript/guides/nestjs.md
- https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/nestjs/crons.md
- https://docs.sentry.io/platforms/javascript/guides/nestjs/features/async-context.md
- https://docs.sentry.io/platforms/javascript/guides/nestjs/tracing.md
- https://docs.sentry.io/platforms/javascript/guides/nestjs/agent-tracing.md
- https://docs.sentry.io/platforms/javascript/guides/nestjs/sourcemaps/uploading.md
- https://docs.sentry.io/platforms/javascript/guides/nestjs/sourcemaps/uploading/typescript.md
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md

## Identifiers

```identifiers
@sentry/nestjs | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
@sentry/profiling-node | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
SentryModule.forRoot | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
SentryGlobalFilter | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
APP_FILTER | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
SentryExceptionCaptured | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
Sentry.captureException | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
Sentry.startSpan | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
nodeProfilingIntegration | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
UseFilters | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
AppModule | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
HttpException | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
RpcExceptionFilter | https://docs.sentry.io/platforms/javascript/guides/nestjs.md
dataCollection | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
userInfo | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
httpHeaders | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
httpBodies | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
urlQueryParams | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
graphQL | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
genAI | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
stackFrameVariables | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
databaseQueryData | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
tracesSampler | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/javascript/guides/nestjs/configuration/options.md
sendDefaultPii | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
beforeSendSpan | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
beforeSendTransaction | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
ignoreTransactions | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
ignoreSpans | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
is_segment | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
profileLifecycle | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
SentryCron | https://docs.sentry.io/platforms/javascript/guides/nestjs/crons.md
Cron | https://docs.sentry.io/platforms/javascript/guides/nestjs/crons.md
Sentry.withIsolationScope | https://docs.sentry.io/platforms/javascript/guides/nestjs/features/async-context.md
withIsolationScope | https://docs.sentry.io/platforms/javascript/guides/nestjs/features/async-context.md
Processor | https://docs.sentry.io/platforms/javascript/guides/nestjs/features/async-context.md
sourceMap | https://docs.sentry.io/platforms/javascript/guides/nestjs/sourcemaps/uploading/typescript.md
inlineSources | https://docs.sentry.io/platforms/javascript/guides/nestjs/sourcemaps/uploading/typescript.md
sourceRoot | https://docs.sentry.io/platforms/javascript/guides/nestjs/sourcemaps/uploading/typescript.md
debugId | https://docs.sentry.io/platforms/javascript/guides/nestjs/sourcemaps/uploading/typescript.md
debug_id | https://docs.sentry.io/platforms/javascript/guides/nestjs/sourcemaps/uploading/typescript.md
```

## Unconfirmed
- `SentryTraced`: suggested by the brief as a NestJS decorator; not on the NestJS tracing page or any fetched page on 2026-10-20. Left out.
- Release fallback without `SENTRY_RELEASE` (git SHA or hosting env): the NestJS options page states only the env var. The Python page describes a git fallback; not confirmed for `@sentry/nestjs`.
- The v11 default and value set of `traceLifecycle`: listed on the options page, but not read on any fetched page.
- Feedback and feature flags on NestJS: no NestJS page checked.
