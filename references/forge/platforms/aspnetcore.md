# ASP.NET Core (module: platforms/aspnetcore)

Applies to `Sentry.AspNetCore` 6.x (6.12.1 in the docs install snippet, fetched 2026-10-20). It wraps `Sentry.Extensions.Logging` and `Sentry`, so their options apply too. Only 6.x is on the fetched pages. Framework id `aspnetcore`, role backend, docs path `dotnet/guides/aspnetcore`.

## Detect

| Signal | Where | Means |
|---|---|---|
| Microsoft.AspNetCore package reference (fixture: `Api.csproj`, `net8.0`) | `*.csproj`, `Directory.Packages.props`, `packages.lock.json` | framework `aspnetcore`; the lockfile gives the real version |
| `Sentry.AspNetCore` package | same files | SDK installed; compare with 6.12.1 |
| `UseSentry(` or `SentrySdk.Init(` | `Program.cs`, `Startup.cs`, host builder files | init site(s); fixture: `Program.cs:3`, `builder.WebHost.UseSentry(o =>` |
| `"Sentry"` section | `appsettings*.json`, environment variables | config-driven options |
| `dotnet publish` in a multi-stage build | `Dockerfile` | see Release and artifacts |

Read the init file, `appsettings*.json`, the csproj and the Dockerfile. A class library with no entrypoint does not initialize Sentry: report and move on. The engine's expected output for the fixture (`evals/expected/dotnet-aspnet.detect.json`) lists the init site, a DSN literal at `Program.cs:5` and `TracesSampleRate` 1.0 in its config snapshot. Those are findings, not defaults.

## Install route

- No accelerator: `data/detect/frameworks.json` has no wizard id for `aspnetcore`. Install manually from the live page: `sentry-ctx docs page platforms/dotnet/guides/aspnetcore --section Install` (NuGet `Sentry.AspNetCore`).
- Config: `--section Configure` (appsettings.json, environment variables, code). `platforms/dotnet/guides/aspnetcore/configuration` has no headings beyond its intro. `platforms/dotnet/guides/aspnetcore/performance` is Page Not Found; tracing is at `platforms/dotnet/guides/aspnetcore/tracing/instrumentation/automatic-instrumentation`.
- Related pages: `platforms/dotnet/guides/extensions-logging` (logging), `platforms/dotnet/configuration/options` (all options), `platforms/dotnet/configuration/msbuild` (build-time upload).

## Init placement

- Minimal hosting: `builder.WebHost.UseSentry();` directly after `WebApplication.CreateBuilder(args)`, before `builder.Build()`.
- Generic host: `webBuilder.UseSentry();` inside `ConfigureWebHostDefaults`. Older `IWebHost` form: `WebHost.CreateDefaultBuilder(args).UseSentry()`.
- Once per process. Extensions.Logging: the SDK "needs to be initialized only once"; set `InitializeSdk` to `false` on the logging integration if you call `SentrySdk.Init` yourself.
- Settings come from `appsettings.json`, environment variables, or the `UseSentry(o => ...)` lambda. Some settings (BeforeSend) are code-only.

## Options by SDK major

Only 6.x is documented on the fetched pages, so the v(N-1) column is `-`.

| option | v(N-1) | v(N) | note |
|---|---|---|---|
| `Dsn` | - | string; if unset the SDK reads `SENTRY_DSN`; if neither, no events | fixture hardcodes a DSN |
| `SendDefaultPii` | - | default `false`; when `true`: request URL and headers, IP, user from `HttpContext.User` | |
| `TracesSampleRate` | - | default `0.0`; tracing needs it or `TracesSampler` | docs example uses `1.0` with "adjust in production" |
| `TracesSampler` | - | callback alternative to `TracesSampleRate` | |
| `Release` | - | default: `SENTRY_RELEASE` env var | see Release and artifacts |
| `Environment` | - | default `production`; ASP.NET Core `staging`/`development` only when no other source is set | precedence: code, env var, config, then `IHostingEnvironment` |
| `MaxRequestBodySize` | - | `None`, `Small` (~4KB), `Medium` (~10KB), `Always` | no default on the page |
| `SetBeforeSend` | - | code only | docs example clears `ServerName` |
| `CaptureBlockingCalls` | - | bool; reports `Task.Wait()` / `Task.Result` in async code | blind spots in Gotchas |
| `IncludeActivityData` | - | opt-in; copies `System.Diagnostic.Activity` values | |
| `MinimumEventLevel` | - | Extensions.Logging; default `Error` | |
| `MinimumBreadcrumbLevel` | - | Extensions.Logging; default `Information` | |
| `InitializeSdk` | - | Extensions.Logging; initializes when a DSN is present unless `false` | |

## Product support matrix

| product | supported | notes |
|---|---|---|
| errors | yes | `UseSentry`; the core .NET SDK |
| tracing | yes | `TracesSampleRate` or `TracesSampler`; automatic instrumentation page under aspnetcore/tracing |
| profiling | unconfirmed | `platforms/dotnet/profiling` exists; research matrix says alpha, .NET 8+; not checked on the page |
| replay | no | `platforms/dotnet/session-replay` is Page Not Found; research matrix shows none |
| logs | yes | `platforms/dotnet/logs` exists (`SetBeforeSendLog`); the ASP.NET Core package carries the Extensions.Logging integration; version gate per research matrix, not checked on the page |
| metrics | yes | `platforms/dotnet/metrics`: `EnableMetrics`, `SetBeforeSendMetric` |
| crons | yes | `platforms/dotnet/crons`: check-ins, heartbeat, upserting monitors |
| feedback | yes | `platforms/dotnet/user-feedback`, including the crash-report modal |
| ai | experimental | `platforms/dotnet/tracing/instrumentation/ai-agents-module`: `Experimental.RecordInputs`, `Experimental.RecordOutputs`, `Experimental.AgentName` |
| flags | no | `platforms/dotnet/feature-flags` is Page Not Found; research matrix shows none |
| debug files | yes | MSBuild upload; see Release and artifacts |

## Release and artifacts

- Runtime release: the `Release` option, else the `SENTRY_RELEASE` env var. Docs: the SDK "will try to" configure one, but set it explicitly so it matches deploy integrations and symbol uploads. Check the Dockerfile and CI for it.
- Build-time release: `SentryCreateRelease` (default `false`). Version source order: `SENTRY_RELEASE`, then `AssemblyInformationalVersionAttribute`, then the entry-assembly version, then `sentry-cli releases propose-version`.
- Environment: default `production`; staging must set it.
- Symbols: the PDB the build already produces, uploaded as debug information files. `SentryUploadSymbols` and `SentryUploadSources` both default `false`. Upload needs `SentryOrg` and `SentryProject` (listed as required). `UseSentryCLI=false` disables the bundled CLI, so nothing uploads. Use `EmbedAllSources` or `SentryUploadSources`, not both.
- Gate uploads on Release: `'$(Configuration)' == 'Release'` (vendored `upstream/debug-artifacts/dotnet`; not stated on a docs page).
- Publish pipelines without MSBuild targets: `sentry-cli debug-files upload --include-sources <build-output>` (vendored reference).
- Auth: no token in the project file; use the CI secret store. The vendored reference discourages putting the token in MSBuild properties.
- Multi-stage Docker: publish with `--no-build --no-restore` and `-p:UseSentryCLI=false` (msbuild page).

## Privacy

| Data | default | control |
|---|---|---|
| user identity read from `HttpContext.User` | not sent | `SendDefaultPii`; custom mapping via `ISentryUserFactory` |
| request URL, headers, client IP | not sent | `SendDefaultPii` |
| request body | no default stated | `MaxRequestBodySize` (`None` keeps bodies out) |
| server name | no default stated | `SetBeforeSend` (docs example nulls `ServerName`) |
| other fields | | docs: remove what you do not want via the Sensitive Data features when `SendDefaultPii` is on |

## Verify recipe

1. In the real app, add a temporary route or action on an existing controller (fixture: `Controllers/HealthController.cs`). Catch an exception there and call `SentrySdk.CaptureException` with a marker such as `sentry-verify-<date>`; return 200.
2. Run the app with `SENTRY_DSN` set (or `Sentry:Dsn` in config) and `SENTRY_RELEASE` set to a known value. Call the route with curl on the app's port.
3. In Sentry, find the event by marker. Release must equal `SENTRY_RELEASE`; environment must match the run.
4. Tracing: the same request makes a transaction when `TracesSampleRate` is above 0.
5. Remove the route or action and the capture call, then `grep -rn "sentry-verify"` in the repo must return nothing.

## Gotchas

| Symptom | Cause | Fix / source |
|---|---|---|
| Fixture `Program.cs`: DSN literal at line 5, `TracesSampleRate` 1.0, `SendDefaultPii` true | example values copied into code | DSN from `SENTRY_DSN` or config; explicit sample rate; `SendDefaultPii` only with privacy sign-off (Configure, Dsn, SendDefaultPii) |
| Docs `appsettings.json` example sets `SendDefaultPii` true, `MaxRequestBodySize` `Always`, `TracesSampleRate` 1.0 | illustrative example, not a default | docs: "adjust this value in production" |
| Events show `production` in staging | no environment set; ASP.NET Core only falls back to `IHostingEnvironment` | set `Environment`, the env var (see Unconfirmed), or config |
| Release missing or wrong | `SENTRY_RELEASE` unset and `SentryCreateRelease` is `false` | set the env var in the deploy; enable `SentryCreateRelease` to create at build |
| Frames show method names but no file or line | `SentryUploadSymbols` defaults to `false` | set true for Release builds (vendored reference) |
| Multi-stage Docker publish fails at Sentry CLI | publish reruns the build without the token | `--no-build --no-restore`; the research note names `-p:UseSentryCLI=false` alone, but docs make `--no-build --no-restore` the fix and `UseSentryCLI=false` a safeguard |
| Two init sites (`UseSentry` and `SentrySdk.Init`) | SDK is meant to start once | keep one; `InitializeSdk` false if you call `SentrySdk.Init` yourself |
| Blocking calls not reported | `CaptureBlockingCalls` skips `ConfigureAwait(false)` cases, syscalls such as `File.Read`, and precompleted tasks | docs caveat list; silence is not proof of no blocking |
| Warning-level logs never become events | `MinimumEventLevel` defaults to `Error` | expected: warnings stay breadcrumbs (`MinimumBreadcrumbLevel` `Information`) |
| Path `aspnetcore/performance` not found | the page does not exist | use the automatic-instrumentation page |

## Sources
- https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
- https://docs.sentry.io/platforms/dotnet/configuration/options/
- https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
- https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
- https://docs.sentry.io/platforms/dotnet/logs/
- https://docs.sentry.io/platforms/dotnet/metrics/
- https://docs.sentry.io/platforms/dotnet/crons/
- https://docs.sentry.io/platforms/dotnet/user-feedback/
- https://docs.sentry.io/platforms/dotnet/profiling/
- https://docs.sentry.io/platforms/dotnet/tracing/instrumentation/ai-agents-module/
- https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/tracing/instrumentation/automatic-instrumentation/

## Identifiers
```identifiers
UseSentry | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
Sentry.AspNetCore | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
appsettings.json | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
WebApplication.CreateBuilder | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
IHostBuilder | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
IWebHost | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
MaxRequestBodySize | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
CaptureBlockingCalls | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
IncludeActivityData | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
System.Diagnostic.Activity | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
ISentryUserFactory | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
HttpContext.User | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
SentrySdk.CaptureException | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
EnableRewind | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
SetBeforeSend | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
ServerName | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
Task.Wait() | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
SendDefaultPii | https://docs.sentry.io/platforms/dotnet/configuration/options/
Dsn | https://docs.sentry.io/platforms/dotnet/configuration/options/
TracesSampleRate | https://docs.sentry.io/platforms/dotnet/configuration/options/
TracesSampler | https://docs.sentry.io/platforms/dotnet/configuration/options/
Release | https://docs.sentry.io/platforms/dotnet/configuration/options/
Environment | https://docs.sentry.io/platforms/dotnet/configuration/options/
IHostingEnvironment | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
ConfigureWebHostDefaults | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
SENTRY_RELEASE | https://docs.sentry.io/platforms/dotnet/configuration/options/
SENTRY_DSN | https://docs.sentry.io/platforms/dotnet/configuration/options/
SentrySdk.Init | https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
AddSentry | https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
MinimumEventLevel | https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
MinimumBreadcrumbLevel | https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
InitializeSdk | https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
TagFilters | https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
Microsoft.Extensions.Logging | https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
Sentry.Extensions.Logging | https://docs.sentry.io/platforms/dotnet/guides/extensions-logging/
SentryUploadSymbols | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryUploadSources | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryCreateRelease | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryOrg | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SentryProject | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
UseSentryCLI | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
AssemblyInformationalVersionAttribute | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
EmbedAllSources | https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
SetBeforeSendLog | https://docs.sentry.io/platforms/dotnet/logs/
EnableMetrics | https://docs.sentry.io/platforms/dotnet/metrics/
SetBeforeSendMetric | https://docs.sentry.io/platforms/dotnet/metrics/
Experimental.RecordInputs | https://docs.sentry.io/platforms/dotnet/tracing/instrumentation/ai-agents-module/
Experimental.RecordOutputs | https://docs.sentry.io/platforms/dotnet/tracing/instrumentation/ai-agents-module/
Experimental.AgentName | https://docs.sentry.io/platforms/dotnet/tracing/instrumentation/ai-agents-module/
```

## Unconfirmed
- `Sentry.Extensions.AI`: appears only in the research matrix; not on any page fetched on 2026-10-20. Verify before use.
- `SENTRY_ENVIRONMENT`: the options page names it only in escaped markdown; verify on platforms/dotnet/configuration/options before use.
- `SENTRY_AUTH_TOKEN`: vendored reference only; not on a fetched docs page.
