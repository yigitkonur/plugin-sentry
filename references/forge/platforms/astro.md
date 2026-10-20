# Astro (module: platforms/astro)

Applies to `@sentry/astro` 11 (current major; the options page and migration page state 11.0.0 defaults). Astro 4.0.0+ per the guide prerequisites. Server init below is for Node runtimes. On Cloudflare (the unit has the `cloudflare` overlay, usually `@astrojs/cloudflare`) the browser side and the `sentry()` integration stay as here, but the server side is a Worker: read `platforms/cloudflare` (Init placement, Astro on Workers) first and ignore the Node server rows.

## Detect

| Signal | Where | Means |
|---|---|---|
| `astro` dependency | package.json (dependencies or devDependencies), lockfile | Astro app; engine id `astro` (data/detect/frameworks.json: role `fullstack`, priority 92) |
| `@sentry/astro` dependency | package.json, lockfile | SDK installed; the lockfile gives the real major (11 is current) |
| `sentry(` in `integrations`, `import sentry from "@sentry/astro"` | `astro.config.mjs` (or .ts/.js) at root | Integration registered. Config files without this entry are not loaded |
| `sentry.client.config.(ts|js)`, `sentry.server.config.(ts|js)` | project root, or the paths in `clientInitPath` / `serverInitPath` | Browser and server init. Auto-detected at root with these exact names |
| `@sentry/profiling-node` | package.json | Only needed for server profiling |
| Node adapter, `@astrojs/netlify` 5.0.0+, Vercel with Lambda functions | astro config, deploy config | Runtimes this module's server rows cover |
| `@astrojs/cloudflare`, a wrangler config, or the `cloudflare` overlay | package.json, `wrangler.jsonc` | Cloudflare Workers: server init is a wrapped Worker entry (`platforms/cloudflare`); a `sentry.server.config` that is not the wrangler `main` does nothing there |

Read first: the `sentry()` entry in `astro.config.mjs`, then both `sentry.*.config` files. Missing `sentry.server.config` on a Node adapter build means server errors are not captured.

## Install route

- Accelerator: `npx astro add @sentry/astro` (yarn/pnpm variants on the guide). No `@sentry/wizard -i` value: `data/detect/frameworks.json` has no wizard id for astro.
- Manual, from the live page: `sentry-ctx docs page platforms/javascript/guides/astro --section "Install the Sentry SDK"`, then sections "Apply Instrumentation to Your App", "Configure Client-side Sentry", "Configure Server-side Sentry", "Add Readable Stack Traces With Source Maps".
- Source maps: `sentry-ctx docs page platforms/javascript/guides/astro/sourcemaps`.
- Options: `sentry-ctx docs page platforms/javascript/guides/astro/configuration/options --section "release"`.

## Init placement

| File | Runs in | Required | Must contain |
|---|---|---|---|
| `astro.config.mjs` | Astro config (build and dev) | yes | `sentry()` in `integrations`; options `org`, `project`, `authToken` for source maps; `clientInitPath` / `serverInitPath` only when renamed |
| `sentry.client.config.(ts|js)` at root | browser bundle | yes | `Sentry.init({ dsn, ... })`; `Sentry.replayIntegration()` and `Sentry.feedbackIntegration()` when used |
| `sentry.server.config.(ts|js)` at root | Node server runtime | yes | `Sentry.init({ dsn, ... })`; `nodeProfilingIntegration()` when profiling |

The guide does not state ordering against Astro middleware or routes, and has no middleware step: do not require one. Two `Sentry.init` calls for the same runtime, or `Sentry.init` inside a page or route, is a finding.

## Options by SDK major

| option | v10 | v11 (current) | note |
|---|---|---|---|
| `sendDefaultPii` | unset = restrictive; `true` sent user data | removed; replaced by `dataCollection` | migration: if `true` is set, remove it |
| `dataCollection` | not used | unset = collects everything by default; per-category keys, `userInfo` | v11 default is more permissive than v10 for the same config |
| `traceLifecycle` | not `'stream'` before 11.0.0 (option available since 10.53.1) | default `'stream'` | `'static'` keeps transaction mode; env `SENTRY_TRACE_LIFECYCLE=static` |
| `beforeSendTransaction`, `ignoreTransactions` | act on transaction events | no effect when no transaction events are produced (stream) | migration page |
| `beforeSendSpan` | `SpanJSON` payload | different payload; in static mode wrap with `Sentry.withStaticSpan()` | options page + migration page |
| `tracesSampleRate` | in `Sentry.init` | same | guide sets `1.0` as an example; comment says adjust in production |
| `profileSessionSampleRate`, `profileLifecycle` | server init | not split by major on fetched pages | Node runtime only |
| `replaysSessionSampleRate`, `replaysOnErrorSampleRate` | client `Sentry.init` | same | set in `Sentry.init`, not on the `sentry()` options |

Astro-level `sentry()` options (not split by major on fetched pages): `org`, `project`, `authToken`, `clientInitPath`, `serverInitPath`, `sourcemaps` (`assets`, `disable`), `telemetry`.

## Product support matrix

| product | supported | notes |
|---|---|---|
| errors | yes | "Issues" always enabled; browser and Node server |
| tracing | yes | `tracesSampleRate` in both init files; span streaming is the default in v11 |
| profiling | yes, Node runtime only | `@sentry/profiling-node`, `nodeProfilingIntegration()` in server init, `profileSessionSampleRate` (guide value `1.0` is an example) |
| replay | yes, client only | `Sentry.replayIntegration()` in client init; rates in `Sentry.init` |
| logs | yes | `Sentry.logger.info`, `Sentry.logger.warn`, `Sentry.logger.error`; option `beforeSendLog` |
| metrics | yes, on by default | guide: "enabled by default"; `Sentry.metrics.count`, `Sentry.metrics.gauge`, `Sentry.metrics.distribution` |
| crons | unconfirmed | no fetched Astro page covers crons |
| feedback | yes | `Sentry.feedbackIntegration()` in client init (guide "User Feedback") |
| ai | unconfirmed | no fetched Astro page covers AI monitoring |
| flags | unconfirmed | no fetched Astro page covers feature flags |
| debug files | yes for JS source maps only | Vite-plugin upload (sourcemaps page); no native debug-file route on fetched pages |

## Release and artifacts

- Release string: the Astro pages do not set one and do not state a default. `release` is a string in `Sentry.init`; on the server the SDK reads `SENTRY_RELEASE` from the environment; in the browser it reads a `SENTRY_RELEASE` value if set. Right: one explicit value (for example `my-app@1.4.0`, the shape the releases page uses) in both init files or in the runtime env, equal to the value used for the build. Neither set = finding "no release"; do not assume a derived value (see Unconfirmed).
- Source maps: production builds upload when `SENTRY_AUTH_TOKEN` is in the build environment. The `sentry()` options need `org` and `project`. Organization-scoped tokens are preferred; old tokens use the legacy upload page.
- Asset directories: found from `outDir`, `rootDir`, and `adapter`. For a custom build or unsupported adapter, set `sourcemaps.assets` to globs such as `[".clientOut/**/*", ".serverOut/**/*"]`.
- Disable: `sourcemaps.disable: true`. Telemetry from the upload plugin: `telemetry: false`.
- CI: `SENTRY_AUTH_TOKEN` in the build step. Vite does not load `.env` into `process.env` when evaluating the config; use `loadEnv` in the config or a `.env.sentry-build-plugin` file. The sourcemaps page links sentry-cli sourcemaps upload as the alternative.
- Debug files and symbols beyond JS source maps: none on the fetched Astro pages.

## Privacy

| Data | Default | Control |
|---|---|---|
| user identity (IP address, user ID, similar) | sent | `dataCollection` with `userInfo: false` |
| HTTP bodies and URL query parameters | sent | turn off the `dataCollection` categories not needed |
| values under keys on the built-in denylist (for example `auth`, `password`) | always replaced with `[Filtered]` | not configurable on fetched pages |
| source-map upload telemetry | on | `telemetry: false` in `sentry()` options |
| browser event delivery | direct to ingest | `tunnel` option, plus a server endpoint (guide, Troubleshooting page) |

## Verify recipe

Goal: one marked error from the real server path, then removal.

1. Create a temporary route `src/pages/api/sentry-verify.ts`:
   ```ts
   export async function GET() {
     throw new Error("sentry-verify <marker>");
   }
   ```
   Replace `<marker>` with a unique string (for example a timestamp).
2. Run the Node-adapter build (static output has no server runtime to run it). Request the route with `curl` at the URL Astro prints. Expect the request to fail.
3. In Sentry, Issues: search for the marker. Expect exactly one new issue whose stack trace points at the source file (production builds show mapped source once source maps are uploaded).
4. Optional client path: a temporary page with a button that calls `fetch("/api/sentry-verify")`, clicked in a real browser. Browser devtools console errors are not captured (guide).
5. Remove: delete `src/pages/api/sentry-verify.ts` and any temporary page; confirm the route no longer resolves and the diff has no verify files left.

## Gotchas

| Trap | What the docs say | Source |
|---|---|---|
| Non-Node runtime | The Astro guide says the SDK works on Node runtimes only and sends Cloudflare Workers and Pages to the Astro on Cloudflare guide, which installs `@sentry/astro` and `@sentry/cloudflare`; Vercel Edge is not covered | guide, "What runtime do you use?"; `platforms/cloudflare` |
| Netlify adapter version | `@astrojs/netlify` must be 5.0.0 or above | guide, Prerequisites |
| Renamed init files | auto-detected only at root with exact names; move via `clientInitPath` / `serverInitPath` | guide, Configure Client-side Sentry |
| Sample rates copied from the guide | guide values `tracesSampleRate: 1.0` and `profileSessionSampleRate: 1.0` are examples; "adjust this value in production" | guide, both init snippets |
| v11 privacy | unset `dataCollection` collects everything in v11; v10 unset was restrictive, so an upgrade widens data | migration v10-to-v11 |
| Replay rates | set in `Sentry.init` of the client file; the research note that the integration rejects them is consistent with the guide | guide, Configure Client-side Sentry |
| Transaction options | `beforeSendTransaction` and `ignoreTransactions` do nothing in the v11 stream default | migration v10-to-v11 |
| `.env` for the build | `.env` is not loaded into `process.env` during Vite config evaluation | sourcemaps page |
| Unusual output | source-map defaults depend on `outDir`, `rootDir`, `adapter`; unsupported adapter needs `sourcemaps.assets` | sourcemaps page |
| Ad blockers | `tunnel` routes events through an app endpoint and needs server forwarding | guide, Avoid Ad Blockers With Tunneling |
| Profiling install | needs `@sentry/profiling-node` plus `nodeProfilingIntegration()` in the server file | guide, Install and Configure Server-side |

## Sources

- https://docs.sentry.io/platforms/javascript/guides/astro.md
- https://docs.sentry.io/platforms/javascript/guides/astro/sourcemaps.md
- https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options.md
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
- https://docs.sentry.io/platforms/javascript/configuration/releases.md

## Identifiers

```identifiers
defineConfig | https://docs.sentry.io/platforms/javascript/guides/astro.md
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/astro.md
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/astro.md
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/guides/astro.md
replayIntegration | https://docs.sentry.io/platforms/javascript/guides/astro.md
feedbackIntegration | https://docs.sentry.io/platforms/javascript/guides/astro.md
nodeProfilingIntegration | https://docs.sentry.io/platforms/javascript/guides/astro.md
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/astro.md
profileLifecycle | https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options.md
traceLifecycle | https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options.md
beforeSendSpan | https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options.md
beforeSendLog | https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options.md
withStaticSpan | https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options.md
SpanJSON | https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/javascript/guides/astro/configuration/options.md
SENTRY_TRACE_LIFECYCLE | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
sendDefaultPii | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
beforeSendTransaction | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
ignoreTransactions | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
dataCollection | https://docs.sentry.io/platforms/javascript/guides/astro.md
userInfo | https://docs.sentry.io/platforms/javascript/guides/astro.md
clientInitPath | https://docs.sentry.io/platforms/javascript/guides/astro.md
serverInitPath | https://docs.sentry.io/platforms/javascript/guides/astro.md
loadEnv | https://docs.sentry.io/platforms/javascript/guides/astro.md
startSpan | https://docs.sentry.io/platforms/javascript/guides/astro.md
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/javascript/guides/astro/sourcemaps.md
authToken | https://docs.sentry.io/platforms/javascript/guides/astro/sourcemaps.md
sourcemaps | https://docs.sentry.io/platforms/javascript/guides/astro/sourcemaps.md
assets | https://docs.sentry.io/platforms/javascript/guides/astro/sourcemaps.md
outDir | https://docs.sentry.io/platforms/javascript/guides/astro/sourcemaps.md
rootDir | https://docs.sentry.io/platforms/javascript/guides/astro/sourcemaps.md
sentryVitePlugin | https://docs.sentry.io/platforms/javascript/guides/astro/sourcemaps.md
```

## Unconfirmed
- `sentryAstro`: name from a research note for the v11 integration; no fetched Astro page uses it (the guide registers `sentry()`). Do not use.
- `enableLogs`, `enableMetrics`: research says removed in v11; the v10-to-v11 page does not mention them. Do not use until confirmed.
- `prerender`: needed for a server route under static output in Astro; not on any fetched Sentry page. Confirm in Astro docs before writing it.
- Release derivation: whether the Astro integration or upload plugin derives a release from git when `release` is unset; not on fetched pages.
- Crons, AI monitoring, feature flags on Astro: no fetched page; the product matrix stays "unconfirmed".
- Node adapter package name: the guide says "Node adapter" without a package name.
