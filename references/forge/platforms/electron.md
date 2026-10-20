# Electron (module: platforms/electron)

## Detect

| Signal | Where | Means |
|---|---|---|
| `electron` dependency (framework id `electron`, role `desktop`) | package.json dependencies or devDependencies | Electron app; the lockfile gives the real version (the engine fixture reports 33.2.1) |
| `@sentry/electron` dependency | package.json; lockfile | SDK installed; read its major. The rows below describe v8, the major the options page calls current |
| imports of `@sentry/electron/main`, `/renderer`, `/utility` | main entry (package.json `main`), renderer scripts, preload script, utility-process files | which process each file starts Sentry in |
| init call (`Sentry.init`) | those files | init sites. Fixture: `src/main.js` line 5 has a DSN literal; `src/renderer.js` inits with empty options |
| `contextIsolation` and a `preload` entry in the window's webPreferences | `src/main.js` (fixture sets `preload`, not `contextIsolation`) | decides whether the preload script needs its own init |
| `forge.config.js` (Electron Forge packaging) | project root | not a Sentry signal; check the build config for source-map output |

## Install route

- Manual route (the one that applies to an existing app): `npm install @sentry/electron --save` (yarn and pnpm variants exist). Fetch `sentry-ctx docs page platforms/javascript/guides/electron`, sections "Install the Sentry SDK" and "Configure the Main Process".
- Source maps: `npx @sentry/wizard@latest -i sourcemaps`. The wizard configures the build tool and CI; the user runs it interactively, then audit the result. Fetch `sentry-ctx docs page platforms/javascript/guides/electron/sourcemaps`.
- The guide documents the manual install; the wizard is documented for source maps only (the `electron` wizard value is in Unconfirmed).

## Init placement

| Process | Import | Where | Note |
|---|---|---|---|
| main | `@sentry/electron/main` | as early as possible in the main entry | owns `dsn`, `release`, `environment`, `ipcMode`, and `dataCollection` `userInfo` |
| renderer | `@sentry/electron/renderer` | as early as possible in each renderer | `dsn`, `release` and `environment` passed here have no effect; renderer events go through main |
| utility process | `@sentry/electron/utility` | every utility process | guide: initialise in each utility process |
| preload | `@sentry/electron/renderer` | preload script, only when `contextIsolation` is `true` | without it, errors in the preload context are not captured automatically |

- `app.setPath("userData", ...)` must run before init. The userData path caches scope and events between restarts.
- Fixture: the only main init is `src/main.js` line 5, before the window is created. The renderer init with empty options matches the docs (no DSN in the renderer). `src/preload.js` has no init; that is a finding only if the window runs with `contextIsolation` on (the fixture does not set it, and no fetched page states the default).

## Options by SDK major

| option | v7 | v8 (current) | note |
|---|---|---|---|
| `dataCollection` | defaults apply only when this option is set (since 7.14.0) | defaults always apply | categories in Privacy |
| `sendDefaultPii` | deprecated; controls data collection when `dataCollection` is unset | not on the fetched page | use `dataCollection` |
| `ipcMode` | not on the fetched page | default `IPCMode.Both`; main process only | other values: `IPCMode.Classic`, `IPCMode.Protocol` |
| `release` | not on the fetched page | default `appName@version`, read from the Electron app module; main process only | renderer value is ignored |
| `environment` | not on the fetched page | no default stated | set per build |
| `tracesSampleRate` | not on the fetched page | docs example `1.0`; page says adjust in production | set in main and renderer |
| `replaysSessionSampleRate`, `replaysOnErrorSampleRate` | not on the fetched page | docs example `0.1` and `1.0` | renderer only |
| `profileSessionSampleRate`, `profileLifecycle` | not on the fetched page | listed on the Electron options page | no Electron profiling step in the guide |

## Product support matrix

| product | supported | notes |
|---|---|---|
| errors | yes | main and renderer; preload needs its own init when `contextIsolation` is on |
| replay | yes | `replayIntegration` in the renderer init only (guide, renderer section) |
| tracing | yes | `startupTracingIntegration` in main; `browserTracingIntegration` in renderer |
| profiling | unconfirmed | options listed on the Electron options page; no guide step (see Unconfirmed) |
| logs | yes | Sentry logger calls in the guide's Verify step; `beforeSendLog` option |
| metrics | yes | "Application Metrics" step in the guide's Verify section; `beforeSendMetric` option |
| crons | unconfirmed | no Electron crons step in the guide; the research platform matrix has no Electron row |
| feedback | yes | `feedbackIntegration` in the renderer init |
| ai | unconfirmed | `genAI` data categories exist; no Electron AI integration step |
| flags | unconfirmed | no page fetched |
| debug files | partial | source maps: yes (wizard or bundler plugins, production builds only). Native symbols and minidumps: unconfirmed |

The statuses come from the guide and options page. The research platform matrix (06-product-map, section 3) has no Electron row.

## Release and artifacts

- Release string: default `appName@version`, built by the SDK from the Electron `app` module in the main process. A `release` set in renderer code does nothing.
- Source maps (sourcemaps page): generated and uploaded only in production builds. Linked by Debug IDs injected into the build output by default; legacy methods exist. Routes: the wizard (`npx @sentry/wizard@latest -i sourcemaps`, also configures CI); bundler plugins for webpack, Rollup, Vite and esbuild; manual guides for tsc, UglifyJS and SystemJS. GitHub Actions release automation is linked from the same page (not fetched).
- Right looks like: the upload runs in the production build pipeline, and the release the upload uses is the release the app reports at runtime. The match rule is not stated on a fetched page (see Unconfirmed).

## Privacy

Default in v8 (options page, `dataCollection`): the SDK collects user identity (`userInfo` covers id, email, username, IP), HTTP headers, request and response bodies, URL query params, cookies, stack-frame locals, GraphQL, gen AI content and database query data. A built-in denylist (`auth`, `token`, `password`, and similar) replaces matching values with `[Filtered]` and also applies to allow lists.

| Data | Control | Note |
|---|---|---|
| user id, email, username, IP | `dataCollection` `userInfo` (set in main) | the main value controls IP inference for all processes; data set with `setUser` is always sent |
| request and response bodies | `httpBodies` (`[]` disables) | |
| headers, cookies, query params | `httpHeaders`, `cookies`, `urlQueryParams` | each accepts true, false, `{ allow }` or `{ deny }` |
| local variables | `stackFrameVariables` | |
| source context lines | `frameContextLines` (default 5) | |

Paths and OS usernames in events are not stated on a fetched page (see Unconfirmed).

## Verify recipe

Emit one marked event from the app's real code path, then remove the trigger.

1. Main: in the window-creation function that `app.whenReady()` calls in `src/main.js`, add a throw after the window is created, with the message `sentry-audit-probe main`.
2. Renderer: add a temporary button to `index.html` and a click listener in the renderer script that throws an Error with the message `sentry-audit-probe renderer`.
3. Start the app with the project's own start script. Use a production build if the check includes source maps.
4. Expect two issues in the project, each with the probe text in the message and release `appName@version`. With source maps, frames resolve to source in both processes.
5. Remove the throw, the button and the listener. Confirm no probe text is left in the tree.

## Gotchas

| Symptom | Cause | Fix (source) |
|---|---|---|
| renderer events show the wrong release or environment, or the renderer has no DSN | `dsn`, `release`, `environment` set in renderer init | set them in main; renderer events go through main (guide, renderer section) |
| errors from the preload script are missing | `contextIsolation` on and preload not initialised | init `@sentry/electron/renderer` in the preload (guide, "Capturing errors in the preload context") |
| events or scope lost or cached in the wrong place across restarts | `app.setPath("userData", ...)` called after init | set the path before init (guide) |
| minified frames in production | no source maps uploaded, or the build is not a production build | sourcemaps page |
| renderer events not arriving | `ipcMode` controls how renderer events reach main; default `IPCMode.Both` configures Electron IPC and a custom protocol with fetch | check main's `ipcMode` (options page) |
| privacy settings behave differently across majors | v7 applies `dataCollection` defaults only when set; v8 always applies them | read the installed major from the lockfile (options page) |
| research note says sentry-cli symbolicates Electron minidumps | no fetched page confirms this | follow the docs; treat as unverified (see Unconfirmed) |

## Sources
- https://docs.sentry.io/platforms/javascript/guides/electron.md
- https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
- https://docs.sentry.io/platforms/javascript/guides/electron/sourcemaps.md
- https://docs.sentry.io/platforms/javascript/guides/electron/sourcemaps/uploading.md (heading listing only)
- https://docs.sentry.io/platforms/javascript/guides/electron/data-management.md (heading listing only)

## Identifiers
```identifiers
@sentry/electron | https://docs.sentry.io/platforms/javascript/guides/electron.md
@sentry/electron/main | https://docs.sentry.io/platforms/javascript/guides/electron.md
@sentry/electron/renderer | https://docs.sentry.io/platforms/javascript/guides/electron.md
@sentry/electron/utility | https://docs.sentry.io/platforms/javascript/guides/electron.md
npm install @sentry/electron --save | https://docs.sentry.io/platforms/javascript/guides/electron.md
npx @sentry/wizard@latest -i sourcemaps | https://docs.sentry.io/platforms/javascript/guides/electron.md
startupTracingIntegration | https://docs.sentry.io/platforms/javascript/guides/electron.md
browserTracingIntegration | https://docs.sentry.io/platforms/javascript/guides/electron.md
replayIntegration | https://docs.sentry.io/platforms/javascript/guides/electron.md
feedbackIntegration | https://docs.sentry.io/platforms/javascript/guides/electron.md
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/electron.md
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/electron.md
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/guides/electron.md
contextIsolation | https://docs.sentry.io/platforms/javascript/guides/electron.md
userData | https://docs.sentry.io/platforms/javascript/guides/electron.md
app.setPath | https://docs.sentry.io/platforms/javascript/guides/electron.md
dataCollection | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
userInfo | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
httpBodies | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
httpHeaders | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
urlQueryParams | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
stackFrameVariables | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
frameContextLines | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
genAI | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
sendDefaultPii | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
setUser | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
ipcMode | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
IPCMode.Both | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
IPCMode.Classic | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
IPCMode.Protocol | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
appName@version | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
profileLifecycle | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
beforeSendLog | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
beforeSendMetric | https://docs.sentry.io/platforms/javascript/guides/electron/configuration/options.md
```

## Unconfirmed
- `webPreferences`: no fetched page states the `contextIsolation` default or the sandbox default for Electron windows; checked 2026-10-20.
- `native-crash-handling`: the guide paths `configuration/native-crash-handling`, `minidumps` and `native-crashes` all returned "Page Not Found" on 2026-10-20. Electron minidump and crash-reporter behaviour is unverified.
- sandboxed renderers: no fetched page covers them.
- `electron` wizard value (`npx @sentry/wizard@latest -i electron`): from data/detect/frameworks.json and the research note only.
- `@sentry/electron` 8.3.0 and an Electron 35+ minimum: research note only.
- `environment` default: not stated on the fetched pages.
- release and source-map match rule for Electron: the bundler pages were not fetched.
- paths and OS usernames in events: not stated on a fetched page; the data-management listing has no body text.
- Electron profiling (UI profiling from Electron 7.4 in the research note): not on a fetched page.
- crons, flags and AI integration for Electron: no page fetched.
- native debug files and symbol upload: not on a fetched page; the research note says sentry-cli symbolicates minidumps.
