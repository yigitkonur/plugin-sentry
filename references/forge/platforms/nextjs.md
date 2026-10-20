# Next.js (module: platforms/nextjs)

`@sentry/nextjs` on Next.js 14 or higher, App Router and Pages Router. Current SDK 11.8.0; v10 still patched. Shared JS rules,
stale-API rows and release/source map rules: `platforms/js`. Node.js >= 20.19.0 for v11.

## Detect
| look at | meaning |
|---|---|
| `next` and `@sentry/nextjs` in `package.json` / lockfile | unit is Next.js; read the installed major from the lockfile |
| `next.config.(js\|mjs\|ts)` | is `withSentryConfig` applied, imported from where, which build options |
| `instrumentation.ts` (root or `src/`) | exports `register()` and `onRequestError`; imports the server and edge configs by `NEXT_RUNTIME` |
| `instrumentation-client.ts` | browser init; should export `onRouterTransitionStart` |
| `sentry.server.config.ts`, `sentry.edge.config.ts` | server and edge init (edge file only if edge routes exist) |
| `sentry.client.config.ts` | legacy browser init: deprecated, ignored entirely by Turbopack builds (no browser SDK, no build error) |
| `app/global-error.tsx` / `pages/_error.tsx` | React render error capture for App Router / Pages Router |
| `middleware.ts` (Next 15) / `proxy.ts` (Next 16+) | matcher must exclude the tunnel route |
| `vercel.json` `crons`, `.env*`, `.sentryclirc`, `.gitignore` | cron monitors, DSN env (`NEXT_PUBLIC_SENTRY_DSN` is fine), token leaks |

## Install route
Wizard id `nextjs`: `npx @sentry/wizard@latest -i nextjs` (interactive; the user runs it). Hosted alternative `sentry init <org>/<project> . --features
errors,tracing,...`; flags in `https://cli.sentry.dev/commands/init.md`. `sentry init` is experimental and uploads file excerpts to
a Sentry service: ask the user first, run `--dry-run` first (observed on sentry 0.47.0: previews, changes nothing). Manual or Pages
Router: `sentry-ctx docs page platforms/javascript/guides/nextjs/manual-setup` (and `.../manual-setup/pages-router`, `.../manual-setup/webpack-setup`).
Audit what either writes (ground rule 10, Gotchas below).

## Init placement
| runtime | file | loaded by |
|---|---|---|
| browser | `instrumentation-client.ts` | Next.js, before the app; also `export const onRouterTransitionStart = Sentry.captureRouterTransitionStart` |
| Node.js server | `sentry.server.config.ts` | `register()` in `instrumentation.ts` when `NEXT_RUNTIME === "nodejs"` |
| edge | `sentry.edge.config.ts` | `register()` when `NEXT_RUNTIME === "edge"` |
| server errors | `export const onRequestError = Sentry.captureRequestError` in `instrumentation.ts` | needs `@sentry/nextjs` >= 8.28.0 and Next.js 15 |
| render errors | `app/global-error.tsx` calls `Sentry.captureException` in an effect; Pages Router `_error` awaits `captureUnderscoreErrorException` | |
| Server Actions | wrap with `Sentry.withServerActionInstrumentation` | |
Hybrid apps: both routers share the same init files; add `pages/_error.tsx` for the Pages part.
Build wrapper: `withSentryConfig(nextConfig, {...})` in `next.config.*`, imported from `@sentry/nextjs/config` in v11 (from `@sentry/nextjs` in v10).

## Options by SDK major
| option | v10 | v11 | note |
|---|---|---|---|
| `withSentryConfig` import | `@sentry/nextjs` | `@sentry/nextjs/config` | the entry point moved; `SentryBuildOptions` type moved with it |
| top-level `autoInstrumentServerFunctions`, `autoInstrumentMiddleware`, `autoInstrumentAppDirectory`, `automaticVercelMonitors`, `excludeServerRoutes` | deprecated since 10.30.0 | removed | moved under `webpack.*`; webpack only, no effect on Turbopack |
| `disableLogger`, `disableManifestInjection`, `unstable_sentryWebpackPluginOptions` | deprecated | removed | `webpack.treeshake.removeDebugLogging`, `routeManifestInjection: false`, first-class build options |
| `hideSourceMaps` | removed in v9 | removed | maps are hidden by default and deleted after upload |
| `reactComponentAnnotation` | `webpack.reactComponentAnnotation` | one top-level option, both bundlers | `enabled`, `ignoredComponents`; Turbopack needs Next.js 16+ |
| `applicationKey` | `_experimental.turbopackApplicationKey` | top-level | pairs with `thirdPartyErrorFilterIntegration` `filterKeys` |
| `tunnelRoute` | webpack skipped your middleware | tunnel requests run through middleware | use a fixed string, exclude it in the matcher |
| `environment` default on Vercel | `vercel-production`, `vercel-preview` | `VERCEL_TARGET_ENV` (`production`, `preview`, custom env) | update alerts and dashboards; deploys created by the plugin use the same name (`release.deploy.env`, or `release.deploy: false`) |
| `enableOpenTelemetrySetup` | `skipOpenTelemetrySetup` | on by default for `@sentry/nextjs` | set `false` explicitly when you run your own OpenTelemetry pipeline |
| `sendDefaultPii`, `enableLogs`, `beforeSendTransaction` ... | | see stale-API table | same rows as `platforms/js` |
Build option defaults (all versions with the option): `widenClientFileUpload` false; `sourcemaps.deleteSourcemapsAfterUpload` true (client maps in
`.next/static/` only, server maps stay); `release.create` and `release.finalize` true; `buildTimeInstrumentation` true (Turbopack: Next.js 16+);
`routeManifestInjection` true (App Router only, since 10.34.0); `useRunAfterProductionCompileHook` false on webpack, true on Turbopack
(Next.js 15.4.1+; mutates build output by injecting Debug IDs, so disable it if you rely on artifact integrity hashes).

## Product support matrix
| product | supported | notes |
|---|---|---|
| errors | yes | client, Node server, edge; `onRequestError` plus `global-error.tsx` |
| tracing | yes | `tracesSampleRate` in each init file; webpack: build-time injection, Turbopack: Next.js telemetry; route manifest groups App Router URLs |
| replay, feedback | browser init only | `replayIntegration()` / `feedbackIntegration()` in `instrumentation-client.ts` |
| logs | yes | on by default (>= 10.71.0); v11 has no option |
| profiling | not documented for the Next.js SDK | do not propose without a docs page: see Unconfirmed |
| crons | Vercel crons | `webpack.automaticVercelMonitors` (default false, webpack only) or `_experimental.vercelCronsMonitoring` (both bundlers) |
| AI | `vercelAIIntegration()` | v11: no-op on the Edge runtime (no diagnostics channels) |
Turbopack vs webpack: route exclusion (`webpack.excludeServerRoutes`) and logger tree-shaking are webpack-only; source maps upload post-compile on Turbopack.

## Release and artifacts
Source maps upload happens inside `withSentryConfig` on production builds. Needs `org`, `project`, and `authToken` (set from `SENTRY_AUTH_TOKEN`
in CI/Vercel project settings, never `NEXT_PUBLIC_*`, never a committed `.sentryclirc`). `sourcemaps.assets` / `sourcemaps.ignore` narrow the upload;
`widenClientFileUpload: true` fixes frames in `static/chunks/`. Release name is auto-detected (`release.name` overrides); do not also hardcode `release` in
the init files. `silent: !process.env.CI` keeps local builds quiet. Generic route: `platforms/js`.

## Privacy
Server init files collect request headers, bodies, cookies and user IP under the v11 default (`dataCollection` unset). Set `dataCollection` in
`sentry.server.config.ts`, `sentry.edge.config.ts` and `instrumentation-client.ts` separately from the policy answers. Replay in the client file:
masking defaults and rates are in `platforms/browser-spa`. `tunnelRoute` adds server load and "doesn't currently work with self-hosted Sentry".

## Verify recipe
Temporary route handler `app/api/<random>/route.ts` (or a Pages API route) that calls `Sentry.captureException(new Error("plugin_marker ..."))` with a
unique tag, requested once against `next start` (a production build: source maps are only generated and uploaded on production builds). Delete it
afterwards. Browser path: a temporary client component that throws on click. `sentry-ctx flow verify` owns the polling and cleanup.
R4 needs a frame from your own file: put the throw in a named function inside the route or component file (a `Sentry.captureException(...)` call directly in the handler body gives framework frames only), build with `next build`, upload that build's artifacts for the release the build uses, and run `next start`. A `next dev` event proves arrival (R3) only: dev frames are compiled chunks and local paths.

## Gotchas
| trap | fix | source |
|---|---|---|
| `sentry init` wrote `enableLogs: true` into client and server files on SDK 11 (TS2353) | delete it; logs need no flag | observed 2026-10-20, spike S6 |
| same run: literal DSN in three files, `tracesSampleRate` 1.0 dev / 0.1 prod, no `environment`, `release`, `dataCollection`, no auth-token plumbing, no `.gitignore` entry | read the DSN from env, set the missing options and ignore `.env.sentry-build-plugin` | observed 2026-10-20, spike S6 |
| `sentry.client.config.ts` still the only browser init | move to `instrumentation-client.ts` | pages-router setup page |
| `import { withSentryConfig } from "@sentry/nextjs"` on v11 | `@sentry/nextjs/config` | v10-to-v11 Next.js page |
| `tunnelRoute: true` with auth middleware | random route cannot be excluded: use a fixed path and `(?!sentry-tunnel)`-style negative matcher | manual-setup, webpack-setup pages |
| webpack-only options set while building with Turbopack | they do nothing; drop them | webpack-setup page |
| alerts on `vercel-production` after upgrade | rename to `production` or set `environment` | v10-to-v11 Next.js page |
| `--require` preload in a custom Node start script | unsupported in v11; use `--import` | v10-to-v11 Next.js page |

## Sources
- https://docs.sentry.io/platforms/javascript/guides/nextjs.md
- https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup.md
- https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/pages-router.md
- https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/webpack-setup.md
- https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build.md
- https://docs.sentry.io/platforms/javascript/guides/nextjs/migration/v10-to-v11.md
- https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11.md
- https://cli.sentry.dev/commands/init.md

## Identifiers
```identifiers
onRequestError | https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
onRouterTransitionStart | https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
withServerActionInstrumentation | https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
thirdPartyErrorFilterIntegration | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
filterKeys | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
captureUnderscoreErrorException | https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/pages-router/
tunnelRoute | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
widenClientFileUpload | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
useRunAfterProductionCompileHook | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
routeManifestInjection | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
reactComponentAnnotation | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
applicationKey | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
ignoredComponents | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
SentryBuildOptions | https://docs.sentry.io/platforms/javascript/guides/nextjs/migration/v10-to-v11/
buildTimeInstrumentation | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
authToken | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
enableOpenTelemetrySetup | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
skipOpenTelemetrySetup | https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11/
tracesSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
dataCollection | https://docs.sentry.io/platforms/javascript/configuration/options/
environment | https://docs.sentry.io/platforms/javascript/configuration/options/
```

## Unconfirmed
- Profiling on the Next.js SDK: no Next.js-specific profiling page was fetched; do not state support.
