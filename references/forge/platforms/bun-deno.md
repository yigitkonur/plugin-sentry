# Bun and Deno (module: platforms/bun-deno)

Covers `@sentry/bun` (Bun) and `@sentry/deno` (Deno, beta per its guide). Framework ids: `bun`, `deno`. Docs: `platforms/javascript/guides/bun` and `platforms/javascript/guides/deno`.

## Detect

| Signal | Where | Means |
|---|---|---|
| `bun-types` or `@types/bun` in deps; `bun.lock` / `bun.lockb` | package.json, lockfile | Bun app |
| `@sentry/bun` in deps | package.json, `bun.lock` | SDK installed for Bun |
| `@sentry/deno` import map entry (`"@sentry/deno": "npm:@sentry/deno"`) | `deno.json` / `deno.jsonc` | SDK installed for Deno |
| `"nodeModulesDir": "auto"` | `deno.json` | required by the Deno import hook |
| `Sentry.init` call | `instrument.js` (Bun) or the Deno entry file | the init site(s) to read |
| `--preload` flag | package.json scripts, Dockerfile, CI, Procfile | Bun preload route in place |
| `sentryBunPlugin` / `Bun.build` | build script or bundler config | Bun dependency spans |
| `deno run` with `--allow-net`, `--allow-env`, `--allow-read`, `--allow-sys` | scripts, `deno.json` tasks, Dockerfile | Deno permissions |
| the SDK's `/import` hook as the first import | Deno entry file | Deno import hook |

## Install route

| Runtime | Route | Docs path |
|---|---|---|
| Bun | `bun add @sentry/bun` | `sentry-ctx docs page platforms/javascript/guides/bun --section "Install the SDK"` |
| Deno | npm specifier in `deno.json` imports; Deno 2.8.3 or later | `platforms/javascript/guides/deno`, section "Import the Sentry SDK" |

No `sentry init` or init wizard step is named on either page. The wizard is documented only for source maps: `npx @sentry/wizard@latest -i sourcemaps`. Write the rest from the live page, not from memory.

## Init placement

| Runtime | Where | Rule |
|---|---|---|
| Bun | `instrument.js` in the project root | init "as early as possible"; the snippet says to call it before importing any other module |
| Bun | process start: `bun --preload ./instrument.js app.js` | `--preload` makes init run before other modules load |
| Bun, bundled | `Bun.build` with `plugins: [sentryBunPlugin()]`, run the output with `--preload` | the plugin is what adds dependency spans |
| Deno | first import of the entry file is the SDK's `/import` hook (the guide's `import "<sdk-package-name>/import"`), then the SDK import as `Sentry` | the hook "only works as the first import of your entry file" |

Findings: `Sentry.init` only inside app code after other imports; a Bun start command without `--preload`; a Deno entry whose first import is not the hook.

## Options by SDK major

| option | v10 | v11 (current) | note |
|---|---|---|---|
| `dataCollection` | defaults apply only when the key is set; without it `sendDefaultPii` controls collection | defaults always apply | Bun options page: "available since 10.57.0" |
| `sendDefaultPii` | deprecated; controls collection when `dataCollection` is unset | not described on the page | use `dataCollection` |
| `tracesSampleRate` | same (page does not split by major) | same | docs example `1.0`; "adjust in production" |
| `release` | same (page does not split by major); server SDK reads `SENTRY_RELEASE` | same | see Release and artifacts |
| `environment` | same (page does not split by major); table default `production` | same | prose disagrees, see Gotchas |

## Product support matrix

| product | supported | notes |
|---|---|---|
| Errors | yes | Issues, always enabled; `Sentry.captureException` on caught errors |
| Tracing | yes | `tracesSampleRate`, `Sentry.startSpan`. Bun: `Bun.serve`, `node:http` and `fetch` spans work without the plugin; database, AI SDK and framework spans need `sentryBunPlugin`. Deno: the import hook covers database drivers, message queues, AI libraries and web frameworks |
| Logs | yes | `Sentry.logger.info`, `Sentry.logger.warn`, `Sentry.logger.error`. Deno guide carries a beta banner |
| Metrics | yes, on by default | "Application Metrics ... enabled by default" on both guides; `Sentry.metrics.count`, `Sentry.metrics.gauge`, `Sentry.metrics.distribution` |
| AI / agents | partial | Bun Topics list "Agent Tracing"; AI SDK spans come from `sentryBunPlugin` (Bun) or the import hook (Deno). Not checked per SDK |
| Profiling | unconfirmed | no profiling content on either guide; product matrix has no Bun or Deno row |
| Replay | unconfirmed | not in either guide's install feature list; matrix Node row is "—" |
| Crons | unconfirmed | not in either guide's install feature list; no matrix row |
| Feedback | unconfirmed | not in either guide's install feature list; no matrix row |
| Feature flags | unconfirmed | not in either guide's install feature list; no matrix row |
| Debug files | source maps only | JS source maps (Release and artifacts); no native symbol route on these pages |

## Release and artifacts

- Release: the Bun options page says the server SDK reads `SENTRY_RELEASE` from the environment and names no other source. Check that the variable is set in the runtime environment of the process, not only at build time.
- Environment: set `SENTRY_ENVIRONMENT` (or `environment`) explicitly; see Gotchas.
- Source maps: the wizard (`npx @sentry/wizard@latest -i sourcemaps`), or the uploading index `platforms/javascript/guides/bun/sourcemaps/uploading` (Deno: `platforms/javascript/guides/deno/sourcemaps/uploading`). The Bun index lists Webpack, Vite, esbuild, Rollup, tsc, Sentry CLI and others; none is `Bun.build`. Use the Sentry CLI entry for a `Bun.build` output and confirm on that page.
- Debug IDs and native symbols: none documented on either guide.

## Privacy

| Data | Default (v11) | Control |
|---|---|---|
| user id, email, username, IP | sent | `dataCollection` `userInfo` set to `false` |
| HTTP headers and cookies | sent; sensitive values become `[Filtered]` | `httpHeaders`, `cookies` |
| HTTP bodies (all four types) | sent | `httpBodies` set to an empty list |
| URL query params | sent; sensitive values become `[Filtered]` | `urlQueryParams` |
| GraphQL document and variables | sent | `graphQL` |
| generative AI inputs and outputs | sent | `genAI` |
| local variables in stack frames | sent | `stackFrameVariables` |
| Deno source lines in stack traces | sent with `--allow-read` | omit the flag |
| Deno hostname and OS version | sent with `--allow-sys` | omit the flag |

The built-in denylist always applies, including to keys in an allow list. It matches partially and case-insensitively on `auth`, `token`, `secret`, `password`, `key`, `session` and others (Bun options page). Extend it with `forwarded`, `-ip`, `remote-`, `via`, `-user` to filter IP-like headers.

## Verify recipe

Bun:
1. In the entry the app runs under `--preload`, add a temporary route (or, for a script, a line in its main function) that calls `Sentry.captureException` with `new Error("sentry-verify-<date>")`. The guide's Issues check does this inside a setTimeout callback; the Tracing check wraps the call in `Sentry.startSpan`.
2. Start the app with its production command (same `--preload`), trigger the route once.
3. In Issues, expect one event whose message carries the marker. Traced runs show the span name you passed to `Sentry.startSpan`.
4. Remove the route or line. `grep -rn "sentry-verify" <repo>` must return nothing.

Deno: the same steps in the Deno entry file, started with the permissions from the guide: `--allow-net` (host), `--allow-env`, `--allow-read`, `--allow-sys`. Expect the event, with source lines in the stack trace only when `--allow-read` is granted. Remove the marker, then grep as above.

## Gotchas

- Deno data loss: the research note says a missing `--allow-read` or `--allow-sys` makes the SDK "silently drop data". The Deno guide says the SDK still sends events, without source lines and host/OS fields, and prints no warning. Follow the guide.
- Deno missing `--allow-env`: the app stops at start with `NotCapable: Requires env access`. A missing `--allow-net` host is named in Deno's error (Deno guide, "Grant Permissions").
- Deno dependency spans: the hook reads dependencies from a local node_modules directory, not Deno's global npm cache, so `nodeModulesDir` must be `"auto"` in `deno.json`.
- Bun dependency spans: `--preload` alone covers `Bun.serve`, `node:http` and `fetch`. Database, AI SDK and framework spans need `sentryBunPlugin` in a `Bun.build` output run with `--preload`.
- Bun `environment`: the options table gives default `production`; the prose says "development or production depending on whether the application is packaged". Set it explicitly.
- Application Metrics is on by default on both guides; no enable flag is documented.

## Sources
- https://docs.sentry.io/platforms/javascript/guides/bun.md
- https://docs.sentry.io/platforms/javascript/guides/deno.md
- https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/deno/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/bun/sourcemaps/uploading.md
- https://docs.sentry.io/platforms/javascript/guides/deno/sourcemaps/uploading.md

## Identifiers
```identifiers
Sentry.init | https://docs.sentry.io/platforms/javascript/guides/bun.md
Sentry.captureException | https://docs.sentry.io/platforms/javascript/guides/bun.md
Sentry.startSpan | https://docs.sentry.io/platforms/javascript/guides/bun.md
Sentry.logger.info | https://docs.sentry.io/platforms/javascript/guides/bun.md
Sentry.logger.warn | https://docs.sentry.io/platforms/javascript/guides/bun.md
Sentry.logger.error | https://docs.sentry.io/platforms/javascript/guides/bun.md
Sentry.metrics.count | https://docs.sentry.io/platforms/javascript/guides/bun.md
Sentry.metrics.gauge | https://docs.sentry.io/platforms/javascript/guides/bun.md
Sentry.metrics.distribution | https://docs.sentry.io/platforms/javascript/guides/bun.md
sentryBunPlugin | https://docs.sentry.io/platforms/javascript/guides/bun.md
Bun.build | https://docs.sentry.io/platforms/javascript/guides/bun.md
Bun.serve | https://docs.sentry.io/platforms/javascript/guides/bun.md
--preload | https://docs.sentry.io/platforms/javascript/guides/bun.md
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/bun.md
@sentry/bun | https://docs.sentry.io/platforms/javascript/guides/bun.md
@sentry/bun/plugin | https://docs.sentry.io/platforms/javascript/guides/bun.md
@sentry/deno | https://docs.sentry.io/platforms/javascript/guides/deno.md
nodeModulesDir | https://docs.sentry.io/platforms/javascript/guides/deno.md
--allow-net | https://docs.sentry.io/platforms/javascript/guides/deno.md
--allow-env | https://docs.sentry.io/platforms/javascript/guides/deno.md
--allow-read | https://docs.sentry.io/platforms/javascript/guides/deno.md
--allow-sys | https://docs.sentry.io/platforms/javascript/guides/deno.md
dataCollection | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
sendDefaultPii | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
userInfo | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
httpHeaders | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
cookies | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
httpBodies | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
urlQueryParams | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
graphQL | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
genAI | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
stackFrameVariables | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
release | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
environment | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/javascript/guides/bun/configuration/options.md
```

## Unconfirmed
- `@sentry/deno` major 11: the research note says v11; the Deno guide states beta and Deno 2.8.3 or later, no major. Not stated on the pages fetched.
- `@sentry/bun` major: not stated on the Bun guide; the options page ties "version 11" only to the `dataCollection` default rule.
- Profiling, Replay, Crons, Feedback, Feature flags on Bun and Deno: not in either guide's install feature list. The Bun Topics list was cut off after "MCP Monitoring" and not read further.
- Whether `sentryBunPlugin` uploads source maps: the guide describes it only for dependency spans.
- Source map CI upload step for Bun and Deno (`sentry-cli` flags): the uploading pages were read only as indexes.
- Deno `release` and `environment` behaviour: only the Bun options page was read; the Deno options page was read for its key list only.
