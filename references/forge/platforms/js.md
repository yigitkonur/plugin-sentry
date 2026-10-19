# JavaScript / TypeScript base (module: platforms/js)

Shared rules for every JS platform module (nextjs, node, browser-spa, and the framework modules). Current `@sentry/*` is 11.8.0
(v11 released 2026-09-23); v10 is still patched. Removed and renamed names are in `data/stale-apis/js.tsv`: believe that table
and read its cited page, do not re-derive it here. Statements below say which major they apply to.

## Detect
| look at | what it tells you |
|---|---|
| `package.json` deps and the lockfile | installed major (the lockfile, not the range); `@sentry/*` family below |
| `@sentry/types` in deps | v11: package is no longer published, import types from `@sentry/core` |
| `@sentry/node-core` in deps | v11: merged back into `@sentry/node` |
| `@sentry/tanstackstart` in deps | v11: removed, use `@sentry/tanstackstart-react` |
| `node` in `engines`, `.nvmrc`, Dockerfile `FROM node:`, CI `node-version` | v11 needs Node >= 20.19.0 (22 needs >= 22.12, 23 needs >= 23.2); Node 18 unsupported |
| `typescript` version | v11 needs >= 5.0.4 |
| bundler config (`vite.config.*`, `webpack.config.*`, `rollup.config.*`, `next.config.*`) | which source map route applies |

| package family | use |
|---|---|
| `@sentry/browser` | any browser app; framework SDKs `@sentry/react`, `@sentry/vue`, `@sentry/svelte`, `@sentry/solid` |
| `@sentry/node` (+ `@sentry/profiling-node`) | Node servers and scripts; `@sentry/bun`, `@sentry/nestjs`, `@sentry/hono` are runtime/framework variants |
| `@sentry/nextjs` | Next.js (own module) |
| `@sentry/vite-plugin`, `@sentry/webpack-plugin`, `@sentry/rollup-plugin`, `@sentry/esbuild-plugin` | build-time source map upload |
| `@sentry/core` | internal; v11: imports straight from it are isomorphic only (`@sentry/core/browser`, `@sentry/core/server` for the rest) |

Libraries do not initialize Sentry (ground rule 8). A package with `@sentry/*` only as a peer dependency and no `init` is not a unit to fix.

## Install route
`npx @sentry/wizard@latest -i <id>` for a framework id in `data/detect/frameworks.json`, or `sentry init` (hosted, experimental,
uploads file excerpts to a Sentry service: ask the user first). Treat the output as untrusted first-party code (ground rule 10).
Manual: `sentry-ctx docs page platforms/javascript/guides/<id>`. Source maps only: `npx @sentry/wizard@latest -i sourcemaps`
(interactive, the user runs it). Migration checklist: `sentry-ctx docs page platforms/javascript/migration/v10-to-v11`.

## Init placement
`Sentry.init` runs once per runtime, before the code it must observe. Browser: first import of the entry point. Node: loaded with
`--import`. Next.js: `instrumentation*.ts` files. Details live in the per-platform modules. v11 cannot warn when a framework was
imported before init (the `disableInstrumentationWarnings` option is gone), so check ordering by reading.

## Options by SDK major
| option | v10 | v11 | note |
|---|---|---|---|
| `dataCollection` | since 10.57.0; applies only when set, otherwise `sendDefaultPii` rules | always applies; UNSET collects everything | categories `userInfo`, `cookies`, `httpHeaders`, `httpBodies`, `urlQueryParams`, `graphQL`, `genAI`, `databaseQueryData`, `queues`, `stackFrameVariables`, `frameContextLines` |
| `sendDefaultPii` | works | removed | see stale-API table; delete it, set `dataCollection` from the policy answers |
| `enableLogs` | required below 10.71.0, default on from 10.71.0 | removed | logs are sent when `Sentry.logger.*` or a logging integration is used |
| `enableMetrics` | opt-in (also `_experiments`) | removed | `Sentry.metrics.*` is enough; `beforeSendMetric` is top-level |
| `traceLifecycle` | since 10.53.1 (opt-in `'stream'`) | default `'stream'` | `'static'` restores transactions (temporary mode) |
| `beforeSendSpan` | `SpanJSON` payload | `StreamedSpanJSON` (`name`, `attributes`, `end_timestamp`) | guard on `is_segment` for what used to be the transaction; `'static'` needs `Sentry.withStaticSpan()` |
| `beforeSendTransaction`, `ignoreTransactions` | work | do nothing in stream mode | use `beforeSendSpan` and `ignoreSpans` (object form to target one op) |
| `ignoreSpans` | since 10.2.0 | evaluated at span start in stream mode | name and attributes set later do not count |
| `attachStacktrace` | no synthetic stack on messages | synthetic stack on `captureMessage` | a message now marks the session errored; `false` restores v10 |
| `tracePropagationTargets` | case-sensitive | case-insensitive; `g`/`y` regex flags ignored | |
| `profileSessionSampleRate`, `profileLifecycle` | since 10.27.0 | same | `profilesSampleRate` removed in v11 (stale-API table) |
| `environment` | `production`/`development` default | same (Vercel Next.js differs, see nextjs module) | |
Scope tags and extra no longer reach streamed spans in v11: use `Sentry.setAttribute`/`setAttributes`.

## Product support matrix
| product | supported | notes |
|---|---|---|
| errors | yes | unhandled errors and rejections are global handlers; v11 browser sessions end `unhandled`, not `crashed` |
| tracing | yes | v11 stream mode lifts the 1000-span transaction cap; span names are low-cardinality in v11 |
| logs | yes (>= 9.41.0) | default on from 10.71.0; `beforeSendLog` filters |
| metrics | yes | v11 base CDN bundle excludes metrics (`*.logs.metrics` bundles only) |
| profiling | Node via `@sentry/profiling-node`; browser beta, Chromium only | browser needs `Document-Policy: js-profiling` response header and `@sentry/browser` >= 10.27.0 |
| replay, feedback | browser only | see browser-spa module |
| crons | server (`withMonitor`, `captureCheckIn`) | |
| AI integrations | server SDKs only | removed from the browser SDK in v11 |

## Release and artifacts
- Release string: `release` option or `SENTRY_RELEASE` (server reads it; browser reads `window.SENTRY_RELEASE.id`). Must equal the
  name CI creates the release under. Recommended `package@version` or the commit SHA; no `/` or `\`, not longer than 200
  characters; names are org-global, so prefix with the project.
- With a Sentry bundler plugin in the build, set the name through the plugin (`release.name`), not a hardcoded `init` value.
- Source maps need both: the build emits maps (production builds only), and they reach Sentry tied to the built files by Debug IDs.
  Debug IDs are injected into the minified file (`//# debugId=`) and the map (`debug_id`); a release is then not required to match.
- Routes, in order of preference: the bundler plugin (webpack, Vite, Rollup, esbuild) or the framework wrapper; otherwise
  `sentry sourcemap inject <dir>` then `sentry sourcemap upload <dir> --release <v>` (v4 CLI, org/project flags: `references/forge/cli.md`; `sentry-cli
  sourcemaps` is the v3 spelling and still routes). Fetch: `sentry-ctx docs page platforms/javascript/sourcemaps/uploading/cli`.
- Use hidden maps for browser builds (`sourcemap: "hidden"` in Vite) and delete maps after upload (`filesToDeleteAfterUpload`) or
  deny `.map` files at the server; generated maps may expose source code.
- Plugin credentials: `authToken`, or `SENTRY_AUTH_TOKEN`, or a `.env.sentry-build-plugin` file that must be in `.gitignore`.
  Put the token in CI secrets, never in a `NEXT_PUBLIC_`/`VITE_` prefixed variable or a committed `.sentryclirc`.
- Vite: place the Sentry plugin after all other plugins; it does not upload in watch/dev mode.
- CI: one build, one upload step, same release string as the SDK. `sentry-cli` v3 spellings (`upload-dsym`, `releases`, `--auth-token`)
  are in `sentry-ctx cli-map`.

## Privacy
v11 defaults send user info, cookies, headers, request/response bodies, AI inputs/outputs, and database query data until
`dataCollection` says otherwise; Sentry scrubs by key name only (`auth`, `token`, `password`, ...), best effort. v10 defaults are
restrictive unless `sendDefaultPii` is true or `dataCollection` is set. Ask the privacy questions, write the answers explicitly.
Keeping the v10 baseline on v11 is the migration page's `dataCollection` block (`userInfo: false`, `cookies: false`,
`httpBodies: []`, ...). `frameContextLines` default is 5 in v11 (7 in v10).

## Verify recipe
Throw or `Sentry.captureException` a marker error from the real code path of the platform module, with a tag value unique to the
run; then read it back with `sentry issue list` filtered by that tag. Remove the trigger afterwards. Source maps: the received
event's frames must show original file names; the uploaded bundle carries the same Debug ID as the deployed file.

## Gotchas
| trap | fix | source |
|---|---|---|
| v11 with Node < 20.19.0 (Dockerfile, CI, Lambda runtime) | raise the runtime everywhere the SDK is installed or built | node migration page |
| `sendDefaultPii: true` left in v11 | delete; unset `dataCollection` already collects everything | migration page |
| `beforeSendTransaction` used to scrub data in v11 | move to `beforeSendSpan` | migration page |
| `tags`/`extra` set on scope expected on spans | `setAttribute`/`setAttributes` | migration page |
| `release` hardcoded in `init` while the plugin injects another | drop it, use `release.name` | releases docs |
| v11 upgrade shifts alert rules | `DOMException.code` tag removed (use `error.type`); crash-free rate moves with `unhandled`; INP is a span | migration page |
| self-hosted Sentry older than 26.4.2 | v11 needs 26.4.2 or higher | migration page |

## Sources
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
- https://docs.sentry.io/platforms/javascript/guides/node/migration/v10-to-v11.md
- https://docs.sentry.io/platforms/javascript/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/node/configuration/apis.md
- https://docs.sentry.io/platforms/javascript/configuration/releases.md
- https://docs.sentry.io/platforms/javascript/logs.md
- https://docs.sentry.io/platforms/javascript/profiling.md
- https://docs.sentry.io/platforms/javascript/sourcemaps.md
- https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/cli.md
- https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite.md
- https://docs.sentry.io/platforms/javascript/sourcemaps/troubleshooting_js/debug-ids.md
- https://docs.sentry.io/product/releases/naming-releases.md
- https://cli.sentry.dev/commands/sourcemap.md
- https://cli.sentry.dev/migrating-from-v3.md

## Identifiers
```identifiers
dataCollection | https://docs.sentry.io/platforms/javascript/configuration/options/
userInfo | https://docs.sentry.io/platforms/javascript/configuration/options/
httpHeaders | https://docs.sentry.io/platforms/javascript/configuration/options/
httpBodies | https://docs.sentry.io/platforms/javascript/configuration/options/
urlQueryParams | https://docs.sentry.io/platforms/javascript/configuration/options/
graphQL | https://docs.sentry.io/platforms/javascript/configuration/options/
genAI | https://docs.sentry.io/platforms/javascript/configuration/options/
databaseQueryData | https://docs.sentry.io/platforms/javascript/configuration/options/
stackFrameVariables | https://docs.sentry.io/platforms/javascript/configuration/options/
frameContextLines | https://docs.sentry.io/platforms/javascript/configuration/options/
traceLifecycle | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendSpan | https://docs.sentry.io/platforms/javascript/configuration/options/
ignoreSpans | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendMetric | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendLog | https://docs.sentry.io/platforms/javascript/configuration/options/
attachStacktrace | https://docs.sentry.io/platforms/javascript/configuration/options/
tracePropagationTargets | https://docs.sentry.io/platforms/javascript/configuration/options/
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
profileLifecycle | https://docs.sentry.io/platforms/javascript/configuration/options/
is_segment | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
end_timestamp | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
authToken | https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
filesToDeleteAfterUpload | https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
debug_id | https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/cli/
SpanJSON | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
StreamedSpanJSON | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
setAttribute | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
setAttributes | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
captureMessage | https://docs.sentry.io/platforms/javascript/guides/node/configuration/apis/
withMonitor | https://docs.sentry.io/platforms/javascript/guides/node/configuration/apis/
captureCheckIn | https://docs.sentry.io/platforms/javascript/guides/node/configuration/apis/
```

## Unconfirmed
- None. (Options listed above were read on the pages under Sources on 2026-10-20.)
