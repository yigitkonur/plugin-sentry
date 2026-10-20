# Flutter (module: platforms/flutter)

Applies to `sentry_flutter` 10.x (docs examples pin `^10.1.0`; Session Replay needs 9.0.0+, `traceLifecycle` needs 9.23.0+) and to the `sentry_dart_plugin` upload tool (3.2.0+ for `dart_symbol_map_path`). Version floors are the ones the cited pages state.

## Detect

| Signal | Where | Means |
|---|---|---|
| `sentry_flutter` under `dependencies:` | pubspec.yaml; resolved version in pubspec.lock | SDK installed; the lock gives the real version |
| `sentry:` block, `sentry_dart_plugin` | pubspec.yaml or sentry.properties | upload configured; no block means no symbol or source upload |
| `SentryFlutter.init(` | lib/main.dart, inside `main()` | the init site (ecosystems.json matches `\bSentryFlutter\.init\s*\(`) |
| `SentryWidget(` | the `appRunner` argument, wrapping the root widget | required for Session Replay |
| `sentry {` block | android/app/build.gradle(.kts) | Sentry Android Gradle Plugin; needed only with R8 or ProGuard |
| `ios/Podfile`, `enable-swift-package-manager: false` | ios/ and the Xcode project | Apple SDK ships through SPM; see Gotchas |

A package with no app entrypoint (no `runApp`) does not initialize Sentry: report and move on.

## Install route

| Route | Use when | Docs path |
|---|---|---|
| Wizard: `@sentry/wizard` with `-i flutter` (confirm with `--help`) | greenfield app, clean git, user can answer prompts | guide page says the wizard adds a sample exception to `main.dart` |
| Manual | existing app, or wizard not runnable | `sentry-ctx docs page platforms/dart/guides/flutter/manual-setup --section Install` |
| Debug symbols | obfuscated builds, native builds, web | `sentry-ctx docs page platforms/dart/guides/flutter/debug-symbols/dart-plugin --section "Configure the Plugin"` |

Never paste install steps from memory. The manual route is: `sentry_flutter` dependency, `SentryFlutter.init` in `main`, then the Apple SPM setup section.

## Init placement

- `main()` is `async` and `await SentryFlutter.init(...)` runs before `runApp`. The documented shape passes the app as `appRunner: () => runApp(SentryWidget(child: ...))`. Docs: configure "as early as possible" (manual-setup, Initialize the Sentry SDK).
- One `SentryFlutter.init` per app entrypoint. An entrypoint that calls `runApp` without init loses its errors and sessions.
- `runApp` outside `appRunner`, or the root widget not wrapped in `SentryWidget`, is a finding (replay does not record).
- Two init calls in one running app are a finding.

## Options by SDK major

| option | 9.x | 10.x (current) | note |
|---|---|---|---|
| `dsn` | not split on the fetched page | `SENTRY_DSN` read when no `dsn` is set | no DSN means no events; manual-setup shows `--dart-define` route |
| `sendDefaultPii` | not split on the fetched page | default `false` | on only by deliberate decision; see Privacy |
| `tracesSampleRate` | not split | `tracesSampleRate` or `tracesSampler` must be set to enable tracing | docs examples use `1.0` and say to adjust in production |
| `traceLifecycle` | added in 9.23.0 | default `SentryTraceLifecycle.stream`; `SentryTraceLifecycle.static` is transaction mode | stream is the 10.x default |
| `replay.sessionSampleRate`, `replay.onErrorSampleRate` | Replay needs 9.0.0+ | no split on the fetched page | examples disagree: 0.1 session in manual-setup, 1.0 in the replay page |
| `environment`, `release`, `dist` | not split | env fallbacks `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`, `SENTRY_DIST`; `environment` has no default | set all three explicitly |
| `attachScreenshot`, `attachViewHierarchy` | not read | not read | listed on the options page; check values against privacy answers |
| `beforeSend` | not split | hook | used for path rewrites (see Release) |

## Product support matrix

| product | supported | notes |
|---|---|---|
| Errors | yes (GA) | `sendDefaultPii` controls what integrations add |
| Tracing | yes | needs `tracesSampleRate` or `tracesSampler`; `traceLifecycle` default `stream` in 10.x |
| Profiling | no | no Flutter profiling page; research product map shows none |
| Replay | yes (GA, mobile) | SDK 9.0.0+; masks text, user input and non-asset images by default |
| Logs | yes | `Sentry.logger`, enabled by default (guide, manual-setup) |
| Metrics | yes | `Sentry.metrics`, enabled by default (guide, manual-setup) |
| Crons | no | no Flutter page |
| Feedback | yes | `SentryFeedbackForm` widget and user-feedback API page |
| AI monitoring | no | no Flutter page |
| Flags | yes (page exists) | feature-flags page with evaluation tracking; beta status not read |
| Debug files | yes | `sentry_dart_plugin`: symbols, Dart symbol map, sources, web source maps |

## Release and artifacts

- SDK release: the options page says `release` is read from `SENTRY_RELEASE` by default. No pubspec-derived SDK default is stated. Look for an explicit `release` or a `--dart-define` value.
- Plugin release: `name@version` from pubspec by default; `dist` defaults to the build number after `+`. The SDK release must be the same string the plugin uploads.
- Build first, then upload, in the same CI job from the same artifacts. Obfuscated mobile or desktop build:
  `flutter build <target> --obfuscate --split-debug-info=<dir> --extra-gen-snapshot-options=--save-obfuscation-map=build/app/obfuscation.map.json`
  Web build: `flutter build web --release --source-maps`.
- Upload: `flutter pub run sentry_dart_plugin` (dart-plugin, Running the Plugin).
- Config: `sentry:` block with `project`, `org`, `dart_symbol_map_path: build/app/obfuscation.map.json` (obfuscated mobile; readable issue titles on iOS and Android), `upload_sources`, `upload_source_maps` (web). Token from `SENTRY_AUTH_TOKEN` in the environment.
- Source context on iOS and Android needs `--split-debug-info`. It covers only the main app package.
- Android with R8 or ProGuard: configure the Sentry Android Gradle Plugin with `autoInstallation` disabled, because the Flutter SDK installs the Android SDK.
- Web: `url_prefix` for non-root deploys, plus a matching `beforeSend` path. Plugin 3.0.0+ needs SDK 9.1.0+, or `legacy_web_symbolication: true`.

## Privacy

| Data | default | control |
|---|---|---|
| user, IP, request headers added by integrations | not sent | `sendDefaultPii` default `false`; the page says to scrub sensitive data when enabled |
| replay text, user input, non-asset images | masked | `privacy.maskAssetImages` for asset images; third-party widgets are not detected, so mask them manually |
| screenshots, view hierarchy | options exist | `attachScreenshot`, `attachViewHierarchy` |
| source code in uploads | `upload_sources` default `false` | enable only by decision |
| upload token | none in code | keep `SENTRY_AUTH_TOKEN` in env, not in pubspec.yaml |

## Verify recipe

1. Add one marked trigger on the path real errors take: a temporary `Sentry.captureException(StateError('sentry-verify-<marker>'));` in the handler the user hits. Same call shape as the manual-setup Verify section (`throw StateError(...)` then `await Sentry.captureException(`).
2. Run `flutter run`, trigger the path, and confirm in Issues that the marker arrives with the expected release and environment.
3. Symbol proof: build with the obfuscated command, run `flutter pub run sentry_dart_plugin`, trigger the marker in that build, and confirm the Dart frames are symbolicated.
4. Remove: delete the marker line and any wizard sample exception (the guide says remove it once confirmed). `grep -rn "sentry-verify" lib/` must print nothing.

## Gotchas

| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Replay never records | `SentryWidget` not around root, or both sample rates 0 | wrap root, set a non-zero rate | session-replay, Setup |
| iOS build fails, native SDK missing | CocoaPods not supported for the plugin; `enable-swift-package-manager: false` disables SPM | remove the override, run `flutter config --enable-swift-package-manager` and `flutter pub get`; keep CocoaPods only for other plugins; iOS 15.0 or macOS 12.0 targets | manual-setup, Apple Platform Setup |
| Obfuscated Dart frames raw | build without `--obfuscate`/`--split-debug-info`, or plugin never run | build with flags, then run the plugin after the build | debug-symbols, When to Upload |
| iOS/Android issue titles still obfuscated | `dart_symbol_map_path` unset, or map not saved | add `--save-obfuscation-map` and point `dart_symbol_map_path` at it | dart-plugin, Building Your Application |
| No source context on iOS/Android | built without `--split-debug-info` | add the flag | dart-plugin, Features footnote |
| Plugin says release missing | previous release not in git history | `ignore_missing: true` | dart-plugin, Troubleshooting |
| Android frames raw under R8 | Android Gradle Plugin not configured | configure it, token from env | dart-plugin, Android Gradle Plugin |
| Web frames minified or unmatched | no `--source-maps`, or subpath deploy without `url_prefix` | rebuild with `--source-maps`; set `url_prefix` and matching `beforeSend` path | dart-plugin, Troubleshooting |
| Web symbolication fails on older SDK | plugin 3.0.0+ with SDK below 9.1.0 | upgrade SDK to 9.1.0+ or set `legacy_web_symbolication: true` | dart-plugin, Troubleshooting |
| Wizard sample exception fires on every launch | exception left in `main.dart` | remove after confirming the first event | guide, Verify Your Setup |
| Upstream note disagrees with docs | vendored debug-artifacts note writes `dart run sentry_dart_plugin`; the docs page writes `flutter pub run sentry_dart_plugin` | follow the docs page | dart-plugin, Running the Plugin |
| DSN or release set two ways | options page describes env fallbacks; manual-setup names `--dart-define` | pick one; confirm the value reaches the running app | options (dsn, release); manual-setup |
| Replay sample rate unclear | docs examples differ (0.1 vs 1.0 session) | decide per team policy | manual-setup vs session-replay |

## Sources
- https://docs.sentry.io/platforms/dart/guides/flutter/
- https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
- https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
- https://docs.sentry.io/platforms/dart/guides/flutter/session-replay/
- https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/
- https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
- https://docs.sentry.io/platforms/dart/guides/flutter/feature-flags/
- https://docs.sentry.io/platforms/dart/guides/flutter/user-feedback/

## Identifiers
```identifiers
sentry_flutter | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
SentryFlutter.init | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
appRunner | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
SentryWidget | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
runApp | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
Sentry.captureException | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
StateError | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
SENTRY_DSN | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
SENTRY_RELEASE | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
SENTRY_DIST | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
--dart-define | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
enable-swift-package-manager | https://docs.sentry.io/platforms/dart/guides/flutter/manual-setup/
sendDefaultPii | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
tracesSampleRate | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
tracesSampler | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
traceLifecycle | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
SentryTraceLifecycle.stream | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
SentryTraceLifecycle.static | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
release | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
environment | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
dist | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
dsn | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
beforeSend | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
attachScreenshot | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
attachViewHierarchy | https://docs.sentry.io/platforms/dart/guides/flutter/configuration/options/
sessionSampleRate | https://docs.sentry.io/platforms/dart/guides/flutter/session-replay/
onErrorSampleRate | https://docs.sentry.io/platforms/dart/guides/flutter/session-replay/
maskAssetImages | https://docs.sentry.io/platforms/dart/guides/flutter/session-replay/
Sentry.logger | https://docs.sentry.io/platforms/dart/guides/flutter/
Sentry.metrics | https://docs.sentry.io/platforms/dart/guides/flutter/
SentryFeedbackForm | https://docs.sentry.io/platforms/dart/guides/flutter/user-feedback/
sentry_dart_plugin | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
dart_symbol_map_path | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
upload_sources | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
upload_source_maps | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
url_prefix | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
legacy_web_symbolication | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
ignore_missing | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
autoInstallation | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
--split-debug-info | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
--obfuscate | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
--save-obfuscation-map | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
--extra-gen-snapshot-options | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
--source-maps | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
```

## Unconfirmed
- `minSdk`: Android minimum 26 comes only from the research notes; no fetched page states it.
- `Logs` floor 9.0 and `Metrics` floor 9.11: research product map only; the fetched pages say "enabled by default" with no version.
- `Flags` beta status: research notes say beta with a Firebase RC path; the feature-flags page was read by heading only.
- iOS dSYM upload step: not stated on the fetched Flutter pages; check the plugin Features table before asserting it.
