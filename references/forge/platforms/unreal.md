# Unreal Engine (module: platforms/unreal)

## Detect
| Signal | Where | Read it for |
|---|---|---|
| `*.uproject` with `"Sentry"` in its Plugins list | project root | plugin enabled for the project (Settings > Plugins > Code Plugins shows it) |
| `Plugins/Sentry/Sentry.uplugin` | project `Plugins/` directory | GitHub or Fab install present; `Sentry.uplugin` declares the `PostBuildSteps` used for symbol upload |
| `"Sentry"` in `PublicDependencyModuleNames` | `*.Build.cs` (docs example: `MyProject.build.cs`) | game module uses the C++ API |
| `USentrySubsystem`, `InitializeWithSettings` | game and plugin C++ sources | init and capture call sites to read |
| `sentry.properties` | project root | written by the plugin for symbol upload; holds an auth token, never public |

Blueprint-only projects have no `*.Build.cs` consumer; the GitHub package needs a C++ project (add an empty C++ class to convert). Project Settings > Plugins > Sentry is editor UI; the fetched pages do not name the file that stores it, so take those values from the user or the build config.

## Install route
| Route | Use when | Docs path (`sentry-ctx docs page`) |
|---|---|---|
| GitHub Releases (recommended) | C++ project, UE 4.27 and newer | `platforms/unreal/install`, section "Installing from GitHub Releases (Recommended)" |
| Fab | UE 5.4 and newer; docs recommend it only for Blueprint projects | `platforms/unreal/install`, section "Installing from Fab" |
| Build Yourself | custom dependency builds | `platforms/unreal/install` ("Build Yourself"); `platforms/unreal/configuration/building-plugin-dependencies` |

No accelerator: `data/detect/frameworks.json` has no wizard id for `unreal`; install is manual from the live page. Copy the artifact matching the engine version into `Plugins/`; on next launch UE prompts to build the Sentry and SentryEditor modules. Right = the plugin is enabled and the game module lists it only if C++ code calls the API.

## Init placement
- Default: the SDK initializes automatically at application startup (`platforms/unreal`, Configure). Right = the "Initialize SDK automatically" setting is on, or an explicit init exists.
- If that setting is off, explicit init goes through `InitializeWithSettings` on `USentrySubsystem`, obtained with `GEngine->GetEngineSubsystem<USentrySubsystem>()`. Right = one call in a startup path every shipped build runs (not behind a debug flag or a level that may never load), before the first capture.
- Runtime overrides use the same call (an `FConfigureSettingsDelegate` receives `USentrySettings`). `bRequireUserConsent` on: nothing is sent until consent; `GiveUserConsent` and `RevokeUserConsent` on the subsystem change the state.

## Options by SDK major
The fetched pages describe one SDK line; no prior-line values were fetched, so v(N-1) is "—" throughout.

| option | v(N-1) | v(N) | note |
|---|---|---|---|
| `Dsn` | — | string | minimum configuration; the project DSN |
| `EditorDsn` | — | string | editor events; empty means `Dsn` is used |
| `Debug` | — | bool, default `true` | verbose SDK logging |
| `SampleRate` | — | float, default `1.0` | error sampling |
| `Release` | — | string | see Release and artifacts |
| `Environment` | — | string | environments page |
| `EnableBuildConfigurations`, `EnableBuildTargets` | — | struct | Core > Advanced; gate symbol upload per configuration and target |
| `UseNativeBackend` | — | bool, default `false` | experimental native backend on Windows, Linux, macOS |
| `CrashpadWaitForUpload` | — | bool, default `false` | Windows and Linux; no effect with `UseNativeBackend` |
| `AttachStacktrace` | — | bool, default `true` | |
| `AttachScreenshot` | — | bool, default `false` | leaves the device when on |
| `AttachGameLog` | — | bool, default `false` | leaves the device when on |
| `AttachGpuDump` | — | bool, default `true` | attached by default; review it |
| `TracesSampleRate`, `TracesSampler` | — | float / function | tracing is off until one is set; `TracesSampleRate` applies only when no sampler is defined and there is no parent decision |
| `SendDefaultPii` | — | bool, default `false` | |
| `bRequireUserConsent`, `bDefaultUserConsentGiven` | — | bool, defaults `false` / `true` | consent gate |
| `BeforeSend`, `BeforeBreadcrumb` | — | hooks | Hooks section of options |

## Product support matrix
| product | supported | notes |
|---|---|---|
| errors | yes | minidump crash capture: Windows (UE 5.2+) and Linux via Native SDK; macOS, iOS, Android via their SDKs; PlayStation, Xbox, Nintendo Switch listed. Windows UE 5.1 or older needs the Crash Reporter Client |
| tracing | yes | must set `TracesSampleRate` or `TracesSampler`; sampling page |
| profiling | unconfirmed | no profiling page or option in the fetched pages |
| replay | yes, experimental | Session Replay page: gameplay video of the moments before a crash |
| logs | yes | Structured Logging page; related options `AutomaticBreadcrumbsForLogs`, `AttachGameLog` |
| metrics | yes | Metrics page: counters, gauges, distributions |
| crons | unconfirmed | not in the features list |
| feedback | unconfirmed | Sentry Crash Reporter collects user feedback after a crash; the User Feedback product page was not fetched |
| ai | unconfirmed | not in the fetched pages |
| flags | unconfirmed | not in the fetched pages |
| debug files | yes | symbol upload in `PostBuildSteps`; see Release and artifacts |
| release health | yes | sessions; Windows automatic crash capture needs UE 5.2+ |

## Release and artifacts
Release string:
- Default: `ProjectName@ProjectVersion`. `ProjectName` comes from `FApp::GetProjectName()`; `ProjectVersion` is read from `DefaultGame.ini`. Right = the version in `DefaultGame.ini` is bumped with each shipped build, or the release is split across versions.
- Override: set `OverrideReleaseName` to true and `Release` on the `USentrySettings` passed to `InitializeWithSettings`. Right = the value comes from a build-time variable, not a hardcoded string.
- Keep the release in sync with deploy or source-map tooling (options, `Release`).

Symbols (`platforms/unreal/configuration/debug-symbols`):

| Item | Right | Source |
|---|---|---|
| Automatic upload | off by default; enable with "Upload debug symbols automatically" or `SENTRY_UPLOAD_SYMBOLS_AUTOMATICALLY` set to `True` (CI) | debug-symbols |
| Scope | only build configurations and target types enabled under Core > Advanced (`EnableBuildConfigurations`, `EnableBuildTargets`) | debug-symbols |
| Runner | bundled `sentry-cli`, run in `PostBuildSteps` declared in `Sentry.uplugin` | debug-symbols |
| Auth | `sentry.properties` at project root (token inside; never public), or `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_AUTH_TOKEN` env vars (used when the properties file is absent) | debug-symbols |
| Manual | `sentry-cli --auth-token <token> debug-files upload --org <org> --project <project> PATH_TO_SYMBOLS` | debug-symbols |
| macOS / iOS | dSYM: `MacPlatform.bUseDSYMFiles = true;` and `IOSPlatform.bGeneratedSYM = true;` in the `.Target.cs`; UE 5.3+ modern Xcode: upload in a custom Xcode build phase | debug-symbols |
| Android | symbols via the Sentry Android Gradle Plugin | debug-symbols |
| Source maps | no source-map step on any fetched page | — |

CI: env vars `SENTRY_UPLOAD_SYMBOLS_AUTOMATICALLY`, `SENTRY_ORG`, `SENTRY_PROJECT`, `SENTRY_AUTH_TOKEN` (token from the CI secret store, never in the repo). The pages do not say how uploaded symbols link to a release; do not assert a link.

## Privacy
| Data | Default | Control |
|---|---|---|
| Minidump | used to build the event, then dropped; sensitive info stripped | "Store Minidumps As Attachments" (org or project Security & Privacy); off by default |
| Minidump / screenshot / log attachments | retained 30 or 90 days by plan; Sentry does not scrub attachments | per-issue limit in Security & Privacy; `AttachScreenshot`, `AttachGameLog` |
| GPU dump | `AttachGpuDump` default `true` | set `false` if not needed |
| PII | `SendDefaultPii` default `false` | Sensitive Data settings if enabled |
| Consent | `bRequireUserConsent` default `false` | consent calls on the subsystem |

## Verify recipe
1. Add one temporary entry point on a real path of the shipped game: a console command or a call in the startup path that calls `CaptureMessage` on `USentrySubsystem` (from `GEngine->GetEngineSubsystem<USentrySubsystem>()`), with a unique marker such as `sentry-verify-<yyyymmdd>`. The docs' Verify snippet is the minimal form; the real path proves the wiring.
2. Build and run the configuration that ships (one listed in `EnableBuildConfigurations`). Editor runs go to `EditorDsn` or `Dsn`, so do not verify from the editor alone.
3. In the Sentry project, find the message by the marker. One event expected. If absent, check the packaged `Dsn`, the init setting, and the consent state.
4. Remove the entry point: grep the source for the marker, delete the lines, rebuild, and grep again to confirm zero hits.

## Gotchas
| Trap | Right | Source |
|---|---|---|
| Blueprint project installs the GitHub package | C++ only; add an empty C++ class, or use Fab (UE 5.4+) for Blueprint | install page, Overview of SDK Versions |
| Windows crash capture on UE 5.1 or older | configure the Crash Reporter Client | platforms/unreal (Features) |
| Release health crash capture on Windows | UE 5.2+ and the "Enable automatic crash capturing (Windows, UE 5.2+)" setting | releases page |
| Minidumps assumed stored | off by default; enabling stores them as attachments | platforms/unreal, Store Minidumps |
| Symbols assumed uploaded | off by default; only enabled configurations and targets upload | debug-symbols |
| Token in project files | `sentry.properties` holds the auth token; never commit or ship it | debug-symbols |
| macOS / iOS symbolication fails | dSYM generation flags in `.Target.cs` are required | debug-symbols |
| Editor events in production project | `EditorDsn` empty means `Dsn` | options |
| Tracing assumed on | off until `TracesSampleRate` or `TracesSampler` is set; the sampler wins over the rate | options, sampling |

## Sources
- https://docs.sentry.io/platforms/unreal/
- https://docs.sentry.io/platforms/unreal/install/
- https://docs.sentry.io/platforms/unreal/configuration/
- https://docs.sentry.io/platforms/unreal/configuration/options/
- https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
- https://docs.sentry.io/platforms/unreal/configuration/releases/
- https://docs.sentry.io/platforms/unreal/configuration/crash-reporter/
- https://docs.sentry.io/platforms/unreal/configuration/sampling/
- https://docs.sentry.io/platforms/unreal/configuration/environments/
- https://docs.sentry.io/platforms/unreal/session-replay/

## Identifiers
```identifiers
CaptureMessage | https://docs.sentry.io/platforms/unreal/
USentrySubsystem | https://docs.sentry.io/platforms/unreal/
GetEngineSubsystem | https://docs.sentry.io/platforms/unreal/
InitializeWithSettings | https://docs.sentry.io/platforms/unreal/configuration/releases/
FConfigureSettingsDelegate | https://docs.sentry.io/platforms/unreal/configuration/releases/
USentrySettings | https://docs.sentry.io/platforms/unreal/configuration/releases/
OverrideReleaseName | https://docs.sentry.io/platforms/unreal/configuration/releases/
FApp::GetProjectName | https://docs.sentry.io/platforms/unreal/configuration/releases/
ProjectName | https://docs.sentry.io/platforms/unreal/configuration/releases/
ProjectVersion | https://docs.sentry.io/platforms/unreal/configuration/releases/
DefaultGame.ini | https://docs.sentry.io/platforms/unreal/configuration/releases/
Dsn | https://docs.sentry.io/platforms/unreal/configuration/options/
EditorDsn | https://docs.sentry.io/platforms/unreal/configuration/options/
SampleRate | https://docs.sentry.io/platforms/unreal/configuration/options/
EnableBuildConfigurations | https://docs.sentry.io/platforms/unreal/configuration/options/
EnableBuildTargets | https://docs.sentry.io/platforms/unreal/configuration/options/
UseNativeBackend | https://docs.sentry.io/platforms/unreal/configuration/options/
CrashpadWaitForUpload | https://docs.sentry.io/platforms/unreal/configuration/options/
AttachStacktrace | https://docs.sentry.io/platforms/unreal/configuration/options/
AttachScreenshot | https://docs.sentry.io/platforms/unreal/configuration/options/
AttachGameLog | https://docs.sentry.io/platforms/unreal/configuration/options/
AttachGpuDump | https://docs.sentry.io/platforms/unreal/configuration/options/
TracesSampleRate | https://docs.sentry.io/platforms/unreal/configuration/options/
TracesSampler | https://docs.sentry.io/platforms/unreal/configuration/options/
SendDefaultPii | https://docs.sentry.io/platforms/unreal/configuration/options/
bRequireUserConsent | https://docs.sentry.io/platforms/unreal/configuration/options/
bDefaultUserConsentGiven | https://docs.sentry.io/platforms/unreal/configuration/options/
GiveUserConsent | https://docs.sentry.io/platforms/unreal/configuration/options/
RevokeUserConsent | https://docs.sentry.io/platforms/unreal/configuration/options/
BeforeSend | https://docs.sentry.io/platforms/unreal/configuration/options/
BeforeBreadcrumb | https://docs.sentry.io/platforms/unreal/configuration/options/
AutomaticBreadcrumbsForLogs | https://docs.sentry.io/platforms/unreal/configuration/options/
SENTRY_UPLOAD_SYMBOLS_AUTOMATICALLY | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
SENTRY_ORG | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
SENTRY_PROJECT | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
sentry.properties | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
PostBuildSteps | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
Sentry.uplugin | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
MacPlatform.bUseDSYMFiles | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
IOSPlatform.bGeneratedSYM | https://docs.sentry.io/platforms/unreal/configuration/debug-symbols/
PublicDependencyModuleNames | https://docs.sentry.io/platforms/unreal/install/
MyProject.build.cs | https://docs.sentry.io/platforms/unreal/install/
```

## Unconfirmed
- `DefaultEngine.ini` (Sentry settings section name): not on any fetched page; research notes say unverified.
- Plugin version `1.25.0`: research note only; not on any fetched page.
- Crash Reporter vs Sentry choice from UE 5.2: the sentence on the main page was cut in the fetch; verify on the crash-reporter pages before stating it.
- Profiling, crons, AI monitoring, feature flags, and the User Feedback widget for Unreal: no fetched page covers them; the auditor should record UNVERIFIED.
