# Unity (module: platforms/unity)

Scope: Sentry Unity SDK, major 4 (4.10.3 is current; the install page uses `#4.10.3` as its pin example). Config is an
editor-written asset, not code. No vendored upstream reference exists. Every statement below is about 4.x.

## Detect

| Signal | Where | Means |
|---|---|---|
| UPM Git URL `https://github.com/getsentry/unity.git` | `Packages/manifest.json` | SDK installed; a `#<version>` suffix pins it (Install) |
| `Assets/Resources/Sentry/SentryOptions.asset` | Assets | DSN, environment, sampling written by `Tools > Sentry`; read at build and runtime (Configure) |
| `Assets/Plugins/Sentry/SentryCliOptions.asset` | Assets | symbol-upload auth token; must not be public (Debug Symbols) |
| `ProjectSettings/ProjectVersion.txt` | project root | Unity editor version; decides IL2CPP line-number support (Gotchas) |
| `Assets/**/*.cs` | Assets | game code; the Verify recipe uses a scene script |

Engine: frameworks id `unity`, role `game`, module `platforms/unity`. Fixture `evals/fixtures/unity`: detected at 0.7 from
`Packages/manifest.json`, both assets found, tracked token in `Assets/Plugins/Sentry/SentryCliOptions.asset`; `Assets/Scripts/Boot.cs` has no Sentry call.

## Install route

- No CLI accelerator. Install by UPM Git URL `https://github.com/getsentry/unity.git` (optional `#4.10.3`).
  Docs: `sentry-ctx docs page platforms/unity --section Install`.
- First open of `Tools > Sentry` runs an in-editor wizard that picks the project and writes the config (`--section Configure`).
- The Asset Store route is not on the fetched page (Unconfirmed). Do not write install steps from memory.

## Init placement

No code-level init call is named on the fetched pages (Unconfirmed). Configure says the asset is read at build time and at
runtime, so the auditor checks the inputs, not a call site.

| Check | Right | Wrong |
|---|---|---|
| `SentryOptions.asset` under `Assets/Resources/Sentry/` | present, written by the editor window | absent: no DSN, no events |
| DSN source | `Dsn` in the asset, or `SENTRY_DSN` env var | neither: no events, no error (Dsn) |
| Sampling | deliberate `TracesSampleRate` or `TracesSampler` | left at `1` from testing (fixture snapshot shows `TracesSampleRate` 1) |

## Options by SDK major

Only the v4 options page was read. The v(N-1) column is n/f (not fetched), so no cross-major claims are made. n/r means the
default was not read on the fetched sections.

| option | v(N-1) | v(N) | note |
|---|---|---|---|
| `Dsn` | n/f | no default; `SENTRY_DSN` is the fallback; no DSN means no events | Core Options |
| `Environment` | n/f | default `production`; `editor` inside the Unity Editor | Core Options |
| `Release` | n/f | default `Application.productName` + `@` + `Application.version` | Core Options |
| `Debug`, `DiagnosticLevel` | n/f | `Debug` default `false`; `DiagnosticLevel` default `debug` | SDK diagnostics |
| `SendDefaultPii` | n/f | default `false`; adds PII from active integrations | Privacy & PII |
| `ServerName` | n/f | sent only when set; often the device hostname | Privacy & PII |
| `TracesSampleRate` | n/f | docs: `1.0` while testing, lower afterwards; default n/r | Tracing page |
| `TracesSampler` | n/f | per-transaction sampling | Tracing page |
| `Il2CppLineNumberSupportEnabled` | n/f | enabled by default; opt out in code or `Tools > Sentry > Advanced` | IL2CPP page |
| `AttachStacktrace` | n/f | default n/r; when on, Unity's stack lines can appear on `Debug.LogError` | IL2CPP page |
| `AttachScreenshot`, `AttachViewHierarchy`, `MaxBreadcrumbs` | n/f | defaults n/r | Data Enrichment |
| `SetBeforeSend`, `SetBeforeBreadcrumb`, `SetBeforeSendTransaction`, `SetBeforeCaptureScreenshot`, `SetBeforeCaptureViewHierarchy` | n/f | Hooks: code-level filter and scrub points | Hooks |
| `ShutdownTimeout`, `InitCacheFlushTimeout`, `MaxCacheItems`, `HttpProxy`, `Transport` | n/f | Transport & Network; defaults n/r | |
| `EnableAppHangTracking`, `AnrDetectionEnabled`, `AndroidNativeAnrEnabled` | n/f | App Hang and ANR section; defaults n/r | |
| `SendClientReports`, `CaptureFailedRequests`, `IsGlobalModeEnabled`, `Distribution`, `InAppInclude`, `InAppExclude` | n/f | listed on the options index; defaults n/r | |

## Product support matrix

"no" means the research matrix marks the cell `—` (its key: no page), and the docs probe returned Page Not Found where probed.
Matrix source: `research/06-product-map.md` section 3. It is not an official page, so it is a lead only.

| product | supported | notes |
|---|---|---|
| replay | no | no `platforms/unity/session-replay` page; matrix `—` |
| profiling | no | no `platforms/unity/profiling` page; matrix `—` |
| logs | yes | page `platforms/unity/logs` exists; matrix GA from 4.0 (version not read on the page) |
| metrics | yes | page `platforms/unity/metrics` (Application Metrics); matrix GA from 4.2 |
| crons | no | no `platforms/unity/crons` page; matrix `—` |
| tracing | yes | page `platforms/unity/tracing`; `TracesSampleRate`, `TracesSampler` |
| feedback | yes | page `platforms/unity/user-feedback`; matrix GA with the prefab in beta (page not read) |
| ai | no | matrix `—`; no page probed |
| flags | no | no `platforms/unity/feature-flags` page; matrix `—` |
| debug files | yes | `platforms/unity/data-management/debug-files`; automated upload (Release and artifacts) |

Native crashes (not a product row): Android, iOS, Windows, macOS, Linux. Consoles: C# errors only. WebGL: C# errors.

## Release and artifacts

- Release: default `Application.productName` + `@` + `Application.version`. Override with `Release`, or the `SENTRY_RELEASE` env
  var, which is read automatically. Precedence between the two is not stated (Unconfirmed).
- Environment: default `production`; `editor` inside the Unity Editor. Staging and dev builds must set `Environment`.
- Debug files and symbols: the automated upload is on by default and runs during the Unity build in the Editor. Configure it in
  `Tools > Sentry > Editor` (Auth Token, Organization Slug, Project Name); that writes
  `Assets/Plugins/Sentry/SentryCliOptions.asset`. The SDK bundles sentry-cli for Windows, macOS and Linux (Debug Symbols).
- Manual route: `sentry-cli --auth-token <token> debug-files upload --org <org> --project <project> PATH` (Manual Upload).
- iOS: dSYM is picked up at the end of the build; `BCSymbolMap` files are processed during archiving (Native Support, iOS).
- IL2CPP line mapping rides on the same upload; the server needs it to show C# line numbers (IL2CPP page).
- Source maps: none on the fetched Unity pages. CI: only the manual route is documented (Unconfirmed).
- Check uploads under Project Settings > Debug Files (`platforms/unity/data-management/debug-files`).

## Privacy

| Data | Default (v4 docs) | Control |
|---|---|---|
| PII from integrations | off (`SendDefaultPii` `false`) | `SendDefaultPii`; if on, strip with Sensitive Data rules |
| Minidumps (native crashes) | used to build the event, then dropped; sensitive data stripped | `Store Minidumps As Attachments` (org or project Security & Privacy); off by default; attachments not scrubbed; kept 30 or 90 days |
| Screenshot, view hierarchy | attachments | `AttachScreenshot`, `AttachViewHierarchy`, `SetBeforeCaptureScreenshot`, `SetBeforeCaptureViewHierarchy` |
| Server name | not sent unless set | `ServerName` |
| Auth token | in `Assets/Plugins/Sentry/SentryCliOptions.asset`; must not be public | keep it out of git and out of shipped builds |

## Verify recipe

Real code path: a script that runs in the scene. In the fixture that is `Start()` in `Assets/Scripts/Boot.cs`.

1. Add one marked line at the top of `Start()`: `Debug.LogError("sentry-verify-<nonce>");`. The Verify section says
   `Debug.LogError` is captured as an Error by default; `Debug.Log` and `Debug.LogWarning` add breadcrumbs.
2. Press Play in the Editor. Editor events carry environment `editor`.
3. In Sentry, search issues for `sentry-verify-<nonce>`: expect one Error with the build's release. Skip the "Unity of Bugs" sample.
4. Remove the line. `grep -rn "sentry-verify" Assets/` must print nothing. Do not commit the marker.

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| No events, no error | no DSN in the asset and no `SENTRY_DSN` (Dsn) | set `Dsn` in `Assets/Resources/Sentry/SentryOptions.asset` |
| Auth token in git | `SentryCliOptions.asset` holds the token; the fixture shows it tracked | gitignore it; docs say it must not be public (Debug Symbols) |
| Editor events under `editor`, shipped under `production` | default environment depends on where the code runs (Environment) | set `Environment` per build flavour |
| No C# line numbers on `SentrySdk.CaptureMessage` or `Debug.LogError` | IL2CPP mapping covers thrown exceptions only (IL2CPP page) | expect native-only stacks for messages |
| `Debug.LogException(new Exception(...))` unmapped | the new exception has no stack frames (IL2CPP page) | throw the real exception |
| IL2CPP line numbers missing | IL2CPP needs Unity 2020.3+; Windows needs 2021.3+ (IL2CPP page); check `ProjectSettings/ProjectVersion.txt` | upgrade the editor or accept native-only stacks |
| Windows native crashes never arrive | `crashpad_handler.exe` is copied to the build output and must ship (Native Support, Windows) | include it in the shipped build |
| iOS symbols not applied | dSYM and `BCSymbolMap` come from the build and archive steps (Native Support, iOS) | keep the automated upload on for iOS archives |
| No symbols uploaded | automated upload needs the `Tools > Sentry > Editor` settings; on by default, needs configuration | fill Auth Token, Organization Slug, Project Name |
| Console crashes missing | consoles get C# errors only (Native Support intro) | expect C# errors only on PlayStation, Xbox, Switch |
| Every transaction sent | `TracesSampleRate` `1` left from testing; docs say lower it afterwards (Tracing page) | pick a deliberate rate or `TracesSampler` |
| Changes missing from the shipped build | asset read at build time and runtime (Configure) | rebuild after editing `SentryOptions.asset` |

## Sources
- https://docs.sentry.io/platforms/unity.md
- https://docs.sentry.io/platforms/unity/configuration/options.md
- https://docs.sentry.io/platforms/unity/configuration/il2cpp.md
- https://docs.sentry.io/platforms/unity/native-support.md
- https://docs.sentry.io/platforms/unity/data-management/debug-files.md
- https://docs.sentry.io/platforms/unity/tracing.md
- https://docs.sentry.io/platforms/unity/logs.md, `metrics.md`, `user-feedback.md` (same host; existence probed)

## Identifiers
```identifiers
Dsn | https://docs.sentry.io/platforms/unity/configuration/options.md
Environment | https://docs.sentry.io/platforms/unity/configuration/options.md
Release | https://docs.sentry.io/platforms/unity/configuration/options.md
Debug | https://docs.sentry.io/platforms/unity/configuration/options.md
DiagnosticLevel | https://docs.sentry.io/platforms/unity/configuration/options.md
SendDefaultPii | https://docs.sentry.io/platforms/unity/configuration/options.md
ServerName | https://docs.sentry.io/platforms/unity/configuration/options.md
TracesSampler | https://docs.sentry.io/platforms/unity/configuration/options.md
AttachStacktrace | https://docs.sentry.io/platforms/unity/configuration/options.md
AttachScreenshot | https://docs.sentry.io/platforms/unity/configuration/options.md
AttachViewHierarchy | https://docs.sentry.io/platforms/unity/configuration/options.md
MaxBreadcrumbs | https://docs.sentry.io/platforms/unity/configuration/options.md
InAppInclude | https://docs.sentry.io/platforms/unity/configuration/options.md
InAppExclude | https://docs.sentry.io/platforms/unity/configuration/options.md
SetBeforeSend | https://docs.sentry.io/platforms/unity/configuration/options.md
SetBeforeBreadcrumb | https://docs.sentry.io/platforms/unity/configuration/options.md
SetBeforeSendTransaction | https://docs.sentry.io/platforms/unity/configuration/options.md
SetBeforeCaptureScreenshot | https://docs.sentry.io/platforms/unity/configuration/options.md
SetBeforeCaptureViewHierarchy | https://docs.sentry.io/platforms/unity/configuration/options.md
ShutdownTimeout | https://docs.sentry.io/platforms/unity/configuration/options.md
InitCacheFlushTimeout | https://docs.sentry.io/platforms/unity/configuration/options.md
MaxCacheItems | https://docs.sentry.io/platforms/unity/configuration/options.md
HttpProxy | https://docs.sentry.io/platforms/unity/configuration/options.md
Transport | https://docs.sentry.io/platforms/unity/configuration/options.md
EnableAppHangTracking | https://docs.sentry.io/platforms/unity/configuration/options.md
AnrDetectionEnabled | https://docs.sentry.io/platforms/unity/configuration/options.md
AndroidNativeAnrEnabled | https://docs.sentry.io/platforms/unity/configuration/options.md
SendClientReports | https://docs.sentry.io/platforms/unity/configuration/options.md
CaptureFailedRequests | https://docs.sentry.io/platforms/unity/configuration/options.md
IsGlobalModeEnabled | https://docs.sentry.io/platforms/unity/configuration/options.md
Distribution | https://docs.sentry.io/platforms/unity/configuration/options.md
SENTRY_DSN | https://docs.sentry.io/platforms/unity/configuration/options.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/unity/configuration/options.md
Application.productName | https://docs.sentry.io/platforms/unity/configuration/options.md
Application.version | https://docs.sentry.io/platforms/unity/configuration/options.md
TracesSampleRate | https://docs.sentry.io/platforms/unity/tracing.md
Il2CppLineNumberSupportEnabled | https://docs.sentry.io/platforms/unity/configuration/il2cpp.md
SentrySdk.CaptureMessage | https://docs.sentry.io/platforms/unity/configuration/il2cpp.md
Debug.LogException | https://docs.sentry.io/platforms/unity/configuration/il2cpp.md
Debug.Log | https://docs.sentry.io/platforms/unity.md
Debug.LogWarning | https://docs.sentry.io/platforms/unity.md
Debug.LogError | https://docs.sentry.io/platforms/unity.md
Assets/Resources/Sentry/SentryOptions.asset | https://docs.sentry.io/platforms/unity.md
Assets/Plugins/Sentry/SentryCliOptions.asset | https://docs.sentry.io/platforms/unity/native-support.md
crashpad_handler.exe | https://docs.sentry.io/platforms/unity/native-support.md
BCSymbolMap | https://docs.sentry.io/platforms/unity/native-support.md
```

## Unconfirmed
- `io.sentry.unity`: UPM package name from the research notes; the fetched install page shows only the Git URL.
- `SentrySdk.Init`: code-level init named in the research notes; not on any fetched page. Check the Programmatic Configuration part of the options page before asserting it.
- Asset Store install route: named in the brief; not on the fetched install page.
- `SENTRY_RELEASE` against the default release string: precedence not stated on the fetched pages.
- Command-line or CI builds running the automated symbol upload: not stated on the fetched pages.
- Defaults marked n/r (for example `AttachStacktrace`, `AttachScreenshot`, `MaxBreadcrumbs`): not read.
- Replay, profiling, crons, flags, AI for Unity: no Unity page found for replay, profiling, crons and flags; matrix `—`. Verify on a live docs page before proposing them.
