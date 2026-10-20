# Angular (module: platforms/angular)

Applies to `@sentry/angular` 11.x (current major; the v10-to-v11 migration page is the reference for changes). v10 columns
are kept because repos on v10 are common. Browser SDK only: the Angular SDK does not run on the server (see SSR).
Framework id `angular` (frameworks.json: dep `@angular/core`, docs `javascript/guides/angular`, wizard `angular`).

## Detect

| Signal | Where | Means |
|---|---|---|
| `@angular/core` in dependencies | package.json, lockfile | Angular app; the Sentry SDK is present when `@sentry/angular` is there too |
| `@sentry/angular` | package.json, lockfile | SDK installed; the version gives the major and the Angular floor |
| `Sentry.init(` | `src/main.ts` | the one init site; a second one (or none) is a finding |
| `bootstrapApplication(` | `src/main.ts` | standalone app; providers live in `app.config.ts` |
| `providers` in an NgModule | `src/app/app.module.ts` | NgModule app; the same providers go there |
| `.sentryclirc`, `.env.sentry-build-plugin` | repo root | wizard/build-plugin token files; must be gitignored |

Library-only Angular repos (no `bootstrapApplication` / app module) do not initialize Sentry: report and move on.

## Install route

- Wizard (user runs it with a TTY): `npx @sentry/wizard@latest -i angular`. It adds `Sentry.init()` to `main.ts`, registers
  `ErrorHandler` and `TraceService` in `app.config.ts`, creates `.sentryclirc` (auth token, added to `.gitignore`), and adds an
  example component. Source: guide, Install section.
- Manual: `npm install @sentry/angular --save`; docs `sentry-ctx docs page platforms/javascript/guides/angular/manual-setup`.
- Older Angular (manual-setup version table, unmaintained 7.x/6.x): 12/13 `@sentry/angular-ivy@^7`; 10/11 `@sentry/angular@^7`; 9 and below `@sentry/angular@^6`.

## Init placement

| Setup | Where | Must be true |
|---|---|---|
| Standalone (`bootstrapApplication`) | `main.ts`, `Sentry.init` before `bootstrapApplication(...)` | docs: "as early as possible" |
| Providers | `app.config.ts` `providers` (NgModule: `app.module.ts`) | `ErrorHandler` and `TraceService` registered once |
| TraceService, Angular 19+ | `provideAppInitializer(() => { inject(Sentry.TraceService); })` | manual-setup, App Config (Angular 19+) |
| TraceService, Angular 18 and older | `APP_INITIALIZER` with `useFactory: () => () => {}`, `deps: [Sentry.TraceService]`, `multi: true` | manual-setup, App Config (Angular <=18) |
| SSR (`app.config.server.ts`) | not there | docs: Sentry providers must not reach the SSR config; SDK is browser-only |

## Options by SDK major

| option | v10 | v11 | note |
|---|---|---|---|
| `sendDefaultPii` | deprecated; when unset, data collection was restrictive | replaced by `dataCollection`; remove it (v11 default matches `sendDefaultPii: true`) | migration, Data Collection |
| `dataCollection` | defaults apply only when this object is set | defaults always apply; unset collects user identity, cookies, headers, bodies | Set `userInfo: false` etc. for a privacy policy; `Sentry.setUser()` data is always sent |
| `traceLifecycle` | transaction model | stream mode is the default; `'static'` restores transactions | migration, Tracing |
| `beforeSendTransaction`, `ignoreTransactions` | work | do nothing in stream mode | use `beforeSendSpan` (payload changed) |
| `tracesSampleRate` / `tracesSampler` | one of them enables tracing | same | the manual example uses `1.0` with a note to lower it in production |
| `tracePropagationTargets` | same-origin requests only by default in browser | same | `[]` disables; cross-origin APIs need an entry |
| `logErrors` (ErrorHandler option) | default `true` | same | `false` only with a reason |

## Product support matrix

Product rows are the JS browser platform (research/06 matrix, not an official page), narrowed by what the Angular guide shows.

| product | supported | notes |
|---|---|---|
| Errors | yes | `createErrorHandler()` as the `ErrorHandler`; Angular wraps errors, so the handler is needed for good extraction |
| Tracing | yes | `browserTracingIntegration` (Angular routing instrumentation); stream mode default in v11 |
| Profiling | unconfirmed | matrix: JS browser UI profiling is beta, Chromium only, >= 10.27; Angular page not checked |
| Replay | yes | `replayIntegration`; `replaysSessionSampleRate` and `replaysOnErrorSampleRate` in the manual example |
| Logs | yes | `Sentry.logger` calls; enabled by default in the guide |
| Metrics | yes | `Sentry.metrics` calls; "Application Metrics" enabled by default in the guide |
| Crons | no | matrix: no crons page for JS browser |
| Feedback | yes | `feedbackIntegration`; the wizard offers it |
| AI / agents | no | matrix: server-side only for JS |
| Flags | unconfirmed | matrix: beta, generic; Angular page not checked |

## Release and artifacts

- Release: the options page says the browser SDK reads `SENTRY_RELEASE.id` from `window` when present, and the `release` option
  sets it. No default derivation (git SHA, hosting env) for the browser build is stated on these pages; the audit checks that
  the release is set explicitly or injected at build time, and that it equals the value used on upload.
- Environment: docs default `production`; the page says development vs production depends on whether the app is packaged.
  Staging must set `environment` explicitly.
- Source maps: production builds need `sourceMap` with `scripts: true` under `architect.build.configurations.production` in
  `angular.json` (sourcemaps page, Manual Setup). Generated `.js.map` files may expose source: deny `.js.map` at the server
  or delete them before deploy.
- Upload routes (pick one; automatic: `npx @sentry/wizard@latest -i sourcemaps`, sourcemaps page):
  1. Angular CLI + custom builder + `sentryWebpackPlugin` (`@angular-builders/custom-webpack`; `ng build` only; the
     `angular-webpack` page). Token: `SENTRY_AUTH_TOKEN` env, or `.env.sentry-build-plugin` (gitignored).
  2. Nx: `@nx/angular` with the same plugin (sourcemaps page).
  3. `sentry-cli sourcemaps inject <dir>` then `sentry-cli sourcemaps upload <dir>` (cli page). Inject writes `debugId`
     into the JS and `debug_id` into the map; verify both before upload.
- Association (optional): `release` in `Sentry.init` identical to the release used on upload. The upload does not create the
  release in Sentry.
- CI: the docs "strongly recommend" running `sentry-cli` in the CI/CD pipeline; env `SENTRY_ORG`, `SENTRY_PROJECT`,
  `SENTRY_AUTH_TOKEN` (cli page, step 2).

## Privacy

| Data | v11 default (`dataCollection` unset) | Control |
|---|---|---|
| user id, email, username, IP (`user.*`) | collected from instrumentation | `dataCollection.userInfo` |
| cookies (names kept; sensitive values `[Filtered]`) | collected | `cookies` |
| request/response headers | collected | `httpHeaders` |
| HTTP bodies (all four directions) | collected | `httpBodies` (`[]` disables) |
| URL query params | collected (sensitive values `[Filtered]`) | `urlQueryParams` |
| stack-frame local variables | collected | `stackFrameVariables`; `frameContextLines` (default `5`) |

The built-in denylist (`auth`, `token`, `password`, ...) scrubs by key name only: best effort.

## Verify recipe

Emit one marked error through the real Angular path, not the devtools console (docs: devtools errors are sandboxed and do not
reach Sentry).

1. Use the wizard's example component if present, or add a temporary button to a component template whose click handler
   throws `new Error("sentry-verify-<marker>")`. Angular routes this through the registered `ErrorHandler`.
2. Optional trace: inside the same handler, `Sentry.startSpan({ op: "test", name: "Example Span" }, () => { ... })` (manual-setup,
   Tracing).
3. Click the button in the running app (`ng serve` is fine for this; the custom builder is `ng build` only). Expect in Sentry
   Issues an error titled with the marker; in Traces, the span if tracing is on.
4. Remove the button, the handler, and the span. Run `ng build` and grep the source for the marker: no hits.

## Gotchas

- Angular does not allow multiple `ErrorHandler` providers. A custom handler must extend `SentryErrorHandler` and call
  `super.handleError(error)` (error-handler page, Multiple Error Handlers).
- Stream mode is the v11 default: `beforeSendTransaction` and `ignoreTransactions` are no-ops; a `beforeSendSpan` written for
  transactions gets a different payload (migration). `traceLifecycle: "static"` is the documented opt-out.
- The manual example's `tracesSampleRate: 1.0` and `replaysSessionSampleRate: 0.1` are examples, not production policy.
- Service worker: Sentry CLI injects debug IDs after `ngsw.json` hashes are computed, so caching breaks. Fix with
  `ngsw-config <dist> <config>` (cli page, Fixing Angular Service Worker caching issues).
- Research note says "Angular 17+" for the wizard row; no fetched page states that minimum. The SDK floor is Angular 14
  (manual-setup). Follow the page.

## Sources

- https://docs.sentry.io/platforms/javascript/guides/angular/
- https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
- https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
- https://docs.sentry.io/platforms/javascript/guides/angular/features/error-handler/
- https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/
- https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/cli/
- https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/angular-webpack/
- https://docs.sentry.io/platforms/javascript/guides/angular/migration/v10-to-v11/

## Identifiers
```identifiers
@sentry/angular | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
@sentry/wizard | https://docs.sentry.io/platforms/javascript/guides/angular/
Sentry.init | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
Sentry.setUser | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
Sentry.startSpan | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
createErrorHandler | https://docs.sentry.io/platforms/javascript/guides/angular/features/error-handler/
SentryErrorHandler | https://docs.sentry.io/platforms/javascript/guides/angular/features/error-handler/
logErrors | https://docs.sentry.io/platforms/javascript/guides/angular/features/error-handler/
ErrorHandler | https://docs.sentry.io/platforms/javascript/guides/angular/features/error-handler/
TraceService | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
provideAppInitializer | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
APP_INITIALIZER | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
useFactory | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
multi | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
bootstrapApplication | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
browserTracingIntegration | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
replayIntegration | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
feedbackIntegration | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
tracePropagationTargets | https://docs.sentry.io/platforms/javascript/guides/angular/manual-setup/
dataCollection | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
userInfo | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
httpHeaders | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
httpBodies | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
urlQueryParams | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
stackFrameVariables | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
frameContextLines | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
cookies | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
tracesSampler | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
traceLifecycle | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/javascript/guides/angular/configuration/options/
sendDefaultPii | https://docs.sentry.io/platforms/javascript/guides/angular/migration/v10-to-v11/
beforeSendSpan | https://docs.sentry.io/platforms/javascript/guides/angular/migration/v10-to-v11/
beforeSendTransaction | https://docs.sentry.io/platforms/javascript/guides/angular/migration/v10-to-v11/
ignoreTransactions | https://docs.sentry.io/platforms/javascript/guides/angular/migration/v10-to-v11/
sourceMap | https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/
sentryWebpackPlugin | https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/angular-webpack/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/cli/
SENTRY_ORG | https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/cli/
SENTRY_PROJECT | https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/cli/
debugId | https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/cli/
debug_id | https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/cli/
ngsw-config | https://docs.sentry.io/platforms/javascript/guides/angular/sourcemaps/uploading/cli/
```

## Unconfirmed
- `zone.js` caveats: no fetched page covers zone.js; not asserted.
- Default release derivation for the browser build (git SHA or hosting env): not stated on the fetched pages.
- Profiling and feature flags for Angular specifically: matrix only (JS browser row), Angular page not checked.
