# Browser apps / SPAs: React, Vue, Svelte, Solid, vanilla (module: platforms/browser-spa)

Client-only apps built with Vite, webpack or similar, on `@sentry/react`, `@sentry/vue`, `@sentry/svelte`, `@sentry/solid` or `@sentry/browser`
(11.8.0; v10 still patched). Shared JS rules, stale-API rows, source map and release basics: `platforms/js`. Meta-frameworks with a server
(Next.js, Remix, SvelteKit, ...) use their own SDK and module, not this one.

## Detect
| look at | meaning |
|---|---|
| `react`/`vue`/`svelte`/`solid-js` + `@sentry/<same>` or `@sentry/browser` in deps | unit is a browser SPA; read `react` version (19 vs <=18) |
| entry file: `src/main.(ts\|tsx\|js)`, `src/index.(tsx\|jsx)`, an `instrument.(js\|ts)` imported first | where `Sentry.init` must be |
| `index.html` with a `browser.sentry-cdn.com` script or loader | CDN route: bundle must include what is configured (tracing, replay, feedback; metrics only in `*.logs.metrics` bundles on v11) |
| `vite.config.*`, `webpack.config.*`, `rollup.config.*` | source map settings and Sentry plugin position |
| `.env*` with `VITE_*`, `REACT_APP_*`, `NEXT_PUBLIC_*` | a DSN there is fine; an auth token there is P0 (ships in the bundle) |
| server code in the same repo or `tunnel` in init | tunnel endpoint to audit |

## Install route
Wizard ids per framework are in `data/detect/frameworks.json`; source maps only: `npx @sentry/wizard@latest -i sourcemaps` (interactive, the user runs
it). Manual: `sentry-ctx docs page platforms/javascript/guides/react` (or `vue`, `svelte`, `solid`, `platforms/javascript` for vanilla). Replay,
feedback and tracing ship in the npm packages: nothing extra to install.

## Init placement
| framework | where | rule |
|---|---|---|
| React | `instrument.js` imported as the first import of the entry point | before `App` and before `createRoot` |
| Vue | `main.js`, `Sentry.init({ app, ... })` | after `createApp` and `createRouter`, before `app.mount`; `browserTracingIntegration({ router })` |
| Svelte | `main.js`/`main.ts` | before `mount(App, ...)` (Svelte v5+) or `new App(...)` (v3-v4) |
| Solid | `index.(jsx\|tsx)` | the docs example gates init with `if (!DEV)`; check that is intended; router tracing via `solidRouterBrowserTracingIntegration()` |
| vanilla | first script of the bundle | before any code that should be instrumented |
React error capture: React 19: `createRoot`/`hydrateRoot` options `onUncaughtError`, `onCaughtError` and `onRecoverableError`, each set to
`Sentry.reactErrorHandler(...)`. React 18 or below: `Sentry.ErrorBoundary` with a `fallback`. Solid: `Sentry.withSentryErrorBoundary(ErrorBoundary)`.
With React Router or TanStack Router, the React guide says to use that router's integration instead of plain `browserTracingIntegration()`.

## Options by SDK major
| option | v10 | v11 | note |
|---|---|---|---|
| `dataCollection` / `sendDefaultPii` | `sendDefaultPii` until `dataCollection` is set | `dataCollection` only; unset collects everything | see `platforms/js` and stale-API table |
| `browserTracingIntegration` web vitals | `enableInp`, standalone spans | adds `webVitalsIntegration` itself; `webVitals: { ignore: ["inp"] }` (also `"cls"`, `"lcp"`) | `enableInp` deprecated; INP is always a span (`browser.web_vital.inp.value` attribute) |
| `softNavigations`, `bfcacheNavigations`, `instrumentBfcacheRestore` | n/a | soft-navigation vitals and bfcache restore navigation on by default (stream mode) | set `false` to keep one set of vitals per page / no restore span |
| `ignorePerformanceApiSpans`, `trackFetchStreamPerformance`, `_experiments.enableInteractions` | on `browserTracingIntegration` | removed | `userTimingIntegration({ ignore })`, `fetchStreamPerformanceIntegration()`, `interactionsIntegration()` |
| `idleTimeout`, `finalTimeout`, `childSpanTimeout` | on `browserTracingIntegration` | interaction spans: on `interactionsIntegration`; pageload/navigation still on BrowserTracing | |
| `browserSessionIntegration` `lifecycle` | per navigation | `'page'` default; `'route'` restores per-navigation sessions | affected sessions end `unhandled`, not `crashed` |
| `tracePropagationTargets` | case-sensitive | case-insensitive; `g`/`y` regex flags ignored | |
| `attachStacktrace` | no stack on messages | synthetic stack on `captureMessage` | `false` restores v10 |
| `beforeSendTransaction`, `ignoreTransactions`, `profilesSampleRate`, `enableLogs` | | see stale-API table | |
| replay options | | no change listed on the v10-to-v11 page | |
Browser SDK in v11: Safari 14 unsupported; AI integrations removed; `breadcrumbsIntegration` no longer has a `console` option (console breadcrumbs come from `consoleIntegration`).

## Product support matrix
| product | supported | notes |
|---|---|---|
| errors | yes | global handlers plus the framework hooks above; `ignoreErrors`, `denyUrls`, `allowUrls` for extension and third-party noise |
| tracing | yes | `browserTracingIntegration`; headers `sentry-trace` and `baggage` go only to `tracePropagationTargets` (default: same origin) |
| replay | yes | `replayIntegration()` plus root-level rates; see Privacy |
| feedback | yes | `feedbackIntegration()`; needs Shadow DOM and `<dialog>`; SDK >= 7.85.0 |
| logs, metrics | yes | `Sentry.logger.*` / `Sentry.metrics.*`; no enabling option on v11 |
| profiling | beta, Chromium only | `Document-Policy: js-profiling` response header; `@sentry/browser` >= 10.27.0 |
| crons, AI | no | server SDKs |

## Release and artifacts
Bundler plugin in the build (`@sentry/vite-plugin`, webpack, Rollup, esbuild): Vite `build.sourcemap` must be on (`"hidden"` recommended), the Sentry plugin
goes after all other plugins, `filesToDeleteAfterUpload` removes maps after upload, no upload in dev/watch mode. Credentials `authToken`/`SENTRY_AUTH_TOKEN` from CI
secrets or an ignored `.env.sentry-build-plugin`; `loadEnv` is needed to read `.env` inside `vite.config`. Debug IDs make a release optional for matching; keep
`release` equal to the plugin's release name when set. `sourcemap: true` without deleting or denying the `.map` files can expose source code publicly. Full route: `platforms/js`.

## Privacy
| item | default | audit |
|---|---|---|
| `maskAllText`, `maskAllInputs`, `blockAllMedia` | `true` | `false` only for a site with no sensitive data (P0 otherwise) |
| `mask`, `block`, `ignore` | `.sentry-mask`/`[data-sentry-mask]` etc. | selectors are added to the defaults |
| `unmask`, `unblock` | `[]` (since v8 they add no default selectors) | keep narrow; `unblock` beats `blockAllMedia`; `iframe[srcdoc]` is blocked unless unblocked |
| `networkDetailAllowUrls` | `[]`: only URL, sizes, method, status | allow-list narrow; `networkCaptureBodies` defaults true for allowed URLs; add headers with `networkRequestHeaders`, `networkResponseHeaders`; deny with `networkDetailDenyUrls` |
| `dataCollection` | v11: everything | set explicitly; `userInfo`, `cookies`, `httpHeaders`, `httpBodies`, `urlQueryParams` all apply in the browser |
Replay rates: `replaysSessionSampleRate` and `replaysOnErrorSampleRate` both default `0`; docs examples use `0.1` and `1.0`. Flag session rate `1.0` in production, flag
on-error rate `0`. `minReplayDuration` default 5000 ms (max 15000), `maxReplayDuration` default 3600000 ms, `mutationLimit` default 10000.

## Verify recipe
In the production build served locally (not the dev server, so the bundler plugin and Debug IDs are exercised), trigger a temporary throw from a rendered
component or `window.setTimeout(() => { throw new Error(marker) })` in the entry, with a unique tag via `Sentry.setTag`; then read the issue back and check the
stack frames show original file names. Remove the trigger. Distributed tracing: the request to the API must carry `sentry-trace` and `baggage`, and the API's
CORS must allow both headers.

## Gotchas
| trap | fix | source |
|---|---|---|
| `Sentry.init` after the framework mounts or after other imports | init first, see Init placement | React, Vue, Svelte guides |
| too generic `tracePropagationTargets` causes extra OPTIONS preflights | list your API origins only; ports count | browser troubleshooting, distributed tracing pages |
| API behind a proxy strips `sentry-trace`/`baggage`, or CORS rejects them | add both headers to the CORS allowlist | distributed tracing page |
| ad-blockers drop events | `tunnel: "/tunnel"` (relative URL, recommended) plus a server endpoint that forwards envelopes to the DSN host; validate DSN host and project id | browser troubleshooting page |
| strict CSP blocks the replay worker | `worker-src 'self' blob:` (and `child-src` for Safari <= 15.4), or self-host via `workerUrl` | session replay page |
| cross-origin script errors show as "Script error" | `crossorigin="anonymous"` plus `Access-Control-Allow-Origin` | browser troubleshooting page |
| Chrome 142+ permission prompt for public app to private-network Sentry | expose Sentry publicly or use `tunnel` | browser troubleshooting page |
| Solid init gated by `!DEV` | intentional in docs; confirm staging builds still report | Solid guide |

## Sources
- https://docs.sentry.io/platforms/javascript/guides/react.md
- https://docs.sentry.io/platforms/javascript/guides/vue.md
- https://docs.sentry.io/platforms/javascript/guides/svelte.md
- https://docs.sentry.io/platforms/javascript/guides/solid.md
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
- https://docs.sentry.io/platforms/javascript/configuration/integrations/webvitals.md
- https://docs.sentry.io/platforms/javascript/session-replay/configuration.md
- https://docs.sentry.io/platforms/javascript/session-replay/privacy.md
- https://docs.sentry.io/platforms/javascript/session-replay.md
- https://docs.sentry.io/platforms/javascript/user-feedback.md
- https://docs.sentry.io/platforms/javascript/user-feedback/configuration.md
- https://docs.sentry.io/platforms/javascript/tracing/distributed-tracing.md
- https://docs.sentry.io/platforms/javascript/troubleshooting.md
- https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite.md

## Identifiers
```identifiers
reactErrorHandler | https://docs.sentry.io/platforms/javascript/guides/react/
onUncaughtError | https://docs.sentry.io/platforms/javascript/guides/react/
onCaughtError | https://docs.sentry.io/platforms/javascript/guides/react/
onRecoverableError | https://docs.sentry.io/platforms/javascript/guides/react/
ErrorBoundary | https://docs.sentry.io/platforms/javascript/guides/react/
createApp | https://docs.sentry.io/platforms/javascript/guides/vue/
createRouter | https://docs.sentry.io/platforms/javascript/guides/vue/
interactionsIntegration | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
captureMessage | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
withSentryErrorBoundary | https://docs.sentry.io/platforms/javascript/guides/solid/
browserTracingIntegration | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
webVitalsIntegration | https://docs.sentry.io/platforms/javascript/configuration/integrations/webvitals/
softNavigations | https://docs.sentry.io/platforms/javascript/configuration/integrations/webvitals/
bfcacheNavigations | https://docs.sentry.io/platforms/javascript/configuration/integrations/webvitals/
instrumentBfcacheRestore | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
idleTimeout | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
finalTimeout | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
childSpanTimeout | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
browserSessionIntegration | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
breadcrumbsIntegration | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
consoleIntegration | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
attachStacktrace | https://docs.sentry.io/platforms/javascript/configuration/options/
tracePropagationTargets | https://docs.sentry.io/platforms/javascript/configuration/options/
dataCollection | https://docs.sentry.io/platforms/javascript/configuration/options/
userInfo | https://docs.sentry.io/platforms/javascript/configuration/options/
httpHeaders | https://docs.sentry.io/platforms/javascript/configuration/options/
httpBodies | https://docs.sentry.io/platforms/javascript/configuration/options/
urlQueryParams | https://docs.sentry.io/platforms/javascript/configuration/options/
ignoreErrors | https://docs.sentry.io/platforms/javascript/configuration/options/
denyUrls | https://docs.sentry.io/platforms/javascript/configuration/options/
allowUrls | https://docs.sentry.io/platforms/javascript/configuration/options/
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
minReplayDuration | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
maxReplayDuration | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
mutationLimit | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
workerUrl | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
networkDetailAllowUrls | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
networkDetailDenyUrls | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
networkCaptureBodies | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
networkRequestHeaders | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
networkResponseHeaders | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
maskAllText | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
maskAllInputs | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
blockAllMedia | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
authToken | https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
filesToDeleteAfterUpload | https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
loadEnv | https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
```

## Unconfirmed
- Replay behaviour in v11: the v10-to-v11 page lists no replay change; defaults above come from the replay pages, which are not versioned. Re-read them if a v11 replay regression is suspected.
