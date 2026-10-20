# Apple iOS, tvOS, visionOS, Mac Catalyst (module: platforms/apple-ios)

Applies to sentry-cocoa 9.x (9.30.2 on 2026-10-20; v10 unreleased) in UIKit/SwiftUI apps. Shared Apple facts (detection, products,
release name, symbol commands, 8.x to 9 options): `platforms/apple`. Native macOS: `platforms/apple-macos`. Removed 9.0 names:
data/stale-apis/cocoa.tsv. Minimums in 9: iOS 15, tvOS 15, visionOS 1.0 (migration page).

## Detect

| Signal | Where | Means |
|---|---|---|
| `SDKROOT` iphoneos/appletvos/xros, `IPHONEOS_DEPLOYMENT_TARGET`, `SUPPORTED_PLATFORMS` | `project.pbxproj` | which row of the support matrix applies; a target can list several |
| `SUPPORTS_MACCATALYST = YES` | `project.pbxproj` | Mac Catalyst build of an iOS app (UIKit features, no AppKit-only options) |
| `UIApplicationDelegateAdaptor`, `@main` + `App.init()`, `UIApplicationDelegate` | sources | init hook |
| `SentrySDK.start { options in` with `attachScreenshot`, `profilesSampleRate`, `sessionReplay` | `AppDelegate.swift` etc. | compare against the options table |
| Run Script with `debug-files upload` + `ENABLE_USER_SCRIPT_SANDBOXING` | `project.pbxproj` | symbol upload state |
| `Podfile` `pod 'Sentry', '~> 8.x'` | repo root | CocoaPods 8.x: migration unit |

## Install route

Accelerator: `sentry-wizard -i ios` (user runs it; it installs via SPM, patches the AppDelegate or SwiftUI `App`, adds an `Upload
Debug Symbols` phase, writes `.sentryclirc` with a token and adds it to `.gitignore`, adds a fastlane lane). Audit the diff.
Manual: `sentry-ctx docs page platforms/apple/guides/ios/manual-setup`. Product choice for an app: `SentrySPM` (recommended, from
source) or pre-built `Sentry` / `Sentry-Dynamic`; exactly one (table in `platforms/apple`). `SentrySwiftUI` is deprecated.

## Init placement

- Main thread, as early as possible: `application(_:didFinishLaunchingWithOptions:)` (UIKit) or the SwiftUI `App` `init()`.
  Background init is possible but not recommended (view hierarchy needs the main thread; launch crashes are detected reliably only
  from the main thread). Crashes are persisted and sent on the next launch on iOS.
- Widgets, Live Activities, Action, Intent and Share extensions are separate processes: the SDK disables app hang tracking there
  (9.0.0); App Clips are not on that list.
- Do not run the verification under the Xcode debugger: crash handlers and hang tracking are off with a debugger attached.

## Options by SDK major

| option | 8.x | 9.x | note |
|---|---|---|---|
| `configureProfiling` | n/a (use `profilesSampleRate`) | closure setting `sessionSampleRate` (default `0`) and `lifecycle` (`manual` default, `trace` needs tracing) | iOS only; not tvOS/watchOS/visionOS |
| `enableAppHangTracking` | default on | default on, deprecated 9.29.0; `appHangTimeoutInterval` default `2.0`, keep it above 0.1 | V2 default on iOS/tvOS since 9.0 |
| `pauseAppHangTracking` / `resumeAppHangTracking` | from 8.30.0 | present; v10 removes them (CHANGELOG_V10) | wrap permission dialogs |
| `enableWatchdogTerminationTracking` | default `true` | default `true` | needs `enableCrashHandler`; foreground apps, not simulators or debugger |
| `enableMetricKit` | default `false` | default `false` | iOS 15+; hang, CPU-exception and disk-write diagnostics only |
| `enableTimeToFullDisplayTracing` | default `false` | default `false`, stable 9.30.0 | requires `SentrySDK.reportFullyDisplayed()` |
| `enablePreWarmedAppStartTracing` | opt-in | default `true` | |
| `attachViewHierarchy` / `attachScreenshot` | default `false` | default `false`; masks default on (`screenshot.maskAllText`) | iOS/tvOS/visionOS; compile gate `os(iOS) \|\| os(tvOS) \|\| os(visionOS)` |
| `sessionReplay.sessionSampleRate` / `sessionReplay.onErrorSampleRate` | from 8.31.1, default `0` | default `0` | iOS 16+; `maskAllText` and `maskAllImages` default `true` |
| `swiftAsyncStacktraces` | default off | default off, stable 9.30.0 | v10 turns it on |
| `enableLogs` / `enableMetrics` | gate logs/metrics | no-op since 9.27.0 | do not rely on `enableLogs = false` for privacy |

## Product support matrix

| product | iOS | tvOS | visionOS | Mac Catalyst |
|---|---|---|---|---|
| Crash, breadcrumbs, attachments, logs | yes | yes | yes (experimental per docs) | yes |
| App hangs | V2 (fully / non-fully blocking) | V2 | hang detection per docs | V1/V2 not documented |
| Watchdog terminations | yes | yes | yes (watchdog page) | yes |
| MetricKit | iOS 15+ | no | no | not documented |
| Session Replay | official, iOS 16+ | works 16+, unofficial | not available | not documented |
| Screenshot, view hierarchy | yes | yes | yes | yes (docs: "except Mac Catalyst" on the macOS page) |
| Profiling (`configureProfiling`) | yes | no | no | compiles as iOS (inferred) |
| User feedback UI (`configureUserFeedback`) | yes | no UI | no UI | not documented |
| App start, UIViewController, user interaction, TTID/TTFD | yes | yes | yes | UIKit features yes; TTID/TTFD not documented |

TTID/TTFD for SwiftUI (`SentryTracedView` with `waitForFullDisplay`) is documented for iOS and tvOS only.

## Release and artifacts

- Release default: `bundleId@version+build` (do not shorten). `dist` is unset by default.
- Symbols: the Release configuration emits dSYMs by default; Debug does not. Choose one route and check it ran.

| Route | What "right" looks like |
|---|---|
| Xcode Run Script | docs script after the compile step; Input Files has `${DWARF_DSYM_FOLDER_PATH}/${DWARF_DSYM_FILE_NAME}/Contents/Resources/DWARF/${EXECUTABLE_NAME}`; `ENABLE_USER_SCRIPT_SANDBOXING = NO`; on arm64 the script puts `/opt/homebrew/bin` on PATH; org, project and token come from `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_AUTH_TOKEN` (not hard-coded); warning vs error is a deliberate choice |
| fastlane | `sentry_debug_files_upload` (plugin 2.0 removed `sentry_upload_dsym` and `sentry_upload_dif`, and `api_key`) |
| CI / Makefile | `sentry debug-files upload` on the archive's dSYMs (v3: `sentry-cli`) |

`--include-sources` / `include_sources` uploads source code; ask first. Verify with `sentry debug-files check` and a symbolicated test crash.

## Privacy

| Data | Default | Control |
|---|---|---|
| IP, user | not sent | `sendDefaultPii` (`false`) |
| Replay | text and images masked | `sessionReplay.maskAllText`, `sessionReplay.maskAllImages` (`true`); `sessionReplay.maskedViewClasses` for more |
| Screenshots | text masked | `screenshot.maskAllText`; screenshots and view hierarchy are off until `attachScreenshot` / `attachViewHierarchy` |
| Crash memory strings | not included since 9.24.0 | `enableMemoryIntrospection` |
| Privacy manifest | static linking (`Sentry`, `SentrySPM`): the app must ship its own `PrivacyInfo.xcprivacy` with `NSPrivacyCollectedDataTypes` and `NSPrivacyAccessedAPITypes`; dynamic frameworks are processed by Apple | privacy manifest page (SDK 8.25.0+) |

## Verify recipe

R2: add a temporary trigger on the real launch path (a debug-only launch argument or button) that captures an error using the guide's
verify snippet and sets the marker tag on the scope; run a Release-like build on a device or simulator with the debugger
detached; relaunch to flush stored crash reports; `sentry-ctx verify wait --marker ...`. R4: stack frames show function and file
names. Remove the trigger afterwards.

## Gotchas

| Symptom | Cause | Source |
|---|---|---|
| Fixture: `profilesSampleRate` compiles on 8.36, breaks on 9 | removed 9.0 | migration page |
| Run Script uploads nothing | `ENABLE_USER_SCRIPT_SANDBOXING = YES` | dsym page |
| App hang false positives | permission dialogs; wrap with `pauseAppHangTracking` / `resumeAppHangTracking`; hang tracking is off under a debugger | app-hangs page |
| Hang events missing | `appHangTimeoutInterval` set too high, or extension processes | options page |
| TTFD spans never finish | `enableTimeToFullDisplayTracing` set but `reportFullyDisplayed()` never called | automatic-instrumentation page |
| Docs quick start copied verbatim sets `sendDefaultPii = true` and `enableLogs = true` | liberal sample values | iOS guide |

## Sources
- https://docs.sentry.io/platforms/apple/guides/ios/ , .../guides/ios/features/ , .../guides/tvos/features/ , .../guides/visionos/features/
- https://docs.sentry.io/platforms/apple/guides/macos/features/
- https://docs.sentry.io/platforms/apple/configuration/options/ , .../configuration/app-hangs/ , .../configuration/watchdog-terminations/
- https://docs.sentry.io/platforms/apple/configuration/metric-kit/
- https://docs.sentry.io/platforms/apple/tracing/instrumentation/automatic-instrumentation/
- https://docs.sentry.io/platforms/apple/tracing/instrumentation/swiftui-instrumentation/
- https://docs.sentry.io/platforms/apple/profiling/ , .../session-replay/ , .../guides/ios/session-replay/
- https://docs.sentry.io/platforms/apple/dsym/ , .../data-management/apple-privacy-manifest/ , .../migration/v8-to-v9/
- https://github.com/getsentry/sentry-cocoa/blob/main/Sources/Swift/Options.swift
- https://github.com/getsentry/sentry-cocoa/blob/main/CHANGELOG.md

## Identifiers
```identifiers
configureProfiling | https://docs.sentry.io/platforms/apple/configuration/options/
sessionSampleRate | https://docs.sentry.io/platforms/apple/configuration/options/
lifecycle | https://docs.sentry.io/platforms/apple/configuration/options/
enableAppHangTracking | https://docs.sentry.io/platforms/apple/configuration/options/
appHangTimeoutInterval | https://docs.sentry.io/platforms/apple/configuration/options/
enableWatchdogTerminationTracking | https://docs.sentry.io/platforms/apple/configuration/options/
enableCrashHandler | https://docs.sentry.io/platforms/apple/configuration/options/
enableMetricKit | https://docs.sentry.io/platforms/apple/configuration/options/
enableTimeToFullDisplayTracing | https://docs.sentry.io/platforms/apple/configuration/options/
enablePreWarmedAppStartTracing | https://docs.sentry.io/platforms/apple/configuration/options/
swiftAsyncStacktraces | https://docs.sentry.io/platforms/apple/configuration/options/
sendDefaultPii | https://docs.sentry.io/platforms/apple/configuration/options/
enableMemoryIntrospection | https://docs.sentry.io/platforms/apple/configuration/options/
screenshot.maskAllText | https://docs.sentry.io/platforms/apple/configuration/options/
sessionReplay.sessionSampleRate | https://docs.sentry.io/platforms/apple/configuration/options/
sessionReplay.onErrorSampleRate | https://docs.sentry.io/platforms/apple/configuration/options/
sessionReplay.maskAllText | https://docs.sentry.io/platforms/apple/configuration/options/
sessionReplay.maskAllImages | https://docs.sentry.io/platforms/apple/configuration/options/
sessionReplay.maskedViewClasses | https://docs.sentry.io/platforms/apple/configuration/options/
pauseAppHangTracking | https://docs.sentry.io/platforms/apple/configuration/app-hangs/
resumeAppHangTracking | https://docs.sentry.io/platforms/apple/configuration/app-hangs/
reportFullyDisplayed | https://docs.sentry.io/platforms/apple/tracing/instrumentation/swiftui-instrumentation/
configureUserFeedback | https://github.com/getsentry/sentry-cocoa/blob/main/Sources/Swift/Options.swift
DEBUG_INFORMATION_FORMAT | https://docs.sentry.io/platforms/apple/dsym/
ENABLE_USER_SCRIPT_SANDBOXING | https://docs.sentry.io/platforms/apple/dsym/
sentry_debug_files_upload | https://docs.sentry.io/platforms/apple/dsym/
sentry_upload_dsym | https://docs.sentry.io/platforms/apple/dsym/
sentry_upload_dif | https://docs.sentry.io/platforms/apple/dsym/
api_key | https://docs.sentry.io/platforms/apple/dsym/
DWARF_DSYM_FOLDER_PATH | https://docs.sentry.io/platforms/apple/dsym/
PrivacyInfo.xcprivacy | https://docs.sentry.io/platforms/apple/data-management/apple-privacy-manifest/
NSPrivacyCollectedDataTypes | https://docs.sentry.io/platforms/apple/data-management/apple-privacy-manifest/
NSPrivacyAccessedAPITypes | https://docs.sentry.io/platforms/apple/data-management/apple-privacy-manifest/
didFinishLaunchingWithOptions | https://docs.sentry.io/platforms/apple/guides/ios/
SentryTracedView | https://docs.sentry.io/platforms/apple/tracing/instrumentation/swiftui-instrumentation/
SentrySPM | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
SentrySwiftUI | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
maskAllText | https://docs.sentry.io/platforms/apple/configuration/options/
maskAllImages | https://docs.sentry.io/platforms/apple/configuration/options/
include_sources | https://docs.sentry.io/platforms/apple/dsym/
```

## Unconfirmed
- `SUPPORTS_MACCATALYST`: an Apple build setting used here as a detection signal; Sentry's docs do not mention it.
- Mac Catalyst rows marked "not documented" or "inferred": Sentry's docs only say the macOS page features "also available" on Mac Catalyst; `Options.swift` gates by `os(iOS)`, which Catalyst compiles as, but no Sentry page states it for profiling, replay, feedback or hangs.
- `sessionReplay` on visionOS: the visionOS features page says Session Replay is not available, while `Options.swift` compiles it for visionOS; treat as unsupported.
- `import SentrySwift`: see `platforms/apple`; shown only in first-party test apps.
