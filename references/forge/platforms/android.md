# Android (module: platforms/android)

## Detect
Framework id `android` (role mobile, eco jvm, wizard `android`). Dependency signals: the Android application or library Gradle plugin, `androidx.*`, `com.google.android.*`. Read these files:

| File | Signal | Check |
|---|---|---|
| app/build.gradle (or the .kts variant) | `com.android.application`; `io.sentry.android.gradle` plugin; `sentry {}` block | plugin version against the AGP version; `autoUploadProguardMapping`, `includeSourceContext`, `uploadNativeSymbols` |
| app/src/main/AndroidManifest.xml | `io.sentry.dsn` meta-data; other `io.sentry.*` keys; `android:name` on the application element | DSN present once; keys match the Options table; the Application class it names |
| The Application subclass named in the manifest | `SentryAndroid.init` call | called once, in `onCreate`, not from an Activity |
| sentry.properties (app module or root) | `auth.token` | not tracked by git |
| Android library modules (no application plugin) | `com.android.library` | no Sentry init here; init belongs to the app module (plugin convention, not a Sentry docs rule) |

## Install route
- **Wizard** (user runs it in a terminal; it needs a TTY): `npx @sentry/wizard@latest -i android`. The page also lists brew and per-OS binaries. The wizard updates the Gradle file and `AndroidManifest.xml`, creates `sentry.properties` with an auth token and adds it to `.gitignore`, and adds an example error to the main Activity. Audit that output as first-party code; the example error is test code to remove.
- **Manual**: docs path `platforms/android/configuration/gradle`. Add the plugin `io.sentry.android.gradle` at the version the live page shows (6.24.0 when fetched). Plugin 3.0.0 and later need AGP 7.0.0 or newer; older AGP uses the 2.x line of the plugin.
- **SDK dependency**: since plugin 3.1.0 the plugin adds `io.sentry:sentry-android` itself, on by default. Declare it yourself only to pin a version (docs example 8.61.0, path `platforms/android/manual-setup`).
- Manifest keys: docs path `platforms/android`, section Configure. Manual init: `platforms/android/manual-setup`.

## Init placement
- **Manifest path (default)**: the `<meta-data>` keys in the manifest initialise the SDK at app start. No code change is needed for DSN and manifest-level options.
- **Manual path**: set `io.sentry.auto-init` to `false` on the application element, then call `SentryAndroid.init` once from the Application subclass `onCreate`. The docs say to call it "as soon as the application is created" and to avoid calling it from an Activity lifecycle method.
- Right: one init path, in the Application class. The manifest keys still load; the init callback only adds what the manifest cannot express.

## Options by SDK major
The fetched pages describe the current 8.x SDK. `—` means the fetched pages do not state it, not that it is absent.

| option | v7.x | v8.x (current) | note |
|---|---|---|---|
| `io.sentry.dsn` (manifest) | — | required | the only key the docs mark Required |
| `io.sentry.auto-init` (manifest) | — | `false` only for manual init | see Init placement |
| `io.sentry.data-collection.user-info` (manifest) | — | docs sample sets `false` | sets `userInfo` in `dataCollection` |
| `dataCollection` | absent before 8.58.0 | since 8.58.0 | replaces `sendDefaultPii`; defaults in Privacy |
| `sendDefaultPii` | — | ignored once any `dataCollection` field is configured | migration note on the options page |
| `attachScreenshot` | since 6.0.0 | default `false` | screenshot masking is also off by default |
| `attachViewHierarchy` | — | default `false` | attaches the whole view tree as JSON |
| `release` / `io.sentry.release` | — | unset = `packageName@versionName+versionCode` | see Release and artifacts |
| `environment` | — | freeform string; no default stated | separate staging from production |
| `io.sentry.traces.sample-rate` (manifest) | — | sample value 1.0, commented "adjust in production" | a sample, not a default |
| `profileLifecycle` / `io.sentry.traces.profiling.lifecycle` | since 8.7.0 | default `manual`; `trace` follows sampled traces | `manual` needs explicit start and stop calls |
| `profileSessionSampleRate` / `io.sentry.traces.profiling.session-sample-rate` | — | sample value 1.0, evaluated once per session | UI profiling |
| `enableNdkAppHangTracking` | since 8.48.0 | default `false`; experimental | NDK hang detection; separate from ANR |
| `io.sentry.logs.enabled` (manifest) | — | sample value `true` | logs bill per GB (quota module) |

## Product support matrix
| product | supported | notes |
|---|---|---|
| errors | yes | ANR detection watches the UI thread; `attachScreenshot` and `attachViewHierarchy` add attachments, both off by default; native (NDK) frames need native symbols (Release section) |
| tracing | yes | enabled by `io.sentry.traces.sample-rate` (manifest) |
| profiling | yes | UI profiling: `profileSessionSampleRate`, `profileLifecycle`. Transaction-based profiling status: see Unconfirmed |
| replay | yes | the replay page states SDK 7.12.0 or newer; masks text, images and webviews by default; manifest keys `io.sentry.session-replay.session-sample-rate` and `io.sentry.session-replay.on-error-sample-rate` |
| logs | yes | `io.sentry.logs.enabled` (manifest) on the platform page |
| metrics | unconfirmed | no Android metrics page fetched |
| crons | no | the plan's platform matrix lists no Android crons page (not a Sentry statement) |
| feedback | unconfirmed | no Android feedback page fetched |
| ai | unconfirmed | no Android AI page fetched; the plan matrix says manual instrumentation |
| flags | unconfirmed | no Android flags page fetched; the plan matrix says beta integration |
| debug files | yes | the Gradle plugin uploads ProGuard/R8 mappings and native symbols (Release and artifacts) |

## Release and artifacts
- **Release string**: set `io.sentry.release` in the manifest, or `options.setRelease` in the init callback. The options page says to set it explicitly so it stays in sync with deploy integrations and source-map uploads. Unset, the SDK builds `packageName`, `versionName` and `versionCode` into `packageName@versionName+versionCode` (docs example `my.project.name@2.3.12+1234`).
- **ProGuard/R8 mapping**: the plugin generates the mapping and a UUID the build reports, then uploads on the assemble task for the variant (docs example `assembleRelease`). Works for any variant with ProGuard/R8 enabled. `includeProguardMapping` and `autoUploadProguardMapping` both default to enabled; with auto-upload off, the plugin only dry-runs and the mapping goes up by hand.
- **Native symbols (NDK)**: `uploadNativeSymbols` defaults to disabled; `autoUploadNativeSymbols` defaults to enabled; `includeNativeSources` defaults to disabled and needs `uploadNativeSymbols`. Runs only for a non-debuggable build type.
- **Source context**: `includeSourceContext` (default disabled) uploads a JVM source bundle.
- **Credentials**: the docs prefer the `SENTRY_AUTH_TOKEN` environment variable, read into `authToken`. Alternatives: `org` and `projectName` in the `sentry {}` block, or `sentry.properties` with `defaults.org`, `defaults.project`, `auth.token`.
- **Other**: `dexguardEnabled` (default disabled, experimental) covers Guardsquare tooling. Size analysis belongs to the mobile builds product, not this module.
- **CI**: export `SENTRY_AUTH_TOKEN`, then run the release-variant build. A pipeline that never runs the release task uploads no mapping.

## Privacy
- **Defaults that leave the app** (`dataCollection` table): `userInfo` true (user identity and IP address); `cookies`, `httpHeaders.request`, `httpHeaders.response` and `urlQueryParams` in `DENY_LIST` (built-in terms such as auth, token, secret, password, key, session); `httpBodies` all body types; `graphql.document` and `graphql.variables` true; `filePaths` true. Full list: `platforms/android/data-management/data-collected`.
- **Control**: `io.sentry.data-collection.user-info` (manifest) and the `dataCollection` fields.
- **Migration trap**: once any `dataCollection` field is configured, `sendDefaultPii` is ignored and headers are sent by default. The legacy filter for `X-Forwarded-For`, `X-Real-IP` and `Remote-Addr` no longer applies. Add the terms forwarded, -ip, remote-, via and -user to the deny lists of `cookies`, `httpHeaders.request`, `httpHeaders.response` or `urlQueryParams`.
- **Screenshots**: `attachScreenshot` is off by default, and masking is off by default (unlike Session Replay). Set `io.sentry.screenshot.mask-all-text` and `io.sentry.screenshot.mask-all-images` to `true`. `setMaskAllImages` also masks WebView, VideoView, CameraX PreviewView, ExoPlayer and Media3 views.
- **View hierarchy**: `attachViewHierarchy` is off by default and sends the whole view tree as JSON. Its masking rules are not read (see Unconfirmed).
- **Session Replay**: masks text, images and webviews by default. `options.sessionReplay.maskAllText` set to false turns that off; the docs say not to do that for apps with sensitive data. `ScreenshotStrategyType.CANVAS` is experimental and ignores the masking options; `ScreenshotStrategyType.PIXEL_COPY` is the default.

## Verify recipe
1. The docs snippet (`Sentry.captureException` in an Activity) proves delivery only. It is the baseline, not the proof.
2. Temporarily add one line in the real code path the feature uses (the repository or view-model method behind a button the user taps), capturing a marked exception: `Sentry.captureException` with a marker such as sentry-verify-<random id>.
3. Run the debug build on a device or emulator and trigger that path once. In the Issues stream, find the marker and check `environment` and `release` against the expected value from Release and artifacts.
4. Remove the line, plus any wizard example error. Confirm nothing is left:

```bash
grep -rn "sentry-verify" app/src   # must print nothing
git diff --stat                    # no unintended edits
```

5. For mapping, one exception from a release build should show named frames, not obfuscated names. This only holds after the release build has uploaded the mapping. Mark UNVERIFIED unless the user confirms it in the UI.

## Gotchas
- **Init outside Application**: the docs say the SDK catches errors only after init, so an Activity-level init misses earlier crashes.
- **Tracked token file**: a committed `sentry.properties` with `auth.token` is a leaked credential. The wizard's `.gitignore` entry does not untrack a file already in git. Rotate the token and untrack the file.
- **Copied sample values**: the docs Configure block sets trace and profiling session rates to 1.0 and replay session rate to 0.1 (on-error 1.0). These are examples marked "adjust in production". A flat 1.0 trace rate in production is a quota issue (quota module).
- **Plugin and AGP pairing**: plugin 3.0.0 and later need AGP 7.0.0 or newer. A stale plugin pin is the common failure.
- **Upload only runs for the release task**: mapping upload runs on the assemble task; native symbols only for non-debuggable builds; `uploadNativeSymbols` is off by default.
- **Replay floor disagreement**: the replay page says SDK 7.12.0 or newer. A research note said 7.20. The page wins; the 7.20 figure is not on the page.
- **Error and ANR vs NDK hang**: `enableNdkAppHangTracking` is experimental, off by default, and separate from ANR detection. Do not count one as the other.
- **Wizard leftovers**: the example error added to the main Activity must be removed after verification.

## Sources
- https://docs.sentry.io/platforms/android/ (Install, Configure, Verify)
- https://docs.sentry.io/platforms/android/configuration/gradle/
- https://docs.sentry.io/platforms/android/configuration/options/
- https://docs.sentry.io/platforms/android/configuration/releases/
- https://docs.sentry.io/platforms/android/manual-setup/
- https://docs.sentry.io/platforms/android/enriching-events/screenshots/
- https://docs.sentry.io/platforms/android/session-replay/
- https://docs.sentry.io/platforms/android/data-management/data-collected/ (headings only)
- https://docs.sentry.io/platforms/android/enriching-events/viewhierarchy/ (headings only)

## Identifiers
```identifiers
io.sentry.dsn | https://docs.sentry.io/platforms/android/
io.sentry.data-collection.user-info | https://docs.sentry.io/platforms/android/
io.sentry.traces.sample-rate | https://docs.sentry.io/platforms/android/
io.sentry.traces.profiling.session-sample-rate | https://docs.sentry.io/platforms/android/
io.sentry.traces.profiling.lifecycle | https://docs.sentry.io/platforms/android/
io.sentry.logs.enabled | https://docs.sentry.io/platforms/android/
io.sentry.session-replay.session-sample-rate | https://docs.sentry.io/platforms/android/
io.sentry.session-replay.on-error-sample-rate | https://docs.sentry.io/platforms/android/
AndroidManifest.xml | https://docs.sentry.io/platforms/android/
Sentry.captureException | https://docs.sentry.io/platforms/android/
io.sentry.auto-init | https://docs.sentry.io/platforms/android/manual-setup/
SentryAndroid.init | https://docs.sentry.io/platforms/android/manual-setup/
onCreate | https://docs.sentry.io/platforms/android/manual-setup/
io.sentry:sentry-android | https://docs.sentry.io/platforms/android/manual-setup/
io.sentry.android.gradle | https://docs.sentry.io/platforms/android/configuration/gradle/
com.android.application | https://docs.sentry.io/platforms/android/configuration/gradle/
sentry.properties | https://docs.sentry.io/platforms/android/configuration/gradle/
auth.token | https://docs.sentry.io/platforms/android/configuration/gradle/
defaults.org | https://docs.sentry.io/platforms/android/configuration/gradle/
defaults.project | https://docs.sentry.io/platforms/android/configuration/gradle/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/android/configuration/gradle/
authToken | https://docs.sentry.io/platforms/android/configuration/gradle/
projectName | https://docs.sentry.io/platforms/android/configuration/gradle/
includeProguardMapping | https://docs.sentry.io/platforms/android/configuration/gradle/
autoUploadProguardMapping | https://docs.sentry.io/platforms/android/configuration/gradle/
uploadNativeSymbols | https://docs.sentry.io/platforms/android/configuration/gradle/
autoUploadNativeSymbols | https://docs.sentry.io/platforms/android/configuration/gradle/
includeNativeSources | https://docs.sentry.io/platforms/android/configuration/gradle/
includeSourceContext | https://docs.sentry.io/platforms/android/configuration/gradle/
dexguardEnabled | https://docs.sentry.io/platforms/android/configuration/gradle/
assembleRelease | https://docs.sentry.io/platforms/android/configuration/gradle/
io.sentry.release | https://docs.sentry.io/platforms/android/configuration/releases/
packageName | https://docs.sentry.io/platforms/android/configuration/releases/
versionName | https://docs.sentry.io/platforms/android/configuration/releases/
versionCode | https://docs.sentry.io/platforms/android/configuration/releases/
options.setRelease | https://docs.sentry.io/platforms/android/configuration/releases/
release | https://docs.sentry.io/platforms/android/configuration/options/
environment | https://docs.sentry.io/platforms/android/configuration/options/
attachScreenshot | https://docs.sentry.io/platforms/android/configuration/options/
attachViewHierarchy | https://docs.sentry.io/platforms/android/configuration/options/
dataCollection | https://docs.sentry.io/platforms/android/configuration/options/
sendDefaultPii | https://docs.sentry.io/platforms/android/configuration/options/
userInfo | https://docs.sentry.io/platforms/android/configuration/options/
cookies | https://docs.sentry.io/platforms/android/configuration/options/
httpHeaders.request | https://docs.sentry.io/platforms/android/configuration/options/
httpHeaders.response | https://docs.sentry.io/platforms/android/configuration/options/
urlQueryParams | https://docs.sentry.io/platforms/android/configuration/options/
httpBodies | https://docs.sentry.io/platforms/android/configuration/options/
graphql.document | https://docs.sentry.io/platforms/android/configuration/options/
graphql.variables | https://docs.sentry.io/platforms/android/configuration/options/
filePaths | https://docs.sentry.io/platforms/android/configuration/options/
DENY_LIST | https://docs.sentry.io/platforms/android/configuration/options/
profileLifecycle | https://docs.sentry.io/platforms/android/configuration/options/
profileSessionSampleRate | https://docs.sentry.io/platforms/android/configuration/options/
enableNdkAppHangTracking | https://docs.sentry.io/platforms/android/configuration/options/
io.sentry.screenshot.mask-all-text | https://docs.sentry.io/platforms/android/enriching-events/screenshots/
io.sentry.screenshot.mask-all-images | https://docs.sentry.io/platforms/android/enriching-events/screenshots/
setMaskAllImages | https://docs.sentry.io/platforms/android/enriching-events/screenshots/
options.sessionReplay.maskAllText | https://docs.sentry.io/platforms/android/session-replay/
ScreenshotStrategyType.CANVAS | https://docs.sentry.io/platforms/android/session-replay/
ScreenshotStrategyType.PIXEL_COPY | https://docs.sentry.io/platforms/android/session-replay/
```

## Unconfirmed
- `profilesSampleRate`: listed on the options page; the Android deprecation status is not stated, so do not recommend it either way.
- `anrProfilingSampleRate` and `enableAnrFingerprinting`: listed under ANR Options; defaults not read.
- Metrics, feedback, AI monitoring and feature flags on Android: no Android page fetched for these.
- View hierarchy masking rules: the viewhierarchy page was read for headings only.
