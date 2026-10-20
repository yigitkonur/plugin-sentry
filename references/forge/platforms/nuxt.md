# Nuxt (module: platforms/nuxt)

Applies to `@sentry/nuxt` 11.x (current major). Where the v10 column differs, it is the version before. Pages: Nuxt guide and its
`manual-setup`, `install` (server side), `sourcemaps`, `configuration/options` subpages, all under `platforms/javascript/guides/nuxt`.

## Detect

| Signal | Where | Means |
|---|---|---|
| `nuxt` or `nuxt3` dependency | package.json | framework `nuxt` (role fullstack, wizard `nuxt`, docs `javascript/guides/nuxt`) |
| `@sentry/nuxt` dependency | package.json, lockfile | SDK installed; the lockfile gives the resolved major (11 is current) |
| `modules: ["@sentry/nuxt/module"]` | nuxt.config.ts | module wired; without it the init files are not bundled |
| `sentry.client.config.ts` | project root (same level as package.json) | client init |
| `sentry.server.config.ts` | project root | server init, bundled into the Nitro server build |
| `sentry: { ... }` block | nuxt.config.ts | build-time options only: `org`, `project`, `authToken`, `sourcemaps`, `debug` |

Read both init files. The repo may have only one of them, which is a finding.

## Install route

- Framework wizard: `npx @sentry/wizard@latest -i nuxt` (interactive). Guide: `platforms/javascript/guides/nuxt`.
- AI-powered `npx sentry@latest init`: the guide labels it experimental. Audit its output like any other first-party code.
- Manual (default when the wizard fails): `sentry-ctx docs page platforms/javascript/guides/nuxt/manual-setup`.
- Prerequisites (guide): Nuxt `3.7.0`+, `3.14.0`+ recommended. Below 3.14 the guide adds `overrides` for `ofetch` `^1.4.0` and
  `@vercel/nft` `^0.27.4`. Missing overrides on an old Nuxt is a finding only if the build fails.

## Init placement

| File | Right looks like |
|---|---|
| `nuxt.config.ts` | `modules: ["@sentry/nuxt/module"]` listed once; `sentry` block reads the token from `process.env` |
| `sentry.client.config.ts` | `Sentry.init` with `dsn`, plus `replayIntegration()` / `feedbackIntegration()` and `tracesSampleRate` when those products are on |
| `sentry.server.config.ts` | `Sentry.init` with `dsn` and `tracesSampleRate`; reads `process.env` only |

- The server file is bundled into the Nitro server build. A Nitro plugin the SDK generates imports it, so `Sentry.init()` runs at
  server start. Development and production both work (install page, "How the SDK Initializes on the Server").
- `useRuntimeConfig()` is not ready when the server file runs. Load env with `node --env-file=.env` or `dotenv` (manual-setup).
- DSN: the docs recommend `NUXT_PUBLIC_SENTRY_DSN` through `runtimeConfig.public.sentry.dsn` for the client.

## Options by SDK major

v10 = before the upgrade, v11 = current. "same" means the fetched pages state no change.

| option | v10 | v11 | note |
|---|---|---|---|
| `dataCollection` | applies only when set; without it the deprecated `sendDefaultPii` decides | the control; per-key defaults on the options page | keys include `userInfo`, `httpBodies`; does not change Session Replay |
| `sendDefaultPii` | deprecated; controls collection when `dataCollection` is unset | not the control | replace with `dataCollection` |
| `autoInjectServerSentry` (`sentry` module key) | modes select how the server init is injected | deprecated; remove it to use the bundled init | build prints a deprecation warning when set |
| `experimental_entrypointWrappedFunctions` (`sentry` module key) | set | deprecated, no replacement; remove | still works in v11, removed in the next major |
| `tracesSampleRate` | example `1.0`, page says adjust in production | same | no default stated on the Nuxt pages |
| `replaysSessionSampleRate` / `replaysOnErrorSampleRate` | client config only; example `0.1` / `1.0` | same | replay is client-only |
| `release` | server reads `SENTRY_RELEASE`; browser reads `window.SENTRY_RELEASE.id` | same | see Release and artifacts |
| `environment` | default `production`; env `SENTRY_ENVIRONMENT` | same | staging and dev must set it |
| `tunnel` | example `"/tunnel"` | same | needs a server endpoint (troubleshooting page, "Using the tunnel option") |
| `debug` | default `false`; in the `sentry` block it prints the bundling message at build | same | use to confirm the server file was bundled |

## Product support matrix

| product | supported | notes |
|---|---|---|
| replay | yes, client only | `replayIntegration()` in the client file; no server replay |
| profiling | unconfirmed | options `profileSessionSampleRate` and `profileLifecycle` are on the options page; no Nuxt setup page found |
| logs | yes, enabled by default | `Sentry.logger.info` / `warn` / `error`; `beforeSendLog` option; page `guides/nuxt/logs` |
| metrics | yes, enabled by default | `Sentry.metrics.count`, `gauge`, `distribution`; `beforeSendMetric` option; page `guides/nuxt/metrics` |
| crons | unconfirmed | no Nuxt page in the guide; see Unconfirmed |
| tracing | yes | client and server spans; in `nuxt dev` some library spans can be missing (install page) |
| feedback | yes | `feedbackIntegration()` in the client file |
| ai | unconfirmed | no Nuxt page; the options page mentions generative AI content only under `dataCollection` |
| flags | unconfirmed | no Nuxt page |
| debug files | yes, source maps only | `@sentry/nuxt` uploads source maps in production builds; no native symbols on these pages |

## Release and artifacts

- Release: set `release` in the config or `SENTRY_RELEASE` in the env; server reads the env var, browser reads
  `window.SENTRY_RELEASE.id` (options page). The pages read state no default derivation (no git SHA fallback) for Nuxt. See Unconfirmed.
- Source maps: `@sentry/nuxt` "will generate and upload source maps automatically during production builds" (sourcemaps page).
  Needs `org`, `project`, and `authToken: process.env.SENTRY_AUTH_TOKEN` in the `sentry` block. The token is needed in CI.
- Client source maps are off until set explicitly: `sourcemap: { client: "hidden" }` (Nuxt's own option; `hidden` suppresses the
  reference comments that otherwise 404 once maps are removed).
- Cleanup: `sentry.sourcemaps.filesToDeleteAfterUpload` takes globs such as `.output/**/public/**/*.map`.
- Manual CI upload, if the module is not used: sentry-cli sourcemaps (link on the sourcemaps page, `cli/releases`).

## Privacy

| Data | Default | Control |
|---|---|---|
| user id, email, IP | sent | `dataCollection.userInfo: false` |
| HTTP bodies (incoming/outgoing request and response) | sent | `dataCollection.httpBodies` (set `[]` to disable) |
| URL query parameters, generative AI content | sent | `dataCollection` keys on the options page |
| values whose keys match the built-in denylist (`auth`, `password`) | always sent as `[Filtered]` | not configurable here |
| Session Replay content | separate | Replay privacy options (`session-replay/privacy` page); `dataCollection` does not apply |

## Verify recipe

1. Optional: set `debug` in the `sentry` block and run a build; the bundling message confirms the server file. Remove after.
2. Add a temporary route `server/api/sentry-example.get.ts` whose `defineEventHandler` throws an `Error` with a unique marker
   message (the manual-setup tracing example, marker changed).
3. Run the real production path: `nuxi build`, then `node .output/server/index.mjs`. Dev mode can miss spans.
4. `curl -i http://localhost:3000/api/sentry-example`. Expect an error response; search Issues for the marker.
5. Optional client path: a temporary button with `@click` that throws (manual-setup "Issues" example) proves `sentry.client.config.ts`.
6. Remove: delete `server/api/sentry-example.get.ts` and any test page, rebuild, and confirm the route now returns 404.

## Gotchas

- `--import` is a v10 requirement, not a v11 one. v10 start commands used
  `node --import ./.output/server/sentry.server.config.mjs .output/server/index.mjs`; v11 removed the need. Existing commands keep working
  and the SDK only prints a reminder. Remove the flag and any `NODE_OPTIONS` copy on the host (install page, "Upgrade to SDK Version 11").
  The research note said the current docs no longer show `--import`; the v11 page shows it only in the "Before" side of the upgrade.
- If a user preloads their own file that calls `Sentry.init()`, the SDK skips the bundled init and prints a notice (install page).
- The server file reads only `process.env` at init (manual-setup); `useRuntimeConfig()` values are not available there.
- Prerendering: no init runs during Nitro prerender, so builds send no events and prerendered HTML has no trace meta tags (install page).
- Cloudflare Nitro preset: the server file is not used; use the Cloudflare Nitro plugin (install page).
- Browser devtools console errors are sandboxed and do not reach Sentry; use a button handler for tests (manual-setup).
- `sentry` block options (`org`, `project`, `authToken`) apply at build time only; they do not configure the runtime SDK.
- Generated source maps can expose source code publicly; delete them after upload or deny `.js.map` (sourcemaps page).

## Sources

- https://docs.sentry.io/platforms/javascript/guides/nuxt.md
- https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
- https://docs.sentry.io/platforms/javascript/guides/nuxt/install.md
- https://docs.sentry.io/platforms/javascript/guides/nuxt/sourcemaps.md
- https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/nuxt/troubleshooting.md

## Identifiers

```identifiers
@sentry/nuxt | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
@sentry/nuxt/module | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
@sentry/wizard | https://docs.sentry.io/platforms/javascript/guides/nuxt.md
ofetch | https://docs.sentry.io/platforms/javascript/guides/nuxt.md
@vercel/nft | https://docs.sentry.io/platforms/javascript/guides/nuxt.md
defineNuxtConfig | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
defineEventHandler | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
nuxt.config.ts | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
sentry.client.config.ts | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
sentry.server.config.ts | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
sentry.server.config.mjs | https://docs.sentry.io/platforms/javascript/guides/nuxt/install.md
useRuntimeConfig | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
NUXT_PUBLIC_SENTRY_DSN | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
NODE_OPTIONS | https://docs.sentry.io/platforms/javascript/guides/nuxt/install.md
--import | https://docs.sentry.io/platforms/javascript/guides/nuxt/install.md
autoInjectServerSentry | https://docs.sentry.io/platforms/javascript/guides/nuxt/install.md
experimental_entrypointWrappedFunctions | https://docs.sentry.io/platforms/javascript/guides/nuxt/install.md
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
replayIntegration | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
feedbackIntegration | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
startSpan | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
userInfo | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
dataCollection | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
httpBodies | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
sendDefaultPii | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
release | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
environment | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
traceLifecycle | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
beforeSendLog | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
beforeSendMetric | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
profileLifecycle | https://docs.sentry.io/platforms/javascript/guides/nuxt/configuration/options.md
debug | https://docs.sentry.io/platforms/javascript/guides/nuxt/install.md
tunnel | https://docs.sentry.io/platforms/javascript/guides/nuxt/manual-setup.md
authToken | https://docs.sentry.io/platforms/javascript/guides/nuxt/sourcemaps.md
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/javascript/guides/nuxt/sourcemaps.md
filesToDeleteAfterUpload | https://docs.sentry.io/platforms/javascript/guides/nuxt/sourcemaps.md
sourcemap | https://docs.sentry.io/platforms/javascript/guides/nuxt/sourcemaps.md
sourcemaps | https://docs.sentry.io/platforms/javascript/guides/nuxt/sourcemaps.md
```

## Unconfirmed
- `release`: no default derivation (git SHA or hosting env) is stated on the Nuxt, options, or sourcemaps pages read; check the repo and CI, do not assume.
- crons, ai, flags: no Nuxt setup page in the guide listing; no Nuxt-specific names were taken from a page for these.
- profiling: the options `profileSessionSampleRate` and `profileLifecycle` exist on the options page, but no Nuxt profiling page was found on 2026-10-20.
- server-side source map upload: not covered by the pages read.
