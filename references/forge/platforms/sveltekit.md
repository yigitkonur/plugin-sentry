# SvelteKit (module: platforms/sveltekit)

## Detect

| Signal | Where | Means |
|---|---|---|
| `@sveltejs/kit` in dependencies | package.json; lockfile gives the exact version | framework `sveltekit` (role fullstack, wizard `sveltekit`) |
| `kit.experimental` block | `svelte.config.js` | SvelteKit 2: server instrumentation and tracing flags live here |
| `sveltekit({...})` call | `vite.config.js` or `.ts` | SvelteKit 3 keeps `tracing` in this call instead |
| `@sentry/sveltekit` | package.json, lockfile | SDK installed; its major selects the column in the options table |
| `src/hooks.client.*`, `src/hooks.server.*`, `src/instrumentation.server.*` | `src/` | the three Sentry wiring points; a missing file means that runtime is not instrumented |
| `@sveltejs/adapter-*` import | `svelte.config.js` | adapter; drives source map upload and the Vercel environment name |

## Install route

| Route | Use when | Docs path |
|---|---|---|
| Wizard: `npx @sentry/wizard@latest -i sveltekit` | greenfield for Sentry, interactive terminal available | platforms/javascript/guides/sveltekit/sourcemaps ("Automatic Setup") |
| Manual: `npm install @sentry/sveltekit --save` (yarn, pnpm variants on the page) | wizard unavailable or failed, or existing Sentry code to audit | platforms/javascript/guides/sveltekit/manual-setup |

Read the manual route with `sentry-ctx docs page <path> --section "<heading>"`: Install, Configure Client-Side Sentry, Configure Server-Side Sentry, Configure Vite, Override Adapter Detection. Audit wizard output as first-party code against the sections below.

## Init placement

| File (`.js` or `.ts`) | Must contain | Notes |
|---|---|---|
| `src/instrumentation.server.*` | server `Sentry.init({ dsn, tracesSampleRate })` | initializes the server SDK; needs the server flag below to be instrumented |
| `src/hooks.client.*` | browser `Sentry.init` with `replayIntegration()` and `feedbackIntegration()`; `export const handleError = Sentry.handleErrorWithSentry(myErrorHandler)` | `handleError` is the hook the docs wire up; `handleErrorWithSentry()` with no argument is also documented |
| `src/hooks.server.*` | `export const handleError = Sentry.handleErrorWithSentry(...)` and `export const handle = Sentry.sentryHandle()` | with your own handler: `sequence(Sentry.sentryHandle(), yourHandler())` |
| `vite.config.*` | `plugins: [sentrySvelteKit(), sveltekit()]` | docs require `sentrySvelteKit` before `sveltekit`; uploads source maps and instruments `load` functions for tracing |
| `svelte.config.js` (SvelteKit 2) | `kit.experimental.instrumentation.server: true`; `kit.experimental.tracing.server: true` for tracing | needs SvelteKit 2.31.0+ and `@sentry/sveltekit` 10.8.0+ |
| `vite.config.*` `sveltekit({...})` (SvelteKit 3) | `tracing: { server: true }` | no instrumentation flag on SvelteKit 3 |

## Options by SDK major

v10 = `@sentry/sveltekit` 10.x. v11 = 11.x, the current major. Only options the SvelteKit pages name.

| option | v10 | v11 | note |
|---|---|---|---|
| `sendDefaultPii` | read only when `dataCollection` is unset; unset means restrictive | replaced by `dataCollection` | if set to `true`, remove it |
| `dataCollection` | available since 10.57.0; defaults apply only when this key is set | defaults always apply (see Privacy) | the audit point for data leaving the app |
| `frameContextLines` | 7 | 5 | source lines captured around each frame |
| `traceLifecycle` | `static` before 11.0.0 | `stream` (default) | `"static"` opts out of span streaming |
| `enableOpenTelemetrySetup` | v10 registers an OTel tracer provider by default; `skipOpenTelemetrySetup` opted out | off by default, except `@sentry/sveltekit`, which needs it for the spans the framework emits | |
| `sourceMapsUploadOptions` | present | removed | move settings into `sentrySvelteKit({...})` |
| `sentrySvelteKit` import | `from "@sentry/sveltekit"` | `from "@sentry/sveltekit/vite"` | the main entry no longer re-exports the plugin |
| `autoUploadSourceMaps` | not checked | on unless `false` | `false` disables upload |
| Vercel deploy environment | `vercel-production` / `vercel-preview` | `VERCEL_TARGET_ENV` value | if events use another environment, set `release.deploy.env` to match, or `release.deploy` to `false` |
| `beforeSendTransaction`, `ignoreTransactions` | listed on the options page | v11 behavior: see Unconfirmed | |

## Product support matrix

No SvelteKit row exists in the platform support matrix. Rows below come from the SvelteKit pages. `unconfirmed` means no fetched page says either way.

| product | supported | notes |
|---|---|---|
| errors | yes | `handleErrorWithSentry` on client and server; errors typed in devtools are not captured |
| tracing | yes | `tracesSampleRate` on both `Sentry.init` calls; server tracing needs the flags above |
| replay | yes (browser) | `replayIntegration()` in `hooks.client`; `replaysSessionSampleRate`, `replaysOnErrorSampleRate` |
| feedback | yes | `feedbackIntegration()` in `hooks.client` |
| logs | yes | `Sentry.logger.info`, `warn`, `error` in the Verify section |
| metrics | yes | enabled by default on this platform; `Sentry.metrics.count` in the Verify section |
| debug files | yes (source maps) | `sentrySvelteKit` upload on production builds; see Release |
| profiling | unconfirmed | `profileSessionSampleRate` is on the options page; no SvelteKit profiling page fetched |
| crons | unconfirmed | no SvelteKit crons page fetched |
| ai | unconfirmed | `genAI` in `dataCollection` controls prompt capture; no SvelteKit AI page fetched |
| flags | unconfirmed | no page fetched |

## Release and artifacts

- **Release string:** the `release` option. The server reads `SENTRY_RELEASE` from the environment; the browser reads `window.SENTRY_RELEASE.id`. No fetched page states a default derivation for SvelteKit (see Unconfirmed). Right: the same release string reaches both runtimes from the build or CI environment.
- **Source maps:** `sentrySvelteKit({ org, project, authToken })` in `vite.config`, imported from `@sentry/sveltekit/vite`. Upload runs only during `npm run build`; `npm run dev` generates no upload. `autoUploadSourceMaps: false` disables it. Use the `adapter` option (for example `"vercel"`) when adapter detection is wrong or unsupported.
- **Token:** `SENTRY_AUTH_TOKEN` in the environment, and present in the CI build that deploys. Vite does not load `.env` into `process.env` during config evaluation; use `loadEnv` or a `.env.sentry-build-plugin` file, which the plugin reads. That file must be gitignored.
- **Debug files and symbols:** no native symbol route on these pages. Source maps are the artifact.
- **CI:** the pages describe upload as part of `npm run build`. No separate CLI step is documented.

## Privacy

Defaults below are v11 (`dataCollection` unset). Keys are case-insensitive partial matches against a built-in denylist (`auth`, `token`, `secret`, `password`, and others); matching values are replaced with `[Filtered]` and cannot be overridden by an `allow` list.

| Category | v11 default | Control |
|---|---|---|
| `userInfo` (IP, id, email, username) | true | `userInfo: false`; `Sentry.setUser()` data is always sent |
| `cookies` | true | `false`; cookie names are always kept |
| `httpHeaders` | request and response, true | one value or `{ request, response }` |
| `httpBodies` | all four types | `httpBodies: []` |
| `urlQueryParams` | true | `CollectBehavior` value |
| `genAI` (`inputs`, `outputs`) | true | `{ inputs, outputs }` |
| `databaseQueryData` | true | `false` |
| `stackFrameVariables` | true | `CollectBehavior` value |
| `frameContextLines` | 5 | number |

## Verify recipe

Emit one marked error through the real server path, then remove it.

1. Create a temporary route `src/routes/sentry-verify/+server.ts` (or `.js`): `export const GET = async () => { throw new Error("sentry-verify <yyyy-mm-dd>"); };`. The docs use the same pattern for the API-route error in their Verify section.
2. Request the route in the running app (dev server or production build). Expect a 500 response, and one issue in Sentry Issues whose message contains `sentry-verify`. The error passes through the `handleError` hook in `src/hooks.server.*`, which `handleErrorWithSentry` wraps.
3. Optional client path: a temporary `src/routes/sentry-verify/+page.svelte` with a button that throws the same marker. Click it in the browser; devtools-console errors are not captured.
4. Remove: delete `src/routes/sentry-verify/`. `grep -r "sentry-verify" src` must return nothing.

## Gotchas

| Trap | Source |
|---|---|
| Server tracing and instrumentation need SvelteKit 2.31.0+ and `@sentry/sveltekit` 10.8.0+. Older setups follow the v10.7.0 manual-setup page. | manual-setup, Configure Server-Side Sentry |
| Research note 04 says both `kit.experimental` flags are needed for SvelteKit. The page says SvelteKit 3 moved tracing into `sveltekit({...})` and needs no instrumentation flag. Follow the page: the flags are SvelteKit 2. | manual-setup (disagrees with research 04) |
| Vite does not load `.env` into `process.env` during config evaluation. `process.env.SENTRY_AUTH_TOKEN` is undefined without `loadEnv`. | manual-setup, Add Readable Stack Traces |
| Source maps are generated and uploaded only on production builds. | sourcemaps, Automatic Setup |
| Errors triggered from browser devtools are sandboxed and never reach Sentry. Test with a page button. | manual-setup, Verify Your Setup |
| `tunnel: "/tunnel"` in `hooks.client` needs a server endpoint that forwards events. The option alone is not enough. | manual-setup, Avoid Ad Blockers; troubleshooting, Using the tunnel option |
| SvelteKit older than 2.16.0 can hit CSP errors from fetch instrumentation. Fixes: upgrade SvelteKit, add a script hash to the CSP, or disable the fetch proxy script. | manual-setup; troubleshooting headings |
| v11 collects more by default (user info, all request and response bodies, cookies). Read the `dataCollection` block; do not assume a v10 default. | v10-to-v11, Data Collection |
| v11 Vercel deploys use `VERCEL_TARGET_ENV` as the environment name, not `vercel-production`. | v10-to-v11, Vercel Deploys Use the Plain Environment Name |
| `sentrySvelteKit` moved to the `@sentry/sveltekit/vite` subpath in v11. | v10-to-v11, The sentrySvelteKit Plugin Moved to a Subpath |
| Cloudflare has its own guide with its own Vite plugin and Wrangler config. Do not audit a Cloudflare project against this module. | platforms/javascript/guides/cloudflare, headings |

## Sources

- https://docs.sentry.io/platforms/javascript/guides/sveltekit.md (headings)
- https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
- https://docs.sentry.io/platforms/javascript/guides/sveltekit/sourcemaps.md
- https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
- https://docs.sentry.io/platforms/javascript/guides/sveltekit/troubleshooting.md (headings)
- https://docs.sentry.io/platforms/javascript/guides/cloudflare.md (headings)

## Identifiers

```identifiers
Sentry.init | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
handleErrorWithSentry | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
Sentry.handleErrorWithSentry | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
handleError | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
Sentry.sentryHandle | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
sentrySvelteKit | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
replayIntegration | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
feedbackIntegration | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
dataCollection | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
userInfo | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
loadEnv | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
Sentry.logger.info | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
Sentry.metrics.count | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
Sentry.startSpan | https://docs.sentry.io/platforms/javascript/guides/sveltekit/manual-setup.md
autoUploadSourceMaps | https://docs.sentry.io/platforms/javascript/guides/sveltekit/sourcemaps.md
authToken | https://docs.sentry.io/platforms/javascript/guides/sveltekit/sourcemaps.md
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
traceLifecycle | https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
window.SENTRY_RELEASE.id | https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
Sentry.setUser | https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
CollectBehavior | https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
beforeSendTransaction | https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
ignoreTransactions | https://docs.sentry.io/platforms/javascript/guides/sveltekit/configuration/options.md
sendDefaultPii | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
frameContextLines | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
enableOpenTelemetrySetup | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
skipOpenTelemetrySetup | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
sourceMapsUploadOptions | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
VERCEL_TARGET_ENV | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
httpBodies | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
httpHeaders | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
urlQueryParams | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
genAI | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
databaseQueryData | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
stackFrameVariables | https://docs.sentry.io/platforms/javascript/guides/sveltekit/migration/v10-to-v11.md
```

## Unconfirmed

- `beforeSendTransaction` and `ignoreTransactions`: research 06 says they do nothing in v11. The v10-to-v11 page has a section on them that was not read; verify before stating the v11 behavior.
- Vercel Edge runtime: research 04 says it is unsupported. No fetched page states this.
- Default release string when `release` is unset: no fetched SvelteKit page states one.
- Profiling, crons, AI, and flags support: no SvelteKit page for these was fetched.
