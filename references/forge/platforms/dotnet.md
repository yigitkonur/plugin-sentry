# .NET (module: platforms/dotnet)

Applies to the 6.x SDK family (`Sentry` 6.12.1, checked 2026-10-20). Covers `dotnet`, `maui`, `wpf`, `winforms`, `azure-functions`. ASP.NET Core is routed to `platforms/aspnetcore`. Only the 6.x options page was read; statements are about 6.x unless a row says otherwise.

## Detect

| Signal | Where | Means |
|---|---|---|
| `Sentry`, `Sentry.AspNetCore`, `Sentry.Maui`, `Sentry.Extensions.Logging`, `Sentry.Profiling` references | `*.csproj`, `Directory.Packages.props`, `packages.config`, `packages.lock.json` | SDK present; the lockfile gives the resolved major |
| `UseSentry(` / `SentrySdk.Init(` | `*.cs` | init site(s); see Init placement |
| `Sentry` section | `appsettings*.json` | options bound from configuration (ASP.NET Core) |
| `SentryOrg`, `SentryProject`, `SentryUploadSymbols` | `*.csproj`, `Directory.Build.props` | MSBuild upload route in use |

## Install route

No wizard id in the `dotnet` row, so install from the live pages. Never paste package steps from memory.

| framework id | docs path (`sentry-ctx docs page`) | package(s) at 6.x |
|---|---|---|
| dotnet | `platforms/dotnet` (Install) | `Sentry`; `Sentry.Profiling` for profiling |
| maui | `platforms/dotnet/guides/maui` | `Sentry.Maui` |
| wpf | `platforms/dotnet/guides/wpf` | `Sentry` |
| winforms | `platforms/dotnet/guides/winforms` (Configure has C# and VB sections; not read here) | per Install section |
| azure-functions | `platforms/dotnet/guides/azure-functions-worker` (`azure-functions` is Page Not Found) | `Sentry.Extensions.Logging`; `Sentry.OpenTelemetry.Exporter` for tracing |

## Init placement

| Framework | Where Sentry starts | Note |
|---|---|---|
| ASP.NET Core | `UseSentry` on the web builder (`builder.WebHost`), right after the builder is created | IHostBuilder form calls `UseSentry` inside ConfigureWebHostDefaults |
| MAUI | `.UseSentry(options => ...)` on the MAUI app builder chain in `MauiProgram.cs` (`CreateMauiApp`) | `Dsn` is the only required setting |
| WPF | `SentrySdk.Init` in the `App` constructor | set `IsGlobalModeEnabled = true` for client apps; dispatcher handler (Gotchas) |
| Azure Functions | `AddSentry` in ConfigureLogging of the `ConfigureFunctionsWorkerDefaults` host; tracing: `UseOtlp()` plus the OTLP exporter on the tracer provider | core features come through logging |

## Options by SDK major

| option | v(N-1) 5.x | v(N) 6.x | note |
|---|---|---|---|
| `Environment` | not checked | default `production` | `debug` with a debugger attached; ASP.NET Core also reports `staging` / `development` |
| `TracesSampleRate` | not checked | default `0.0` | tracing is off unless this or `TracesSampler` is set |
| `ProfilesSampleRate` | not checked | set with tracing | needs `Sentry.Profiling` and `AddProfilingIntegration()` |
| `SendDefaultPii` | not checked | default `false` | request URL/headers, user IP and name from integrations |
| `EnableLogs` | not checked | default `false` | logging integrations only; `SentrySdk.Logger` always sends since 6.10.0 |
| `EnableMetrics` | not checked | obsolete | ignored since 6.10.0; docs say removed in 7.0.0 |

ASP.NET Core reads the same keys from the `Sentry` section of `appsettings.json` (`MaxRequestBodySize`, `MinimumBreadcrumbLevel`, `MinimumEventLevel`, `AttachStackTrace`, `DiagnosticLevel`, `TracesSampleRate`).

## Product support matrix

| product | supported | notes |
|---|---|---|
| tracing | yes | `TracesSampleRate` or `TracesSampler`; Azure Functions uses OTLP (`UseOtlp()`) |
| profiling | yes, transaction-based | `ProfilesSampleRate`; `Sentry.Profiling` (not iOS/Mac Catalyst); `AddProfilingIntegration()`. Maturity label and .NET floor: unconfirmed |
| logs | yes | `EnableLogs` for logging integrations; `SentrySdk.Logger` always sends; SDK 5.14.0+ |
| metrics | yes | `SentrySdk.Metrics` counters, distributions, gauges; `SetBeforeSendMetric` filters; minimum version unconfirmed |
| crons | yes | SDK 4.2.0+; monitor config sent from code, created on first check-in (or in the UI) |
| feedback | yes | `SentrySdk.CaptureFeedback`; ASP.NET and ASP.NET Core have feedback integrations |
| ai | yes, experimental | `Sentry.Extensions.AI` needs `Microsoft.Extensions.AI.Abstractions` 9.7.0+; options carry the `Experimental.` prefix |
| replay, flags | no | no replay or feature-flag page for .NET; matrix shows no integration |
| debug files | yes | MSBuild `SentryUploadSymbols` / `SentryUploadSources`, or sentry-cli `debug-files upload` |

## Release and artifacts

- Release string: `Release` reads `SENTRY_RELEASE` by default. Docs say the SDK tries to configure one automatically, but the derivation is not on the options page (Unconfirmed). Right: set explicitly or via `SENTRY_RELEASE` at deploy, equal to the release CI creates.
- Debug files (PDBs, MSBuild route): `SentryUploadSymbols` defaults to `false`; set it `true` for Release builds. `SentryUploadSources` adds source context. Required: `SentryOrg`, `SentryProject`. Optional: `SentryUrl`, `SentryCreateRelease`, `SentrySetCommits`, `SentrySetCommitOptions`. `UseSentryCLI` defaults to `true`; `false` disables the bundled CLI, so nothing uploads.
- Direct route (publish pipelines without the MSBuild targets): `sentry-cli debug-files upload -o <org> -p <project> <paths>`; `--wait` blocks until analysis finishes (`cli/dif`). Source maps do not apply to managed code.
- Auth: CI sets `SENTRY_AUTH_TOKEN`; a workstation runs `sentry-cli login` (writes `~/.sentryclirc`). Docker: BuildKit `--secret id=sentry_auth_token,env=SENTRY_AUTH_TOKEN` on the build stage; in multi-stage builds publish with `--no-build --no-restore -p:UseSentryCLI=false`. `SentryAuthToken` and `SentryApiKey` exist; docs say keep them out of source and logs.

## Privacy

| Data | Default | Control |
|---|---|---|
| request URL/headers, user IP and name from integrations | not sent | `SendDefaultPii` (default `false`) |
| MAUI control text in breadcrumbs; screenshots on error | text off; MAUI sample turns screenshots on | `IncludeTextInBreadcrumbs`; `AttachScreenshot` (docs: only if no sensitive data on screen) |
| `SentrySdk.Logger` logs and metrics | always sent | `SetBeforeSendLog` / `SetBeforeSendMetric` returning `null` |

## Verify recipe

Use the real route. In the ASP.NET Core fixture, add one temporary action to `Controllers/HealthController.cs` (route `/Health/sentry-verify`). For MAUI or WPF, put the capture in the handler the user presses.

1. Inside the action, run the docs capture pattern (`try { throw ... } catch (Exception ex) { SentrySdk.CaptureException(ex); }`) with a unique marker in the message.
2. Run with `TracesSampleRate` non-zero, call the route once: 200 response, and one event with the marker appears in the project.
3. Remove the action and any temporary debug or sample-rate change; `grep -rn "sentry-verify" .` should print nothing.

## Gotchas

| Symptom | Cause | Fix |
|---|---|---|
| WPF: exception shown in the error dialog never reaches Sentry | production WPF apps (no debugger) catch it before `AppDomain.UnhandledException` | handle `DispatcherUnhandledException` in `App` and capture there (WPF page) |
| MAUI: Android or Apple native crashes missing | native SDKs are configured via `options.Native` | Android and Apple native options pages linked from the MAUI page |
| Stack frames without file or line | no PDB uploaded; `SentryUploadSymbols` is `false` by default | MSBuild route; without PDBs there are no line numbers |
| Tracing or profiling absent | `TracesSampleRate` defaults to `0.0`; profiling depends on tracing and the package | set the rate or `TracesSampler`; add `Sentry.Profiling` |
| Logs absent from logging integrations | `EnableLogs` defaults to `false` | set it; `SentrySdk.Logger` is separate |
| Multi-stage Docker publish fails after build upload | publish re-runs the CLI without the token | `--no-build --no-restore -p:UseSentryCLI=false` on publish |
| Azure Functions: logs arrive, traces do not | tracing needs the OTLP exporter | `UseOtlp()` and exporter per azure-functions-worker Configure |

## Sources
- https://docs.sentry.io/platforms/dotnet/
- https://docs.sentry.io/platforms/dotnet/configuration/options/
- https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
- https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
- https://docs.sentry.io/platforms/dotnet/guides/maui/
- https://docs.sentry.io/platforms/dotnet/guides/wpf/
- https://docs.sentry.io/platforms/dotnet/guides/azure-functions-worker/
- https://docs.sentry.io/platforms/dotnet/profiling/
- https://docs.sentry.io/platforms/dotnet/logs/
- https://docs.sentry.io/platforms/dotnet/metrics/
- https://docs.sentry.io/platforms/dotnet/crons/
- https://docs.sentry.io/platforms/dotnet/user-feedback/
- https://docs.sentry.io/platforms/dotnet/tracing/instrumentation/ai-agents-module/
- https://docs.sentry.io/cli/dif/

## Identifiers
```identifiers
UseSentry | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
Sentry.AspNetCore | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
Sentry.Maui | https://docs.sentry.io/platforms/dotnet/guides/maui/
CreateMauiApp | https://docs.sentry.io/platforms/dotnet/guides/maui/
MauiProgram.cs | https://docs.sentry.io/platforms/dotnet/guides/maui/
IncludeTextInBreadcrumbs | https://docs.sentry.io/platforms/dotnet/guides/maui/
AttachScreenshot | https://docs.sentry.io/platforms/dotnet/guides/maui/
options.Native | https://docs.sentry.io/platforms/dotnet/guides/maui/
SentrySdk.Init | https://docs.sentry.io/platforms/dotnet/guides/wpf/
DispatcherUnhandledException | https://docs.sentry.io/platforms/dotnet/guides/wpf/
AppDomain.UnhandledException | https://docs.sentry.io/platforms/dotnet/guides/wpf/
IsGlobalModeEnabled | https://docs.sentry.io/platforms/dotnet/guides/wpf/
ConfigureFunctionsWorkerDefaults | https://docs.sentry.io/platforms/dotnet/guides/azure-functions-worker/
AddSentry | https://docs.sentry.io/platforms/dotnet/guides/azure-functions-worker/
UseOtlp | https://docs.sentry.io/platforms/dotnet/guides/azure-functions-worker/
Sentry.OpenTelemetry.Exporter | https://docs.sentry.io/platforms/dotnet/guides/azure-functions-worker/
Sentry.Extensions.Logging | https://docs.sentry.io/platforms/dotnet/guides/azure-functions-worker/
Sentry | https://docs.sentry.io/platforms/dotnet/
SentrySdk.CaptureException | https://docs.sentry.io/platforms/dotnet/
SentrySdk.CaptureFeedback | https://docs.sentry.io/platforms/dotnet/user-feedback/
Release | https://docs.sentry.io/platforms/dotnet/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/dotnet/configuration/options/
Environment | https://docs.sentry.io/platforms/dotnet/configuration/options/
TracesSampleRate | https://docs.sentry.io/platforms/dotnet/configuration/options/
TracesSampler | https://docs.sentry.io/platforms/dotnet/configuration/options/
SendDefaultPii | https://docs.sentry.io/platforms/dotnet/configuration/options/
ProfilesSampleRate | https://docs.sentry.io/platforms/dotnet/profiling/
AddProfilingIntegration | https://docs.sentry.io/platforms/dotnet/profiling/
Sentry.Profiling | https://docs.sentry.io/platforms/dotnet/profiling/
EnableLogs | https://docs.sentry.io/platforms/dotnet/logs/
SentrySdk.Logger | https://docs.sentry.io/platforms/dotnet/logs/
SetBeforeSendLog | https://docs.sentry.io/platforms/dotnet/logs/
SentrySdk.Metrics | https://docs.sentry.io/platforms/dotnet/metrics/
EnableMetrics | https://docs.sentry.io/platforms/dotnet/metrics/
SetBeforeSendMetric | https://docs.sentry.io/platforms/dotnet/metrics/
Sentry.Extensions.AI | https://docs.sentry.io/platforms/dotnet/tracing/instrumentation/ai-agents-module/
Microsoft.Extensions.AI.Abstractions | https://docs.sentry.io/platforms/dotnet/tracing/instrumentation/ai-agents-module/
MaxRequestBodySize | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
MinimumBreadcrumbLevel | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
MinimumEventLevel | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
AttachStackTrace | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
DiagnosticLevel | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
SentryOrg | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryProject | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryUrl | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryUploadSymbols | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryUploadSources | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryCreateRelease | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentrySetCommits | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentrySetCommitOptions | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
UseSentryCLI | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryAuthToken | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryApiKey | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
sentry_auth_token | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
-p:UseSentryCLI=false | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
--no-build | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
--no-restore | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
sentry-cli debug-files upload | https://docs.sentry.io/cli/dif/
--wait | https://docs.sentry.io/cli/dif/
```

## Unconfirmed
- Release auto-derivation (assembly version or git): docs say the SDK tries to configure it; the rule is not on the options page.
- Profiling maturity label, .NET version floor, and metrics minimum version: not on the pages read.
