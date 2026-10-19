# Apple platforms, shared base (module: platforms/apple)

Applies to the sentry-cocoa SDK: 9.x current (9.30.2 on 2026-10-20), 8.x legacy, v10 unreleased. Platform specifics live in
`platforms/apple-ios` (iOS, tvOS, visionOS, Mac Catalyst) and `platforms/apple-macos` (native AppKit/SwiftUI macOS); read this file
first, then the one that matches the target's `SDKROOT`. Removed/renamed 9.0 options: data/stale-apis/cocoa.tsv (believe those rows).

## Detect

| Signal | Where | Means |
|---|---|---|
| `sentry-cocoa` dependency, products `SentrySPM` / `Sentry` / `Sentry-Dynamic` / `SentryObjC` | `Package.swift` | SPM install in a package |
| `XCRemoteSwiftPackageReference`, `XCSwiftPackageProductDependency` | `project.pbxproj` | SPM added through Xcode; the product name tells the route |
| pinned version | `Package.resolved` (also under an `.xcworkspace` `xcshareddata/swiftpm`) | the installed SDK version; the declared range is not |
| `pod 'Sentry'` / `Sentry (x.y.z)` | `Podfile`, `Podfile.lock` | CocoaPods: frozen, see Install route |
| `Cartfile` mention | repo root | Carthage: dropped in 9 |
| `import Sentry`, `import SentrySwift`, `@import Sentry`, `SentrySDK.start` / `startWithConfigureOptions` | sources | init site and import style |
| `SDKROOT`, `SUPPORTED_PLATFORMS`, `IPHONEOS_DEPLOYMENT_TARGET`, `MACOSX_DEPLOYMENT_TARGET` | `project.pbxproj` | which platform module applies; one repo can hold several targets |
| `DEBUG_INFORMATION_FORMAT`, `ENABLE_USER_SCRIPT_SANDBOXING`, a `shellScript` with `debug-files upload` | `project.pbxproj` | symbol upload state (see Release and artifacts) |
| `PrivacyInfo.xcprivacy`, `.sentryclirc`, `fastlane/Fastfile` with `sentry_debug_files_upload` | repo | privacy manifest, token file (must be gitignored), CI lane |

Multi-target repos get one finding set per target, with the platform of that target. Libraries/frameworks do not initialize Sentry.

## Install route

Wizard: `sentry-wizard -i ios` (interactive, the user runs it; iOS-oriented). Audit what it wrote (ground rule 10). Otherwise manual from
the live page: `sentry-ctx docs page platforms/apple/install/swift-package-manager`. Use exactly one product:

| Product | Use | Notes |
|---|---|---|
| `SentrySPM` | recommended: compiled from source | supports package traits; imported as `SentrySwift` in first-party test apps (the SPM page does not say so) |
| `Sentry` | pre-built static | `import Sentry`; fastest app start of the pre-built options |
| `Sentry-Dynamic` | pre-built dynamic | when the project needs dynamic linking |
| `SentryObjC` (+ `SentryObjC-Static` / `-Dynamic`) | pure Objective-C, ObjC++, Clang modules off | since 9.16.0; never link it together with `Sentry` |
| `SentrySwiftUI` | deprecated | merged into `Sentry` in 9.4.1; flag as a stale dependency |
| `NoUIFramework` trait | headless/CLI targets | with `SentrySPM`, SDK 9.7.0+, Swift 6.1+, Xcode 26.4+; not for apps |

CocoaPods: the SDK is not published after 9.19.1 (older versions stay); the trunk goes read-only Dec 2 2026 (blog.cocoapods.org plan).
Carthage support was dropped in 9. Both are migration findings, with SPM or the pre-built XCFramework from GitHub Releases as target.

SDK version guidance: read the pin, not the range. An 8.x pin keeps 8.x option names valid but blocks the 9 line (iOS/tvOS 15,
macOS 10.14 then 12 from 9.25.0, Xcode 16; migration page). A pin of exactly 9.29.1 crashes statically linked apps without `-ObjC`
(fixed in 9.29.2). v10 is unreleased: do not write v10 names.

## Init placement

`SentrySDK.start` on the main thread as early as the platform allows (details in the platform module). Background-thread init
works but is not recommended. A second `start`, or init after the first view appears, is a finding.

## Options by SDK major

| option | 8.x | 9.x | note |
|---|---|---|---|
| `profilesSampleRate`, `profilesSampler`, `enableAppLaunchProfiling` | work | removed 9.0 | `configureProfiling` with `sessionSampleRate` (default `0`) and `lifecycle` |
| `enableTracing`, `enablePerformanceV2`, `inAppExclude`, `defaultIntegrations`, `integrations` | present | removed 9.0 | set `tracesSampleRate` |
| `enableAppHangTrackingV2` | opt-in from 8.50.0 | removed; V2 default on iOS/tvOS only | |
| `enableAppHangTracking` | default on | default `true`, deprecated 9.29.0; v10 removes it | prefer `enableMetricKit` |
| `enableLogs` / `enableMetrics` | experimental | top-level; no-op since 9.27.0 (docs page still says "must set") | `SentrySDK.logger` is not gated |
| `enableMemoryIntrospection` | no option, behaviour on | default `false` since 9.24.0 | stack strings near the crash can hold PII |
| `sendDefaultPii` | default `false` | default `false` | v10 replaces it with `dataCollection` |
| `releaseName`, `dist`, `environment` | same | same | `environment` defaults to `production`; `dist` max 64 chars |
| `enableMetricKit` | default `false` | default `false` | needs iOS 15+ / macOS 12+ |
| `beforeSend`, `beforeSendWithHint` | `beforeSend` | `beforeSendWithHint` since 9.28.0 | attach files to fatal events through the hint |

## Product support matrix

Shared by every Apple target: crash reporting (reports go to disk, sent on next launch), breadcrumbs, attachments, release health
(`enableAutoSessionTracking`, sessions end after 30 s in background), HTTP client errors (`enableCaptureFailedRequests` default
`true`), network/file I/O/Core Data tracing, logs, metrics. Everything UI-dependent differs by platform: see the platform modules.

## Release and artifacts

- Release: when `releaseName` is unset the SDK uses `CFBundleIdentifier@CFBundleShortVersionString+CFBundleVersion`, for example
  `my.project.name@2.3.12+1234`. Overriding with a bare version collides across projects. Release, archive dSYMs and (for
  non-store apps) the appcast must describe the same build.
- Symbols (required for readable native stacks): the build must emit dSYMs (`DEBUG_INFORMATION_FORMAT` = DWARF with dSYM File; the Xcode
  default for Release only); an org auth token (secret; never in the repo or on a command line); then one upload route:
  Xcode Run Script, fastlane, or CI/Makefile. Matching is by debug UUID, not by release.
- Commands: v4 `sentry debug-files upload <path>... --org <o> --project <p> [--include-sources]`, check with
  `sentry debug-files check <path>`; v3 `sentry-cli debug-files upload ...` (docs still show `sentry-cli`; `upload-dsym` and
  `upload-dif` map to `debug-files upload`; `sentry-ctx cli-map --intent upload_dsyms`). `--include-sources` uploads source code
  to Sentry: only with consent.
- Verify uploads in Project Settings, Debug Files, then with a crash from a Release build with the debugger detached.

## Privacy

`sendDefaultPii` defaults to `false`; since 8.56.0 Relay infers the IP only when it is `true` (CHANGELOG 8.56.0; docs: the SDK
doesn't send the user's IP address by default). Replay and screenshot masking default to masking all text and images (iOS module). Static linking
(`Sentry`, `SentrySPM`) means the app must carry the privacy manifest entries itself (iOS module). Swift log string interpolation
turns interpolated values into attributes (`sentry.message.parameter.N`): review before using `SentrySDK.logger`.

## Verify recipe

Platform modules own the trigger. Common rules: run without a debugger; use a Release-like configuration for symbol checks;
`environment` non-production; marker via a tag on the scope; remove the trigger after R3.

## Gotchas

| Symptom | Cause | Source |
|---|---|---|
| Build error after bumping to 9 | removed 9.0 option (`profilesSampleRate`, `enableTracing`, ...) | migration page, cocoa.tsv |
| Upload phase silently does nothing | `ENABLE_USER_SCRIPT_SANDBOXING = YES` | dsym page |
| Unsymbolicated stacks | Debug config has no dSYM, or dSYM UUID differs from the shipped build | dsym page |
| App crashes at launch on 9.29.1 | static link without `-ObjC` | CHANGELOG 9.29.1 / 9.29.2 |
| Pod resolves 9.19.1 forever | CocoaPods frozen | cocoapods page |

## Sources
- https://docs.sentry.io/platforms/apple/install/swift-package-manager/
- https://docs.sentry.io/platforms/apple/install/ , .../install/cocoapods/ , .../install/carthage/ , .../install/manual-install/
- https://docs.sentry.io/platforms/apple/migration/v8-to-v9/
- https://docs.sentry.io/platforms/apple/configuration/options/ , .../configuration/releases/
- https://docs.sentry.io/platforms/apple/dsym/
- https://docs.sentry.io/platforms/apple/data-management/data-collected/
- https://github.com/getsentry/sentry-cocoa/blob/main/CHANGELOG.md
- https://blog.cocoapods.org/CocoaPods-Specs-Repo/

## Identifiers
```identifiers
releaseName | https://docs.sentry.io/platforms/apple/configuration/options/
dist | https://docs.sentry.io/platforms/apple/configuration/options/
environment | https://docs.sentry.io/platforms/apple/configuration/options/
sendDefaultPii | https://docs.sentry.io/platforms/apple/configuration/options/
enableMemoryIntrospection | https://docs.sentry.io/platforms/apple/configuration/options/
enableMetricKit | https://docs.sentry.io/platforms/apple/configuration/options/
enableAppHangTracking | https://docs.sentry.io/platforms/apple/configuration/options/
enableAutoSessionTracking | https://docs.sentry.io/platforms/apple/configuration/options/
enableCaptureFailedRequests | https://docs.sentry.io/platforms/apple/configuration/options/
beforeSend | https://docs.sentry.io/platforms/apple/configuration/options/
beforeSendWithHint | https://docs.sentry.io/platforms/apple/configuration/options/
configureProfiling | https://docs.sentry.io/platforms/apple/configuration/options/
sessionSampleRate | https://docs.sentry.io/platforms/apple/configuration/options/
lifecycle | https://docs.sentry.io/platforms/apple/configuration/options/
tracesSampleRate | https://docs.sentry.io/platforms/apple/configuration/options/
enableLogs | https://docs.sentry.io/platforms/apple/configuration/options/
enableMetrics | https://docs.sentry.io/platforms/apple/configuration/options/
SentrySPM | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
Sentry-Dynamic | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
SentryObjC | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
SentrySwiftUI | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
NoUIFramework | https://docs.sentry.io/platforms/apple/install/swift-package-manager/
SentrySwift | https://github.com/getsentry/sentry-cocoa/blob/main/TestApps/macOS-CLI-Xcode/Sources/main.swift
DEBUG_INFORMATION_FORMAT | https://docs.sentry.io/platforms/apple/dsym/
ENABLE_USER_SCRIPT_SANDBOXING | https://docs.sentry.io/platforms/apple/dsym/
sentry_debug_files_upload | https://docs.sentry.io/platforms/apple/dsym/
dataCollection | https://github.com/getsentry/sentry-cocoa/blob/main/CHANGELOG_V10.md
startWithConfigureOptions | https://docs.sentry.io/platforms/apple/guides/ios/
```

## Unconfirmed
- `shellScript`, `XCRemoteSwiftPackageReference`, `XCSwiftPackageProductDependency`, `Package.resolved`: Xcode/SwiftPM file formats used as detection signals; Sentry's docs do not describe them, and the `xcshareddata/swiftpm` location of a workspace's `Package.resolved` is from Xcode convention, not a Sentry page.
- `sentry init`: not exercised on Apple targets; the documented accelerator is `sentry-wizard -i ios`.
- `import SentrySwift`: shown only in first-party test apps (TestApps/macOS-CLI-Xcode, TestApps/SPM); the SPM docs page and README use `import Sentry`.
