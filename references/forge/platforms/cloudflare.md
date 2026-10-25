# Cloudflare Workers and Pages (module: platforms/cloudflare)

## Detect
| Signal | Where | Meaning |
|---|---|---|
| `wrangler.jsonc`, `wrangler.json` or `wrangler.toml` at the app root | repo root | Workers project; the strongest signal (engine overlay note) |
| deps `wrangler`, `@cloudflare/workers-types`, `@cloudflare/vite-plugin`, `@cloudflare/vitest-pool-workers` | `package.json` | Cloudflare toolchain |
| dep `@sentry/cloudflare`; calls `withSentry(`, `instrumentDurableObjectWithSentry(`, `defineCloudflareOptions(`, `sentryPagesPlugin` | package.json, Worker entry, `functions/_middleware.js` | Sentry already present |
| `instrument.server.ts` (or `.mts`, `.js`, `.mjs`, `.cjs`) beside the Worker entry | source tree | Options file read by the Vite plugin |

Engine record (`data/detect/frameworks.json`, id `cloudflare`): role `serverless`, `overlay: true`, docs path `javascript/guides/cloudflare`, wizard id `cloudflare`. An overlay means the framework is detected first and this module adds the runtime. In the fixture `evals/fixtures/cloudflare-worker` the engine reports framework `hono` with overlay `cloudflare`; audit the Hono module for the Hono API and this module for wrangler config, runtime flags and the Sentry wrapper.

Files to read: wrangler config (`main` names the entry); the entry (fixture: `src/index.ts`, `Sentry.withSentry(` at line 11, DSN read from `env.SENTRY_DSN`); `vite.config.*` if present; `instrument.server.*` beside the entry; `functions/_middleware.js` for Pages.

## Install route
Use the manual route from the live docs. Do not paste install steps from memory.

| Path | When | Docs path for `sentry-ctx docs page` |
|---|---|---|
| Vite plugin (`sentryCloudflareVitePlugin`) | Project already builds with Vite (`@cloudflare/vite-plugin`) | `platforms/javascript/guides/cloudflare` (section "Add the Vite Plugin"), `.../cloudflare/install/vite-plugin` |
| Plain Wrangler (`withSentry` wrapper) | Wrangler-only build, no Vite | `.../cloudflare/install/wrangler` |
| Pages Functions (`sentryPagesPlugin`) | Cloudflare Pages `functions/` directory | `.../cloudflare/features/pages` |
| Hono on Workers (`sentry` middleware) | Hono app; the Hono page shows this path | `.../cloudflare/frameworks/hono` |
| Astro on Workers | `astro` + `@astrojs/cloudflare`; the unit carries both `platforms/astro` and this module | `.../cloudflare/frameworks/astro` |
| Source maps | Any build that should upload maps | `.../cloudflare/sourcemaps` (wizard `-i sourcemaps`) |

Wizard: the docs page shows `npx @sentry/wizard@latest -i sourcemaps`, which installs packages, configures the build tool and configures CI. Confirm the wizard id `cloudflare` (engine data) with the wizard's `--help` before proposing it; see Unconfirmed.

## Init placement
- Vite path: the plugin wraps the entry named by `main` and any Durable Object, Workflow or Agents class declared in the wrangler config. An entry already wrapped by hand is left alone. `instrument.server.*` must sit beside the entry: for `main: src/worker/index.ts` the file is `src/worker/instrument.server.ts`, not the project root.
- Plain path: the module's default export is `withSentry(optionsCallback, handler)`. Each Durable Object, Workflow or Agent class is wrapped with its own `instrument...WithSentry` call and exported under the class name the wrangler binding uses.
- Pages: `sentryPagesPlugin` must be the first entry of the `onRequest` array in `functions/_middleware.js`. The docs say "Make sure Sentry is the first middleware".
- Hono: `sentry(app, options)` is added with `app.use(...)` as early as possible, before the routes it should cover.
- Astro on Workers (Astro 6.0.0+, `@astrojs/cloudflare` 13+, `@sentry/astro` and `@sentry/cloudflare` 10.40.0+; install both): wrangler `main` points at `./sentry.server.config.ts`, which default-exports `Sentry.withSentry(optionsCallback, handler)` with `handler` imported from `@astrojs/cloudflare/entrypoints/server`. `sentry()` stays in `astro.config.mjs` `integrations`; the browser `Sentry.init` is `sentry.client.config.(ts|js)` using `@sentry/astro`. A `sentry.server.config.ts` that only calls `Sentry.init` and is not the wrangler `main` is the Node guide pasted into a Worker: server errors are not reported. DSN comes from `env.SENTRY_DSN`.
- Astro 3 to 5 with `@astrojs/cloudflare` 12: `@sentry/astro` detects the adapter and wraps the Worker itself; server config is environment variables only (`SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_RELEASE`, `SENTRY_ENVIRONMENT`), and `sentry.server.config` is not supported. For Pages, the `_middleware.js` route above applies.

## Options by SDK major
Columns: v10 is N-1, v11 is the current major (N). Only options the docs list for this platform.

| option | v10 (N-1) | v11 (N, current) | note |
|---|---|---|---|
| `dataCollection` | Defaults apply only when this key is set; without it `sendDefaultPii` decides | Defaults always apply | Available since 10.57.0 (options page) |
| `sendDefaultPii` | Controls collection when `dataCollection` is unset | Deprecated; use `dataCollection` | Options page marks it deprecated; it does not say when it was removed |
| `traceLifecycle` | Not stated on the page | Stream mode is the default; `'static'` restores the legacy transaction model | Page gives no major; check the installed `@sentry/cloudflare` version |
| `rpcTracePropagationBindings` | Plain Wrangler builds list bindings by hand; Vite builds derive them from 10.72.0 | Same rule; the page names no v11 change | Install/wrangler page; derivation page: vite-plugin |
| `instrumentAgentWithSentry` | Needs 10.69.0+ | Needs 10.69.0+ | Supports `Agent`, `AIChatAgent`, `McpAgent` |

## Product support matrix
| product | supported | notes |
|---|---|---|
| tracing | yes | Stream mode by default; enable with `tracesSampleRate` or `tracesSampler` (options page). Streamed-spans page exists under the guide. |
| logs | yes | Verify page has a Logs step; `beforeSendLog` hook (options page) |
| metrics | yes | Verify page has an "Application Metrics" step; `beforeSendMetric` hook (options page) |
| debug files | yes | Source maps only: `upload_source_maps` in wrangler config plus the sourcemaps route. See Release and artifacts. |
| ai | yes, Agents SDK only | `instrumentAgentWithSentry` (10.69.0+); content capture via `dataCollection.genAI`. Other AI clients: unconfirmed. |
| profiling | unconfirmed | Options page lists `profileSessionSampleRate` and `profileLifecycle` for Cloudflare, but no Cloudflare profiling page was fetched |
| replay | unconfirmed | No replay page in the Cloudflare guide; a Worker renders no DOM |
| crons | unconfirmed | Fixture has `triggers.crons` and a `scheduled` handler; no Workers cron page was fetched |
| feedback | unconfirmed | No Cloudflare feedback page fetched |
| flags | unconfirmed | No Cloudflare feature-flag page fetched |

## Release and artifacts
- Default release: the SDK reads `SENTRY_RELEASE` first, then the `CF_VERSION_METADATA.id` binding (guide, "Release Configuration"). The binding exists only when wrangler config declares `version_metadata` with `binding` set to `CF_VERSION_METADATA`. The page lists no third source: with neither set, no release is sent.
- Audit: the fixture `wrangler.jsonc` has no `version_metadata`, so its release comes only from CI setting `SENTRY_RELEASE`. Right: one of the two is set on every deploy.
- Source maps: set `upload_source_maps: true` in wrangler config (guide, "Add Readable Stack Traces"), then run `npx @sentry/wizard@latest -i sourcemaps`. The wizard configures the build tool and CI. Manual route: the bundler guides linked from the sourcemaps page (not fetched).
- No native debug files or symbol upload: the Cloudflare pages fetched cover source maps only.

## Privacy
Defaults from `dataCollection` (options page). The SDK always replaces values of keys in its built-in denylist (`auth`, `token`, `password` and similar) with `[Filtered]`.

| key | default | what it sends |
|---|---|---|
| `userInfo` | true | `user.*` fields: id, email, username, IP address inferred from the request |
| `httpHeaders` | both directions true | request and response headers |
| `httpBodies` | all four body types | incoming and outgoing request and response bodies |
| `urlQueryParams` | true | query parameter values (sensitive ones filtered) |
| `cookies` | true | cookie values (sensitive ones filtered) |
| `genAI` | inputs and outputs true | prompt and completion content |
| `databaseQueryData` | true | bound query parameters and result data |
| `queues` | true | task arguments |
| `stackFrameVariables` | true | local variable values in stack frames |

Right: a deliberate `dataCollection` block in `instrument.server.*` (or the options callback) that turns off what the product does not need. Without the key, v11 still sends these defaults.

## Verify recipe
Use the real Worker entry, so the marker travels the wrapper that ships. Add a temporary route to the fetch handler; for the fixture, wrap `fetch` so the check runs before Hono (`Sentry.startSpan` around handler code is shown on the Cloudflare Pages page):

```ts
fetch: async (req, env, ctx) => {
  if (new URL(req.url).pathname === "/debug-sentry") {
    await Sentry.startSpan({ op: "test", name: "verify-span" }, async () => {
      throw new Error("sentry-verify-<date>"); // marker
    });
  }
  return app.fetch(req, env, ctx);
},
```

1. Run `vite dev` when the Vite plugin is in place, otherwise `wrangler dev`; request the local URL it prints with `curl -i <url>/debug-sentry`.
2. Expect one issue whose message carries the marker, and a trace whose span shows the `verify-span` name. CPU-only spans show 0 ms (see Gotchas).
3. Remove: restore `fetch: app.fetch,`, delete the block and the marker, and confirm `git diff` shows only intended lines.

For Pages, the docs give no Pages-specific verify step; place the same temporary throw in a function under `functions/` and expect the same issue.

## Gotchas
- `nodejs_compat` plus `compatibility_date` of 2024-09-23 or later is required, because the SDK needs `AsyncLocalStorage` (guide and Hono page). Use the latest date; the docs say some integrations need newer runtime features.
- Span durations read `0ms` for CPU-bound work: the runtime clock advances only after I/O (guide, "Known Limitations"). This is expected, not a bug.
- Tracing is off unless `tracesSampleRate` or `tracesSampler` is set (options page). `tracesSampler` wins when both are set.
- Plain Wrangler cannot patch bundled packages (database and AI clients); those spans are missing without the Vite plugin's `buildTimeInstrumentation` (install/wrangler, "What You Give Up").
- Research note C8 said packages can only be instrumented at build time. The fetched docs say `withSentry` without Vite still instruments the handlers and `fetch`; follow the docs.
- Pages: `sentryPagesPlugin` comes from the package root (`Sentry.sentryPagesPlugin` in the docs). Research note C1 says a `pages` subpath import does not exist; the fetched page shows only the root export. Where a project cannot add the `onRequest` middleware, the Pages page offers `wrapRequestHandler` from `@sentry/cloudflare/request`.
- Cloudflare has its own Logs, Traces and Issues (Workers Logs is on by default for new Workers; Traces and Issues are opt-in): read `products/cf-observability` and the policy answer `cloudflare.owner` before proposing Sentry logs or tracing here.
- Vite plugin: run `vite build` before `wrangler deploy`; use `vite dev` in place of `wrangler dev` (guide, "Add the Vite Plugin").
- Inference, not on a page: do not wrap `app.fetch` with `withSentry` and also add the Hono `sentry` middleware in one Worker; the docs show each path on its own.

## Sources
- https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
- https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
- https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/vite-plugin.md
- https://docs.sentry.io/platforms/javascript/guides/cloudflare/sourcemaps.md
- https://docs.sentry.io/platforms/javascript/guides/cloudflare/features/pages.md
- https://docs.sentry.io/platforms/javascript/guides/cloudflare/frameworks/hono.md
- https://docs.sentry.io/platforms/javascript/guides/cloudflare/tracing/streamed-spans.md (headings only)

## Identifiers
```identifiers
withSentry | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
instrumentDurableObjectWithSentry | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
instrumentWorkflowWithSentry | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
instrumentAgentWithSentry | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
AIChatAgent | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
McpAgent | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
rpcTracePropagationBindings | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
@sentry/cloudflare | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/wrangler.md
@sentry/cloudflare/vite | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
@sentry/cloudflare/request | https://docs.sentry.io/platforms/javascript/guides/cloudflare/features/pages.md
@sentry/hono/cloudflare | https://docs.sentry.io/platforms/javascript/guides/cloudflare/frameworks/hono.md
sentryCloudflareVitePlugin | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
autoInstrumentation | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/vite-plugin.md
buildTimeInstrumentation | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/vite-plugin.md
wranglerConfigPath | https://docs.sentry.io/platforms/javascript/guides/cloudflare/install/vite-plugin.md
defineCloudflareOptions | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
nodejs_compat | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
AsyncLocalStorage | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
compatibility_date | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
version_metadata | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
CF_VERSION_METADATA | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
upload_source_maps | https://docs.sentry.io/platforms/javascript/guides/cloudflare.md
startSpan | https://docs.sentry.io/platforms/javascript/guides/cloudflare/features/pages.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
tracesSampler | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
traceLifecycle | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
profileLifecycle | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
beforeSendLog | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
beforeSendMetric | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
dataCollection | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
sendDefaultPii | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
userInfo | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
httpHeaders | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
httpBodies | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
urlQueryParams | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
cookies | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
genAI | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
databaseQueryData | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
queues | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
stackFrameVariables | https://docs.sentry.io/platforms/javascript/guides/cloudflare/configuration/options.md
sentryPagesPlugin | https://docs.sentry.io/platforms/javascript/guides/cloudflare/features/pages.md
wrapRequestHandler | https://docs.sentry.io/platforms/javascript/guides/cloudflare/features/pages.md
onRequest | https://docs.sentry.io/platforms/javascript/guides/cloudflare/features/pages.md
_middleware.js | https://docs.sentry.io/platforms/javascript/guides/cloudflare/features/pages.md
```

## Unconfirmed
- `waitUntil` and `flush`: the brief asked for guidance on these; no fetched official page covers them. Do not require them in an audit.
- `SENTRY_TRACE_LIFECYCLE`: taken from a research note only; no fetched page names it.
- Span operation names for cron, email and workflow steps changing in v11: research note only; no fetched page confirms it.
- Wizard id `cloudflare` (engine data) and a `-i cloudflare` flag: the fetched docs show only `-i sourcemaps`.
