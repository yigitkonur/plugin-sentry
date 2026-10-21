# React Native and Expo (module: platforms/react-native)

Serves framework ids `react-native` and `expo`; `cordova` falls back here (no Cordova page was fetched for this module). Expo SDK 50 or newer is required by `@sentry/react-native`. SDK-version statements below name the version the page gives.

## Detect

| Signal | Where | Means |
|---|---|---|
| `expo` dependency | package.json | framework `expo` (engine priority 91); outranks bare `react-native` (90) and React (60) |
| `react-native` dependency | package.json | framework `react-native`; wizard id `reactNative` |
| `@sentry/react-native` | package.json and lockfile (`yarn.lock` in the fixture) | SDK installed; the lockfile gives the resolved version |
| `@sentry/react-native/expo` in `plugins`, or `withSentry(` | app.json, app.config.js / app.config.ts | Expo config plugin: native build hooks and uploads |
| `getSentryExpoConfig(` or `@sentry/react-native/metro` | metro.config.js | Metro serializer that assigns unique Debug IDs |
| `Sentry.init(` | App.tsx, or the root layout (`app/_layout.tsx` with expo-router) | the init site; a second init site is a finding |
| `ios/sentry.properties`, `android/sentry.properties`, `.env.local` | native projects, repo root | build credentials the wizard writes; a committed token is a finding |
| `sentry-expo`, `react-native-sentry` | package.json, app.json | legacy and retired (see Gotchas) |

Fixture `evals/fixtures/expo` (expo 52.0.20, yarn): init in `App.tsx` with the DSN read from an env var, Expo plugin in `app.json`, role `mobile`, native subprojects `android` and `ios`. The engine's expected output is `evals/expected/expo.detect.json`.

Read, in this order: `App.tsx` or `app/_layout.tsx`, `app.json` or `app.config.*`, `metro.config.js`, then the `ios/` and `android/` build files.

## Install route

- Wizard (bare RN and Expo): `npx @sentry/wizard@latest -i reactNative`. Install page: it installs the package, adds the metro and Expo plugins, enables the Gradle step, wires the Xcode bundle and debug-symbol build phases, runs `pod install`, writes the credential files, and configures the init file. It is interactive, so the user runs it; the auditor reads the result.
- Expo, manual: `sentry-ctx docs page platforms/react-native/manual-setup/expo`, sections Prerequisites, Initialize the SDK, Add the Sentry Expo Plugin, Add Sentry Metro Plugin, Verify Setup.
- Bare React Native, manual: `sentry-ctx docs page platforms/react-native/manual-setup/manual-setup` (linked from the sourcemaps page; not fetched for this module).
- Expo SDK 49 or older: legacy `sentry-expo`; migrate per the Expo prerequisites link.

## Init placement

| Setup | Where Sentry starts | Note |
|---|---|---|
| Expo Router | `Sentry.init(` in the root layout module (docs example imports `Stack` from `expo-router` in the same file) | initialize as early as possible; no ref wiring needed for the router integration |
| Bare RN, or Expo without a router | the App entry (App.tsx) | install page names `layout.tsx` / `App.tsx` |
| Root component | `export default Sentry.wrap(App);` | touch tracking and automatic tracing; not needed without a single parent App component |
| Metro | `getSentryExpoConfig(` in place of the Expo default config call | unique Debug IDs for bundles and source maps |
| Native layer | default `autoInitializeNativeSdk` `true` | when set `false`, JS `Sentry.init()` is still required |

## Options by SDK major

v(N-1) is the older behaviour the fetched pages describe; "—" means no difference is stated. v(N) is the current docs state: minimum version or default as the page gives it.

| option | v(N-1) | v(N) | note |
|---|---|---|---|
| `tracesSampleRate` | — | docs example `1.0`; tune for production | gate for tracing and for profiling |
| `profilesSampleRate` | below 5.32.0 | 5.32.0+ | Hermes JS profiling; relative to `tracesSampleRate` |
| `hermesProfilingIntegration` | — | `platformProfilers` option | native profilers on by default |
| `enableLogs` | below 7.0.0 | 7.0.0+ | `enableLogs: true` in `Sentry.init` |
| `mobileReplayIntegration` | below 6.5.0 | 6.5.0+ | masking on by default; see Privacy |
| `replaysOnErrorSampleRate`, `replaysSessionSampleRate` | — | top level of `Sentry.init` in docs examples (1.0 and 0.1) | error and session sampling |
| `sendDefaultPii` | — | docs example `true` | adds IP, cookies, user; default not stated on fetched pages |
| `enableNative` | — | default `true` | `false` disables all native crash and error handling |
| `autoInitializeNativeSdk` | — | default `true` | `false` means the native SDK is initialized by hand |
| `enableNativeCrashHandling` | — | default `true` | `false` means no hard-crash events from native code |
| `SENTRY_RELEASE` (env) | — | read by default for `release` | see Release and artifacts |

## Product support matrix

| product | supported | notes |
|---|---|---|
| errors | yes | `Sentry.init` with `dsn`; native crash check is `Sentry.nativeCrash()` |
| tracing | yes | `tracesSampleRate`; `Sentry.wrap` adds touch and automatic tracing; Expo Router has its own tracing page |
| profiling | yes, SDK 5.32.0+ | needs tracing on; JS profiles on Hermes (iOS, Android); native profilers on by default (Swift/ObjC, Kotlin/Java); not on tvOS or visionOS. Research matrix marks it beta; fetched sections show no beta banner |
| replay | yes, SDK 6.5.0+ | `mobileReplayIntegration`; masks all text, images and webviews by default; native-first init needs 6.15.1+ |
| logs | yes, SDK 7.0.0+ | `enableLogs: true`; logs page has a "Missing Logs for Crashes" troubleshooting section |
| metrics | yes | Features list links a metrics page; minimum version not fetched |
| crons | no | not in the Features list and no crons page; research matrix shows no page |
| feedback | yes | User Feedback page linked from the Features list |
| ai | unconfirmed | no React Native AI page fetched; research notes say the page mirrors Node |
| flags | unconfirmed | research marks beta (generic); no React Native page fetched |
| debug files | yes | wizard wires the Xcode debug-symbol phase and the Gradle step; see Release and artifacts |

## Release and artifacts

- Release string: the SDK reads `SENTRY_RELEASE` by default (options page, `release`). Pin it explicitly so uploads and deploys use one value. Auditor check: the release on the source-map or symbol upload equals the release the app sends.
- Expo: the `@sentry/react-native/expo` plugin uploads JS source maps and native symbols during local and EAS native builds. `SENTRY_AUTH_TOKEN` belongs in `.env.local` for local builds and in an EAS secret for EAS builds, because EAS cannot read the local file.
- Bare RN (wizard): patches the Xcode bundle-and-upload phase, the Xcode "Upload Debug Symbols to Sentry" phase, and the Gradle step. Check both iOS and Android were patched.
- Engines: the sourcemaps page says the wizard handles JavaScript Core (including RAM bundle) and Hermes.
- Android native: when the disable switch is used, `autoUploadProguardMapping` and `uploadNativeSymbols` are set from `shouldSentryAutoUpload()` in the `sentry {}` block (sourcemaps page).
- Disable switches: env `SENTRY_DISABLE_AUTO_UPLOAD`; Expo plugin option `disableAutoUpload`, which is baked in at `expo prebuild` and works from the Xcode GUI.
- Debug builds: no upload; Metro symbolicates. A Release build is the only valid test.
- EAS Update (OTA) source maps: Expo upload page `platforms/react-native/guides/expo/sourcemaps/uploading/expo`; the exact commands are in Unconfirmed.

## Privacy

| Data | Default (fetched pages) | Control |
|---|---|---|
| Replay content | all text, images and webviews masked | `maskAllText`, `maskAllImages`, `maskAllVectors`; set `false` only when the app has no PII |
| IP, cookies, user (`sendDefaultPii`) | default not stated; docs example sets `true` | `sendDefaultPii` |
| Screenshot, view hierarchy | options exist; defaults not fetched | `attachScreenshot`, `attachViewHierarchy` |
| Auth token | must not be committed | `.env.local` locally; EAS secret for EAS builds |

Data-collected reference (linked from the init comment, not fetched): `platforms/react-native/data-management/data-collected`.

## Verify recipe

1. Build a Release build. Expo verify step says to build Release; dev builds prove neither upload nor symbolication.
2. Add one temporary trigger on the real code path: a handler on a screen the app renders, or a temporary route file under `app/` for Expo Router, that calls `Sentry.captureException(new Error("sentry-verify <unique-marker>"))`.
3. Native path, separately: a temporary `Sentry.nativeCrash()` call (docs Verify step). It stops the process; use it only to test native crash capture.
4. In Sentry, find the marker and check the pinned release. OTA builds also carry `expo.updates.update_id`, `expo.updates.channel` and `expo.updates.runtime_version`.
5. Remove both triggers, then `grep -rn "sentry-verify" <app source dirs>` must print nothing before commit.

## Gotchas

- Expo 49 or older: `sentry-expo` is deprecated; migrate to `@sentry/react-native` (Expo prerequisites). `sentry-expo` in package.json is a finding.
- Expo Updates tags are `expo.updates.update_id`, `expo.updates.channel`, `expo.updates.runtime_version` (Expo Updates page). The research notes list different singular names; the docs win.
- Expo Go: the Expo Router example gates `enableTimeToInitialDisplay` and `enableNativeFramesTracking` with `isRunningInExpoGo()`. Copy the gate; ungated values are a finding.
- Profiles: `profilesSampleRate` is relative to `tracesSampleRate`, so tracing off means no profiles. JS profiles need Hermes.
- Replay masking: `maskAllText: false` (or the other two) removes the default protection; the docs allow it only with no sensitive data.
- Native init split: `autoInitializeNativeSdk: false` means JS `Sentry.init()` is still required, `dsn` must be set on both sides, and options are not merged.
- Replay with manual native init before JS: replay page asks for SDK 6.15.1+ (GH-4853 linked there).
- Metro: without `getSentryExpoConfig(` the Debug ID serializer is missing (docs: it ensures unique Debug IDs).
- Observed, not a Sentry docs page (Expo CLI 58.0.16 `expo export --help`, 2026-10-20): `expo export` emits no source maps by default (`--source-maps` defaults to false) and writes Hermes bytecode. `npx expo export --platform ios --source-maps true --no-bytecode` is a linkage check only: with the Sentry Metro config the one `.js.map` had the same Debug ID as the bundle's `sentry-dbid` marker, and `sentry sourcemap resolve dist` found 1 pair. A `--no-bytecode` map describes plain JS, not the Hermes bytecode a Release build ships, so do not upload it for a Hermes app.
- Observed, not a Sentry docs page (Expo 58 iOS Release on the simulator, `@sentry/react-native` 8.28.0, `sentry` 0.47.0, 2026-10-21): a Hermes bundle cannot be uploaded with the v4 `sentry sourcemap upload`. Hermes frames are bytecode offsets on line 1. The bytecode file gave `js_no_source`, and the placeholder v4 rewrites gave `js_invalid_sourcemap_location`. The SDK's own path works differently: the Xcode/Gradle build phase, or `@sentry/expo-upload-sourcemaps` (installed with the SDK) for an export, runs sentry-cli 3 `sourcemaps upload --debug-id-reference`, which uploads an empty placeholder carrying the map's Debug ID. Keep that path, give it `SENTRY_AUTH_TOKEN`, and never set `SENTRY_DISABLE_AUTO_UPLOAD` on a Release build. In that build, with the upload disabled, the composed Hermes map (`SOURCEMAP_FILE`) had no `debugId`.
- Replay and Expo Router docs call Expo Go unsupported for some features; follow the `isRunningInExpoGo()` gate, not a memory of it.
- Research notes disagree with the pages on the Expo Updates tag names (docs win). Other research claims (masking components, OTA upload commands, `eas secret`) are not confirmed on any fetched page; see Unconfirmed.

## Sources
- https://docs.sentry.io/platforms/react-native/ (Install, Configure, Wrap Your App, Verify, Features)
- https://docs.sentry.io/platforms/react-native/manual-setup/expo/
- https://docs.sentry.io/platforms/react-native/configuration/options/
- https://docs.sentry.io/platforms/react-native/sourcemaps/
- https://docs.sentry.io/platforms/react-native/session-replay/
- https://docs.sentry.io/platforms/react-native/profiling/
- https://docs.sentry.io/platforms/react-native/logs/
- https://docs.sentry.io/platforms/react-native/guides/expo/tracing/instrumentation/expo-router/
- https://docs.sentry.io/platforms/react-native/guides/expo/manual-setup/expo/expo-updates/
- https://docs.sentry.io/platforms/react-native/guides/expo/sourcemaps/uploading/expo/

## Identifiers

```identifiers
Sentry.init | https://docs.sentry.io/platforms/react-native/manual-setup/expo/
Sentry.wrap | https://docs.sentry.io/platforms/react-native/
Sentry.nativeCrash | https://docs.sentry.io/platforms/react-native/
Sentry.captureException | https://docs.sentry.io/platforms/react-native/manual-setup/expo/
reactNative | https://docs.sentry.io/platforms/react-native/
withSentry | https://docs.sentry.io/platforms/react-native/manual-setup/expo/
getSentryExpoConfig | https://docs.sentry.io/platforms/react-native/manual-setup/expo/
getDefaultConfig | https://docs.sentry.io/platforms/react-native/manual-setup/expo/
mobileReplayIntegration | https://docs.sentry.io/platforms/react-native/session-replay/
maskAllText | https://docs.sentry.io/platforms/react-native/session-replay/
maskAllImages | https://docs.sentry.io/platforms/react-native/session-replay/
maskAllVectors | https://docs.sentry.io/platforms/react-native/session-replay/
expoRouterIntegration | https://docs.sentry.io/platforms/react-native/guides/expo/tracing/instrumentation/expo-router/
enableTimeToInitialDisplay | https://docs.sentry.io/platforms/react-native/guides/expo/tracing/instrumentation/expo-router/
enableNativeFramesTracking | https://docs.sentry.io/platforms/react-native/guides/expo/tracing/instrumentation/expo-router/
isRunningInExpoGo | https://docs.sentry.io/platforms/react-native/guides/expo/tracing/instrumentation/expo-router/
tracesSampleRate | https://docs.sentry.io/platforms/react-native/configuration/options/
profilesSampleRate | https://docs.sentry.io/platforms/react-native/profiling/
hermesProfilingIntegration | https://docs.sentry.io/platforms/react-native/profiling/
platformProfilers | https://docs.sentry.io/platforms/react-native/profiling/
enableLogs | https://docs.sentry.io/platforms/react-native/logs/
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/react-native/manual-setup/expo/
replaysSessionSampleRate | https://docs.sentry.io/platforms/react-native/manual-setup/expo/
sendDefaultPii | https://docs.sentry.io/platforms/react-native/configuration/options/
enableNative | https://docs.sentry.io/platforms/react-native/configuration/options/
autoInitializeNativeSdk | https://docs.sentry.io/platforms/react-native/configuration/options/
enableNativeCrashHandling | https://docs.sentry.io/platforms/react-native/configuration/options/
attachScreenshot | https://docs.sentry.io/platforms/react-native/configuration/options/
attachViewHierarchy | https://docs.sentry.io/platforms/react-native/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/react-native/configuration/options/
SENTRY_DISABLE_AUTO_UPLOAD | https://docs.sentry.io/platforms/react-native/sourcemaps/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/react-native/manual-setup/expo/
disableAutoUpload | https://docs.sentry.io/platforms/react-native/sourcemaps/
autoUploadProguardMapping | https://docs.sentry.io/platforms/react-native/sourcemaps/
uploadNativeSymbols | https://docs.sentry.io/platforms/react-native/sourcemaps/
shouldSentryAutoUpload | https://docs.sentry.io/platforms/react-native/sourcemaps/
expo.updates.update_id | https://docs.sentry.io/platforms/react-native/guides/expo/manual-setup/expo/expo-updates/
expo.updates.channel | https://docs.sentry.io/platforms/react-native/guides/expo/manual-setup/expo/expo-updates/
expo.updates.runtime_version | https://docs.sentry.io/platforms/react-native/guides/expo/manual-setup/expo/expo-updates/
```

## Unconfirmed
- `Sentry.Mask`, `Sentry.Unmask`, `maskedViewClasses`: research notes say these replace `sentry-mask` / `sentry-unmask` props; the privacy page was not fetched on 2026-10-20.
- `@sentry/expo-upload-sourcemaps`, `expo export --dump-sourcemap`: EAS Update (OTA) upload route from research notes; not in fetched text on 2026-10-20.
- `eas secret`: research notes say Expo docs moved to `eas env`; the Sentry page still says "EAS secret". Not confirmed on 2026-10-20.
- Auto-derived release string (native app id, version, build): research only; the options page gives only the `SENTRY_RELEASE` default.
- Metrics minimum SDK version (research: 7.8) and latest SDK version (research: 8.31.0): not on a fetched page on 2026-10-20.
- Cordova: no page fetched on 2026-10-20.
