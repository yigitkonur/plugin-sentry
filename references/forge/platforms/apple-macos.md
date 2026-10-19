# Native macOS apps (module: platforms/apple-macos)

Applies to AppKit and SwiftUI apps whose target is macOS (SDKROOT macosx), sandboxed or not, distributed outside the App Store
(notarized DMG, Sparkle) or inside it. Verified against sentry-cocoa 9.30.2 (2026-10-19). Shared Apple facts: `platforms/apple`.
macOS is **not** iOS: several iOS options do not exist on this platform and setting them is a compile error, not a no-op.

## Detect

| Signal | Where | Meaning |
|---|---|---|
| `SDKROOT = macosx`, `MACOSX_DEPLOYMENT_TARGET` | `project.pbxproj` | native macOS target (engine: `platforms: [macos]`, `role: desktop`) |
| `XCRemoteSwiftPackageReference "sentry-cocoa"`, pin in `Package.resolved` | pbxproj, `*.xcworkspace/xcshareddata/swiftpm/` | SPM install; the resolved pin is the SDK version, not the declared range |
| `NSApplicationDelegateAdaptor` / `applicationWillFinishLaunching` / `main.swift` | sources | where init must go |
| `com.apple.security.app-sandbox`, `com.apple.security.network.client` | `*.entitlements` | engine: `apple.sandbox`, `apple.network_client` |
| `SUFeedURL` / Sparkle | Info.plist, deps | outside-the-store distribution: releases and appcast must line up |
| no CI, a `Makefile` release target | repo root | symbol upload must be added to that target |

## Install route

SPM is the supported route. Use exactly one product: `SentrySPM` (compiled from source, imported as `SentrySwift`) or the prebuilt
`Sentry` / `Sentry-Dynamic`. Headless helpers and CLIs: `SentrySPM` with the `NoUIFramework` trait. CocoaPods is frozen at 9.19.1 (trunk
goes read-only 2026-12-02) and Carthage was dropped in 9: migrate those units. Current instructions:
`sentry-ctx docs page platforms/apple/install/swift-package-manager` and `sentry-ctx docs page platforms/apple/guides/macos`.
The docs quick start for macOS still shows iOS-only lines: do not copy it blindly (see Gotchas). `sentry init` is not verified for
Apple targets; use the manual route and audit the result.

## Init placement

Call `SentrySDK.start` on the main thread at the earliest hook: the `App` initializer, `applicationWillFinishLaunching`
(earlier) or `applicationDidFinishLaunching`, or the top of `main.swift`. Crash handlers do not install under a debugger.
A command-line tool or LaunchAgent must `SentrySDK.flush(timeout:)` / `close()` before exit; `shutdownTimeInterval` bounds the wait.

## Options by SDK major

| option | 8.x | 9.x | note |
|---|---|---|---|
| `profilesSampleRate` | works | **removed (9.0)** | use `configureProfiling` with `sessionSampleRate` and `lifecycle` (`.trace` needs tracing); not on tvOS/watchOS/visionOS |
| `enableTracing`, `enablePerformanceV2`, `inAppExclude`, `defaultIntegrations` | | **removed (9.0)** | see `data/stale-apis/cocoa.tsv` |
| `enableAppHangTracking` | on | on, **deprecated 9.29.0** | pair with `enableMetricKit`; v10 removes it and `pauseAppHangTracking`/`resumeAppHangTracking` |
| `enableLogs`, `enableMetrics` | gate logs/metrics | **no-op since 9.27.0** | `SentrySDK.logger` calls are not gated by them |
| `releaseName` | default `bundleId@version+build` | same | do not override with the bare short version |
| `enableFileIOTracing` | on | on | note the spelling (not `enableFileIOTracking`) |
| `enableMemoryIntrospection` | | off by default since 9.24.0 | keep it off for privacy |
| `swiftAsyncStacktraces` | | opt-in | init must run on the main thread |
| `enabled` | | | a consent switch: an alternative to not calling start |

## Product support matrix (native macOS)

| product | supported | notes |
|---|---|---|
| crashes (Mach/signal/C++/ObjC) | yes | |
| uncaught `NSException` | **opt-in** | `enableUncaughtNSExceptionReporting`; macOS only (`#if os(macOS)`), needs swizzling (`enableSwizzling`); never together with the `SentryCrashExceptionApplication` principal class |
| app hangs | V1 only, deprecated | V2 is iOS/tvOS only; pause/resume around permission dialogs |
| MetricKit | yes, macOS 12+ | `enableMetricKit` defaults to false; delivers hang, CPU-exception and disk-write diagnostics only (not crashes, thermal or fatal terminations) |
| tracing: network, file I/O, Core Data | yes | NSData swizzling stops working on macOS 15: use the `...WithSentryTracing` file APIs |
| app start, UIViewController, TTID/TTFD, user-interaction tracing | **no** | Mac Catalyst only; `waitForFullDisplay` is a compile error |
| UI profiling | yes | via `configureProfiling` |
| Session Replay | **no (compile error)** | officially iOS only |
| `attachScreenshot`, `attachViewHierarchy` | **no (compile error)** | iOS/tvOS/visionOS |
| user feedback | API only | `SentryFeedback` + `SentrySDK.capture(feedback:)`; no widget on macOS |
| watchdog terminations | no | `enableWatchdogTerminationTracking` compiles but does nothing |
| logs, release health, breadcrumbs, attachments | yes | logs GA since 9.0 |

## Release and artifacts

- Leave `releaseName` unset: the default `bundleId@version+build` is unique across projects and carries the build number. Keep the
  archive's dSYMs, the Sentry release and the Sparkle appcast on the same version+build. `dist` is unset by default.
- Symbolication matches by debug UUID, not by release. Set `DEBUG_INFORMATION_FORMAT = dwarf-with-dsym` for every shipped configuration.
- With no CI, add a step after the archive in the release `Makefile`:
  `sentry debug-files upload <App>.xcarchive/dSYMs --org <org> --project <project> [--include-sources]` (v4; v3: `sentry-cli debug-files upload`),
  with the token from the environment or a gitignored `.sentryclirc`, never from the repo. Check with `sentry debug-files check <path>`.
- If you use an Xcode Run Script instead: it needs the documented Input Files entry, `ENABLE_USER_SCRIPT_SANDBOXING = NO`, and the
  `/opt/homebrew/bin` PATH on Apple silicon (see the dSYM docs page).
- Cache directory: `~/Library/Caches/` unsandboxed, `~/Library/Containers/<bundle id>/Data/Library/Caches/` sandboxed (`cacheDirectoryPath`).

## Privacy

`sendDefaultPii` defaults to false and, since 8.56, gates server-side IP inference. Review `enableNetworkBreadcrumbs` and
`enableCaptureFailedRequests`; use `beforeSend` and `beforeBreadcrumb` (also `beforeSendWithHint`) to redact `/Users/<name>` paths and
tokens. Swift string interpolation in `SentrySDK.logger` calls is extracted into log attributes: never interpolate user content.
The breadcrumb `data` setter is deprecated since 9.24.0. Static linking means the app must ship the privacy manifest entries Sentry
requires (see the Apple privacy manifest page). `user.geo` is inferred from the connecting IP at ingest even with no IP stored.

## Verify recipe

1. Detach the debugger (crash handlers do not install under it) and run a **signed Release-like build**.
2. R2: a debug-only trigger handled in the real app (a launch argument or hidden menu item) calls `SentrySDK.capture(message:)` with the
   marker, then throws an `NSException` and, last, crashes. Register the trigger file with `sentry-ctx run trigger <path>`; remove it after.
3. R3: `sentry-ctx verify wait --marker <id>`. A sandboxed app without `com.apple.security.network.client` never delivers: check
   the entitlement before debugging anything else.
4. R4: upload the dSYMs first, then confirm frames are symbolicated; native events can be reprocessed after an upload.
5. R5: scan the arrived event for `/Users/` paths, IP, geo and environment.

## Gotchas

- The quick start and the old template set `attachScreenshot`, `attachViewHierarchy` and `sessionReplay`: compile errors on macOS. Guard
  multi-platform code with `#if os(iOS) || os(tvOS) || os(visionOS)`.
- Sandboxed apps need `com.apple.security.network.client` to send events at all (Apple documents the entitlement as controlling outgoing connections).
- Permission dialogs look like hangs: call `pauseAppHangTracking` before and `resumeAppHangTracking` after. MetricKit hang diagnostics are not paused.
- 9.29.1 crashed apps that link statically without `-ObjC`; fixed in 9.29.2.
- Scope attachments from a previous run are no longer sent with a crash (9.29.2); use `beforeSendWithHint`.
- macOS minimum deployment target is 12 since 9.25.0 (the features page lags behind).
- v10 (unreleased, tracked in CHANGELOG_V10.md): MetricKit and logs on by default, `enableLogs`/`enableMetrics` and legacy app hangs removed, `sendDefaultPii` replaced by `dataCollection`.

## Sources
- https://docs.sentry.io/platforms/apple/guides/macos/
- https://docs.sentry.io/platforms/apple/guides/macos/features/
- https://docs.sentry.io/platforms/apple/guides/macos/usage/
- https://docs.sentry.io/platforms/apple/guides/macos/configuration/app-hangs/
- https://docs.sentry.io/platforms/apple/guides/macos/configuration/metric-kit/
- https://docs.sentry.io/platforms/apple/configuration/options/
- https://docs.sentry.io/platforms/apple/dsym/
- https://docs.sentry.io/platforms/apple/install/swift-package-manager/
- https://docs.sentry.io/platforms/apple/migration/v8-to-v9/
- https://github.com/getsentry/sentry-cocoa/blob/main/Sources/Swift/Options.swift
- https://github.com/getsentry/sentry-cocoa/blob/main/CHANGELOG.md
- https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.network.client

## Identifiers

```identifiers
enableUncaughtNSExceptionReporting | https://docs.sentry.io/platforms/apple/guides/macos/usage/
SentryCrashExceptionApplication | https://docs.sentry.io/platforms/apple/guides/macos/usage/
enableSwizzling | https://docs.sentry.io/platforms/apple/configuration/options/
enableAppHangTracking | https://docs.sentry.io/platforms/apple/configuration/options/
pauseAppHangTracking | https://docs.sentry.io/platforms/apple/guides/macos/configuration/app-hangs/
resumeAppHangTracking | https://docs.sentry.io/platforms/apple/guides/macos/configuration/app-hangs/
enableMetricKit | https://docs.sentry.io/platforms/apple/guides/macos/configuration/metric-kit/
configureProfiling | https://docs.sentry.io/platforms/apple/configuration/options/
sessionSampleRate | https://docs.sentry.io/platforms/apple/configuration/options/
releaseName | https://docs.sentry.io/platforms/apple/configuration/options/
enableFileIOTracing | https://docs.sentry.io/platforms/apple/configuration/options/
enableMemoryIntrospection | https://docs.sentry.io/platforms/apple/configuration/options/
swiftAsyncStacktraces | https://docs.sentry.io/platforms/apple/configuration/options/
sendDefaultPii | https://docs.sentry.io/platforms/apple/configuration/options/
enableNetworkBreadcrumbs | https://docs.sentry.io/platforms/apple/configuration/options/
enableCaptureFailedRequests | https://docs.sentry.io/platforms/apple/configuration/options/
beforeSend | https://docs.sentry.io/platforms/apple/configuration/options/
beforeBreadcrumb | https://docs.sentry.io/platforms/apple/configuration/options/
beforeSendWithHint | https://docs.sentry.io/platforms/apple/configuration/options/
cacheDirectoryPath | https://docs.sentry.io/platforms/apple/configuration/options/
shutdownTimeInterval | https://docs.sentry.io/platforms/apple/configuration/options/
enableWatchdogTerminationTracking | https://docs.sentry.io/platforms/apple/configuration/options/
enableLogs | https://docs.sentry.io/platforms/apple/configuration/options/
enableMetrics | https://docs.sentry.io/platforms/apple/configuration/options/
SentryFeedback | https://docs.sentry.io/platforms/apple/guides/macos/user-feedback/
SentrySPM | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
SentrySwift | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
NoUIFramework | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
dataCollection | https://github.com/getsentry/sentry-cocoa/blob/main/CHANGELOG_V10.md
DEBUG_INFORMATION_FORMAT | https://docs.sentry.io/platforms/apple/dsym/
ENABLE_USER_SCRIPT_SANDBOXING | https://docs.sentry.io/platforms/apple/dsym/
waitForFullDisplay | https://github.com/getsentry/sentry-cocoa/blob/main/Sources/Swift/SentrySwiftUI/SentryTracedView.swift
attachScreenshot | https://github.com/getsentry/sentry-cocoa/blob/main/Sources/Swift/Options.swift
attachViewHierarchy | https://github.com/getsentry/sentry-cocoa/blob/main/Sources/Swift/Options.swift
sessionReplay | https://github.com/getsentry/sentry-cocoa/blob/main/Sources/Swift/Options.swift
```

## Unconfirmed
- `kernel EPERM`: the exact failure mode of a missing network entitlement is not documented by Apple or Sentry; the requirement itself is.
- `sentry init` and `@sentry/wizard -i ios` behavior on a native macOS target: not exercised.
