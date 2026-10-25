# Remix and React Router (module: platforms/remix-react-router)

## Detect

| Signal | Where | Means |
|---|---|---|
| `@remix-run/react`, `@remix-run/node` or `@remix-run/server-runtime` in deps (engine regex `@remix-run/(react\|node\|server-runtime)`) | package.json | Remix v2, framework id `remix`. Remix 3 is a different setup (see Gotchas). |
| `vitePlugin as remix` imported from `@remix-run/dev`; `remix-serve build` in a script | vite.config.ts, package.json | Remix v2 built with Vite. The start script is where the `--import` goes. |
| `react-router` plus `@react-router/dev` (`@react-router/dev/vite` import, `react-router.config.ts`) | package.json, vite.config.ts | React Router v7 Framework Mode, framework id `react-router`. `react-router` alone is declarative/data mode, which has its own guide. |
| `entry.client.tsx`, `entry.server.tsx` (exposed with `npx react-router reveal`); `root.tsx` (Remix) | app/ | Sentry init and error-capture sites |
| `instrument.server.mjs` | repo root | Server instrumentation file. Absent means the server half is not set up. |

Read first: `instrument.server.mjs`, `entry.client.tsx`, `entry.server.tsx`, `root.tsx` (Remix), `vite.config.ts`, `react-router.config.ts` (React Router), and the `dev` and `start` scripts.

## Install route

| Framework | Route | Docs path for `sentry-ctx docs page` |
|---|---|---|
| Remix v2 | Wizard: `npx @sentry/wizard@latest -i remix` (wizard id `remix`) | `platforms/javascript/guides/remix` (wizard); `platforms/javascript/guides/remix/manual-setup` (manual) |
| React Router v7 Framework Mode | `npx sentry@latest init` (AI-driven; the guide labels it experimental) or `npx @sentry/wizard@latest -i reactRouter` | `platforms/javascript/guides/react-router` (wizard); `platforms/javascript/guides/react-router/manual-setup` (manual) |

Remix wizard output, per its guide: `entry.(client|server).tsx` created or updated, `.env.sentry-build-plugin` with an auth token (added to .gitignore), build script or Vite config updated, example page `/sentry-example-page`. Audit each item against the sections below.

## Init placement

Remix v2

| File | What goes there | Evidence |
|---|---|---|
| `instrument.server.mjs` (root) | `Sentry.init` from `@sentry/remix`; with profiling, `nodeProfilingIntegration()` from `@sentry/profiling-node` | Remix manual, Configure Server-Side Sentry |
| Server start script | `NODE_OPTIONS='--import=./instrument.server.mjs' remix-serve build` | Remix manual, server startup step |
| `root.tsx` | `export default withSentry(App)` for server performance | Remix guide, Configure Server-Side Performance Monitoring |
| `entry.client.tsx` | Client `Sentry.init` (the wizard writes it) | Remix guide, Install |
| `entry.server.tsx` | `export const handleError` built with `wrapHandleErrorWithSentry`, or `sentryHandleError` if there is no custom handler | Remix manual, Capture Server-Side Errors |
| `vite.config.ts` | `sentryRemixVitePlugin()` after the `remix(...)` plugin | Remix manual, Configure Vite |

React Router v7 Framework Mode

| File | What goes there | Evidence |
|---|---|---|
| `instrument.server.mjs` (root) | `Sentry.init` from `@sentry/react-router`; `tracesSampleRate`; with profiling, `nodeProfilingIntegration()` | React Router manual, Configure Server-Side Sentry |
| `package.json` `dev` and `start` | `NODE_OPTIONS='--import ./instrument.server.mjs' react-router dev` and `NODE_OPTIONS='--import ./instrument.server.mjs' react-router-serve ./build/server/index.js` | React Router manual, Load Instrumentation on Startup (ESM: load before the app starts) |
| `entry.server.tsx` | `handleRequest = Sentry.createSentryHandleRequest({ ServerRouter, renderToPipeableStream, createReadableStreamFromReadable })`; `handleError = Sentry.createSentryHandleError(...)`; `instrumentations = [Sentry.createSentryServerInstrumentation()]` | React Router manual, Configure Server-Side Sentry |
| `entry.client.tsx` | Client `Sentry.init` above the `hydrateRoot` call | React Router guide, Client-Side Configuration |
| `vite.config.ts`, `react-router.config.ts` | `sentryReactRouter(...)` in Vite plugins; `sentryOnBuildEnd` in the build-end hook | React Router manual, Add Readable Stack Traces With Source Maps |

Right: every start path (`dev`, `start`, container CMD) loads `instrument.server.mjs` with `--import`. The React Router page says the file must load before the app starts, so an init that runs only from `entry.server.tsx` is not the placement it describes.

## Options by SDK major

Current major is v11. The guides use `dataCollection`, the v11 option.

| option | v10 (N-1) | v11 (N) | note |
|---|---|---|---|
| `sendDefaultPii` | Set-able; unset was restrictive | Removed, replaced by `dataCollection` | Migration page: "a behavior change, not a rename" |
| `dataCollection` | Not an option (replacement for `sendDefaultPii`) | Object, per category; unset collects everything | React Router guide: `dataCollection: { userInfo: false }` |
| `tracesSampleRate` | Not split by major on these pages | `1.0` in both guides' examples | Guides say adjust in production |
| `profileSessionSampleRate` | Not split by major on these pages | `1.0` in examples, server only | Requires `nodeProfilingIntegration()` |
| `replaysSessionSampleRate`, `replaysOnErrorSampleRate` | Not split by major on these pages | `0.1` and `1.0` in React Router client example | Client only |
| `tunnel` | Not split by major on these pages | `"/tunnel"` in Remix example | Needs server-side forwarding (Remix troubleshooting page, not fetched) |
| `captureActionFormDataKeys` | Not split by major on these pages | Remix server only | Without it, all action form fields are captured |

## Product support matrix

| product | supported | notes |
|---|---|---|
| replay | yes (client) | React Router guide: `replayIntegration()` with `replaysSessionSampleRate` and `replaysOnErrorSampleRate`. Remix wizard offers Session Replay; the Remix client config is not on the fetched pages (Unconfirmed). |
| profiling | yes (server, Node) | `nodeProfilingIntegration()` from `@sentry/profiling-node` with `profileSessionSampleRate` in the server init (React Router guide; Remix manual). Browser profiling: Unconfirmed. |
| logs | yes, enabled by default | Both verify sections: `Sentry.logger.info`, `Sentry.logger.warn`, `Sentry.logger.error` |
| metrics | yes, enabled by default | Both verify sections: `Sentry.metrics.count`, `Sentry.metrics.gauge`, `Sentry.metrics.distribution` (marked NEW) |
| crons | unconfirmed | Neither guide mentions crons |
| tracing | yes | Server: `withSentry(App)` in `root.tsx` (Remix); `instrumentations` with `createSentryServerInstrumentation()` (React Router). Client: `reactRouterTracingIntegration()` (React Router). |
| feedback | yes (client) | React Router client: `feedbackIntegration()`. Remix wizard lists User Feedback. |
| ai | unconfirmed | Neither guide mentions AI monitoring |
| flags | unconfirmed | Neither guide mentions feature flags |
| debug files | yes | Source maps via `sentryRemixVitePlugin()` (Remix) or `sentryReactRouter` plus `sentryOnBuildEnd` (React Router). See Release and artifacts. |

## Release and artifacts

- Release string: no default derivation is stated on either guide, the Remix manual, or the JS `release` option page (that page only says the browser reads `window.SENTRY_RELEASE.id`). Do not assume a default. Right: `release` is set explicitly in both the server and client init, or both read the same CI-provided value.
- Remix v2 source maps: `sentryRemixVitePlugin()` takes `org`, `project` and `authToken` (the page says `org` and `project` can come from environment variables). It injects debug IDs, uploads source maps during the production build, deletes them from the output afterwards, and turns on hidden source maps unless `build.sourcemap` is set.
- React Router source maps: `sentryReactRouter(sentryConfig, config)` in the Vite plugins, with `authToken: process.env.SENTRY_AUTH_TOKEN`, plus `sentryOnBuildEnd` in `react-router.config.ts`. The page gives both as steps.
- Token location: `SENTRY_AUTH_TOKEN` in the environment, or `.env.sentry-build-plugin` (wizard-created, gitignored). Right: the token is not a literal in `vite.config.ts` or any tracked file.
- CI: the upload runs inside the production build, so the CI build job needs the token.

## Privacy

| Data | Default on the guides | Control |
|---|---|---|
| User identity (IP address, ID, similar) | Sent | `dataCollection: { userInfo: false }` (React Router guide) |
| HTTP bodies, URL query parameters | Sent | `dataCollection` category toggles (React Router guide; both guides link the options page) |
| Keys such as `auth`, `password` | Always filtered, sent as `[Filtered]` | Built-in denylist (React Router guide) |
| Remix action form fields | All fields captured | `captureActionFormDataKeys` allowlist (Remix manual) |

Right: the `dataCollection` block is present in the init the audit reads. In v11 an unset `dataCollection` collects everything, so a missing block is not the restrictive default.

## Verify recipe

Server path (the one this module's init covers):
1. Add a temporary resource route, e.g. `app/routes/sentry-verify.tsx`, whose `loader` throws one marked error: `throw new Error("sentry-verify-<timestamp>")`. Loader errors reach the `handleError` export this module wires.
2. Start the app with the same command the start script uses (with the `--import`). Run `curl -i <app-url>/sentry-verify` and confirm an error response.
3. In Sentry Issues, find the marker in the message and open the event. In Traces, the loader span appears when tracing is on (`tracesSampleRate` above 0).
4. Remove: delete `app/routes/sentry-verify.tsx`, rebuild, and confirm the same `curl` now returns 404.

Browser path (optional): the wizard's `/sentry-example-page`, button "Throw Sample Error" (both guides). Errors raised in browser devtools are sandboxed and are not captured (React Router guide, Important). Remove the example page when it was added only for this check.

## Gotchas

| Trap | Why | Source |
|---|---|---|
| Remix 3 projects get this module | The Remix guide covers Remix 2 only. Remix 3 (alpha) has its own setup page. | Remix guide, "Using Remix 3?" |
| No `--import` means no server instrumentation | React Router runs in ESM mode and the instrumentation file must load before the app. Remix uses `NODE_OPTIONS='--import=...'`. On Windows, set `NODE_OPTIONS` by hand in cmd or PowerShell. | React Router manual; Remix manual |
| Node floor for React Router auto-instrumentation | OpenTelemetry auto-instrumentation only on Node 20 below 20.19 and Node 22 below 22.12. Loaders, actions, middleware and request handlers still traced through `instrumentations` on any Node. The research notes marked this unverified; the page states it. | React Router manual, Configure Server-Side Sentry |
| Example rates are 1.0 | Guide examples use `tracesSampleRate: 1.0`, `profileSessionSampleRate: 1.0`, `replaysOnErrorSampleRate: 1.0`; the guides say adjust in production | React Router guide; React Router manual |
| Custom `handleRequest` | Use `wrapSentryHandleRequest` and `getMetaTagTransformer` by hand; `createSentryHandleRequest` is the default helper | React Router manual, Do you need to customize your handleRequest function |
| CSP nonce | Pass `getNonce` to `createSentryHandleRequest`. Sentry does not set the CSP header; the app must send the same nonce in `script-src`. | React Router manual, nonce section |
| Custom Remix `handleError` | Wrap it with `wrapHandleErrorWithSentry`, or use `sentryHandleError` if there is none. The page offers those two options. | Remix manual, Capture Server-Side Errors |
| `.env` in Vite config | Vite does not load `.env` into `process.env` when it evaluates the config. Use `loadEnv` or `.env.sentry-build-plugin`. | React Router manual, source maps |
| React Router `sentry init` | AI-driven and labelled experimental. Audit what it writes against this module. | React Router guide, Install |
| v10 config carried to v11 | v10 unset `sendDefaultPii` was restrictive; v11 unset `dataCollection` collects everything | Migration v10 to v11 |
| Remix tunnel | `tunnel: "/tunnel"` needs a server endpoint that forwards events to Sentry | Remix guide, Avoid Ad Blockers With Tunneling |

## Sources
- https://docs.sentry.io/platforms/javascript/guides/remix.md
- https://docs.sentry.io/platforms/javascript/guides/remix/manual-setup.md
- https://docs.sentry.io/platforms/javascript/guides/react-router.md
- https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
- https://docs.sentry.io/platforms/javascript/configuration/options.md
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md

## Identifiers
```identifiers
withSentry | https://docs.sentry.io/platforms/javascript/guides/remix.md
tunnel | https://docs.sentry.io/platforms/javascript/guides/remix.md
.env.sentry-build-plugin | https://docs.sentry.io/platforms/javascript/guides/remix.md
captureActionFormDataKeys | https://docs.sentry.io/platforms/javascript/guides/remix/manual-setup.md
wrapHandleErrorWithSentry | https://docs.sentry.io/platforms/javascript/guides/remix/manual-setup.md
sentryHandleError | https://docs.sentry.io/platforms/javascript/guides/remix/manual-setup.md
sentryRemixVitePlugin | https://docs.sentry.io/platforms/javascript/guides/remix/manual-setup.md
NODE_OPTIONS | https://docs.sentry.io/platforms/javascript/guides/remix/manual-setup.md
reactRouter | https://docs.sentry.io/platforms/javascript/guides/react-router.md
dataCollection | https://docs.sentry.io/platforms/javascript/guides/react-router.md
userInfo | https://docs.sentry.io/platforms/javascript/guides/react-router.md
reactRouterTracingIntegration | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
replayIntegration | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
feedbackIntegration | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
nodeProfilingIntegration | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
hydrateRoot | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
handleRequest | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
handleError | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
instrumentations | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
createSentryHandleRequest | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
createSentryHandleError | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
createSentryServerInstrumentation | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
wrapSentryHandleRequest | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
getMetaTagTransformer | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
getNonce | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
logErrors | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
renderToPipeableStream | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
createReadableStreamFromReadable | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
ServerRouter | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
sentryReactRouter | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
sentryOnBuildEnd | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
authToken | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
loadEnv | https://docs.sentry.io/platforms/javascript/guides/react-router/manual-setup.md
sendDefaultPii | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
```

## Unconfirmed
- `release` default for Remix and React Router: not stated on the guide pages, the Remix manual, or the JS options page read on 2026-10-20.
- `crons`, `ai`, `flags` for Remix and React Router: no section on either guide.
- Browser profiling (React Router) and Remix client config for replay and feedback: not on the fetched pages; the Remix wizard writes the client config.
- Node floor for Remix auto-instrumentation: only the React Router manual states it.
- Remix 3 setup (`platforms/javascript/guides/remix/remix-3`) and non-Vite Remix source maps (`guides/remix/sourcemaps`): not fetched.
- Remix tunnel server endpoint (`guides/remix/troubleshooting`): not fetched.
