# Go (module: platforms/go)

Applies to `sentry-go` 0.x (stable, 0.50.0 on 2026-10-20). The repo's CHANGELOG also carries a `1.0.0-alpha.1` entry (unreleased,
needs Go 1.26+) that removes the Hub API; it is called out below, not recommended. Framework modules (gin, echo, fiber, iris,
negroni, fasthttp) add to this one.

## Detect

| Signal | Where | Means |
|---|---|---|
| `github.com/getsentry/sentry-go` (+ `/gin`, `/echo`, `/fiber`, `/http`, `/slog`, `/zap`, `/logrus`, `/cron`) | go.mod, go.sum | SDK and which integration sub-modules are present; the go.mod version gives the real minor |
| `github.com/getsentry/raven-go` | go.mod | legacy SDK, replaced by sentry-go |
| `sentry.Init(` | `*.go` (usually `main.go`, `cmd/*/main.go`) | init site; more than one `main` package = more than one init |
| `sentrygin.New(`, `sentryecho.New(`, `sentryfiber.New(`, `sentryhttp.New(` | router setup | per-request hub middleware |
| `robfig/cron`, `time.Ticker`, `os.Args` job runners | go.mod, code | scheduled work and short-lived processes (crons, Flush rows below) |
| `-ldflags` in Dockerfile / Makefile / CI | build files | release injection; absent `.git` in the image = no automatic release |

Library-only modules (no `package main`) do not initialize Sentry.

## Install route

No wizard integration for Go: manual from the live page. `sentry-ctx docs page platforms/go` and
`sentry-ctx docs page platforms/go/guides/<gin|echo|fiber|http|iris|negroni|fasthttp>`; logs integrations under
`platforms/go/logs/<slog|zap|logrus>`. Each integration is its own `go get` sub-package.

## Init placement

| Place | Rule |
|---|---|
| `main()` | `sentry.Init(sentry.ClientOptions{...})` first, check the returned error, before routers, cron, DB pools or goroutines |
| Long-running server | `defer sentry.Flush(...)` right after Init (docs use a 2 second timeout) |
| CLI / job / lambda-like process | `Flush` before every exit path. `os.Exit` and `log.Fatal` skip deferred calls, so flush explicitly before them; serverless: `Flush` or swap to `HTTPSyncTransport` |
| Goroutine started from a handler | never the global `sentry.CaptureMessage`; use a cloned hub (`CurrentHub().Clone()`) passed as an argument |

Per-request hub (0.x): the integration middleware attaches a `*sentry.Hub` to the request context. "`*sentry.Hub` won't be available
in middleware attached before" the sentry one, so register the sentry middleware first, then middleware that needs the hub.

| Framework | Middleware | Hub accessor | Notes |
|---|---|---|---|
| Gin | `sentrygin.New(sentrygin.Options{...})` via `Use` | `sentrygin.GetHubFromContext(c)` | `Repanic: true` because `gin.Default` has its own Recovery |
| Echo | `sentryecho.New(sentryecho.Options{...})` | `sentryecho.GetHubFromContext(c)` | `Repanic: true` since Echo's Recover renders the response |
| Fiber | `sentryfiber.New(sentryfiber.Options{...})` | `sentryfiber.GetHubFromContext(c)` | separate guide for Fiber v3 (`platforms/go/guides/fiberv3`) |
| net/http | `sentryhttp.New(sentryhttp.Options{...})` then `.Handle` / `.HandleFunc` | `sentry.GetHubFromContext(r.Context())` | wrap every route or the mux, not just one |

All take `Repanic`, `WaitForDelivery` (keep `false` unless the process restarts after a panic), `Timeout`. Docs: use the request hub
"instead of the global" capture calls, otherwise scope data bleeds between requests.

## Options by SDK major

| option | 0.x (0.50.0) | 1.0.0-alpha.1 (unreleased) | note |
|---|---|---|---|
| `Dsn` | falls back to `SENTRY_DSN`; no DSN = nothing sent | unchanged in CHANGELOG | |
| `SendDefaultPII` | default `false`; deprecated | no change listed | `true` behaves like enabling all `DataCollection` categories |
| `DataCollection` | `*sentry.DataCollection`, since 0.48.0; `&sentry.DataCollection{}` opts into MORE permissive defaults; takes precedence over `SendDefaultPII` | no change listed | set every field from the privacy answers |
| `EnableTracing` | default `false`; docs examples pair it with `TracesSampleRate` | no change listed | `TracesSampler` wins if both set |
| `TracesSampleRate` | default `0.0` | no change listed | |
| `TraceIgnoreStatusCodes` | 404 ignored by default; empty non-nil slice allows all | no change listed | |
| `TracePropagationTargets` | `[]string`, no regex | no change listed | |
| `Release` / `Environment` | derived from env or git when unset / `SENTRY_ENVIRONMENT` | no change listed | |
| `BeforeSend` | `func(*Event, *EventHint) *Event` | `EventModifier` helpers removed; use `BeforeSend` | |
| `BeforeSendLog` | since logs (0.33.0) | no change listed | |
| `DisableTelemetryBuffer` | exists | removed (buffer always on) | |
| Hub API | `GetHubFromContext`, `CurrentHub().Clone()` | removed: contexts carry scope/client, capture calls take a context | breaking for every framework integration |

## Product support matrix

| product | supported | notes |
|---|---|---|
| Errors | yes | `CaptureException` unwraps error chains; panics via `Recover` / middleware |
| Tracing | yes (SDK >= 0.9.0) | needs `EnableTracing` + a sample rate; middleware creates transactions; OpenTelemetry bridge exists |
| Logs | yes (>= 0.33.0), on by default | `sentry.NewLogger(ctx)`; slog (>= 0.34.0), zap, logrus; Zerolog is error events only, no structured logs |
| Metrics | yes (>= 0.42.0) | |
| Crons | yes (>= 0.23.0) | `sentry.WithMonitor` and `sentrycron.AddFunc` for robfig/cron need >= 0.50.0; else `CaptureCheckIn` |
| Profiling, Session Replay, User Feedback | no Go page in the docs (the `platforms/go/<product>` URLs return Page Not Found on 2026-10-20; the Topics list has none) | treat as unsupported; do not propose |
| AI / agent tracing | no Go page in the docs | not proposed |

Default integrations: `ModulesIntegration`, `EnvironmentIntegration`, `IgnoreErrorsIntegration`, `IgnoreTransactionsIntegration`,
`GlobalTagsIntegration`; trim with the `Integrations` option.

## Release and artifacts

- Release: when `Release` is unset the SDK derives it from environment variables or the git repo in the working directory. For a
  distributed binary set it at build time (docs): `go build -ldflags='-X main.release=VALUE'`, then pass it as `Release`. Container
  runtime images (distroless, scratch) have no `.git`, so a missing `-ldflags` means no release. Use the git SHA or
  `mypackage@version`; the CI step passes the same string to `sentry release create` / `set-commits --auto` / `deploy`.
- `Environment` is not set by default (reads `SENTRY_ENVIRONMENT`); the DSN is not a place to encode it.
- No symbol, source-map or debug-file upload for Go. Source lines come from SCM Source Context (SCM integration + code
  mappings + enabled per project), not from the SDK or CI; missing source context is a project setting, not a build step.

## Privacy

| Data | Without `DataCollection` (`SendDefaultPII` false) | With `DataCollection` set |
|---|---|---|
| user info / IP | off (`Scope.SetUser` data always sent) | `UserInfo` default `sentry.Set(true)` |
| cookies | not collected | `Cookies`: denylist mode (sensitive values scrubbed) |
| headers | collected with legacy filtering | `HTTPHeaders`: request and response, denylist |
| bodies | not collected | `HTTPBodies`: all body types |
| query string | legacy behaviour | `QueryParams`: denylist |

`X-Forwarded-For` can still carry IPs: add denylist terms to headers, cookies and query params. Under `DataCollection`, restrict
bodies by passing an empty slice. `Debug: true` prints SDK output; keep it off in production.

## Verify recipe

R2: temporary route (or a one-shot flag on the real binary) that takes the request hub, calls `hub.WithScope` + `SetTag("plugin_marker",
...)` + `hub.CaptureMessage(...)` and then `sentry.Flush(...)`. For a worker or cron path, trigger the real job once with a
marker tag. Use a non-production `Environment`; remove the route afterwards. Cron: call the wrapped job and watch the check-in.

## Gotchas

| Symptom | Cause | Source |
|---|---|---|
| Events lost on exit | async transport; `os.Exit`/`log.Fatal` skip `defer sentry.Flush` | usage, serverless pages |
| Request data on the wrong event | global capture calls instead of the request hub, or a goroutine sharing the hub | concurrency page |
| Hub nil in a handler | sentry middleware registered after the middleware reading the hub | gin/echo/fiber/http guides |
| `slog.SetDefault(...)` with a JSON handler | records never reach Sentry; the `sentryslog` handler must be added (fan-out section) | slog page |
| `robfig/cron` jobs unmonitored | cron library is not instrumented by default | crons page |
| Cron monitor not created | specs Sentry cannot express (`@every` under a minute) send check-ins only; non-IANA local TZ also | crons page |
| 404 transactions missing | `TraceIgnoreStatusCodes` ignores 404 by default | options page |
| Zerolog logs absent from Logs | Zerolog sends error events only | logs page |

## Sources
- https://docs.sentry.io/platforms/go/
- https://docs.sentry.io/platforms/go/configuration/options/
- https://docs.sentry.io/platforms/go/guides/gin/ (and echo, fiber, http siblings)
- https://docs.sentry.io/platforms/go/usage/ , .../usage/concurrency/ , .../usage/panics/ , .../usage/serverless/
- https://docs.sentry.io/platforms/go/logs/ , .../logs/slog/ , .../logs/zap/ , .../logs/logrus/
- https://docs.sentry.io/platforms/go/crons/ , .../tracing/ , .../source-context/ , .../integrations/
- https://docs.sentry.io/platforms/go/data-management/data-collected/
- https://github.com/getsentry/sentry-go/blob/master/CHANGELOG.md

## Identifiers
```identifiers
SendDefaultPII | https://docs.sentry.io/platforms/go/configuration/options/
DataCollection | https://docs.sentry.io/platforms/go/configuration/options/
EnableTracing | https://docs.sentry.io/platforms/go/configuration/options/
TracesSampleRate | https://docs.sentry.io/platforms/go/configuration/options/
TracesSampler | https://docs.sentry.io/platforms/go/configuration/options/
TraceIgnoreStatusCodes | https://docs.sentry.io/platforms/go/configuration/options/
TracePropagationTargets | https://docs.sentry.io/platforms/go/configuration/options/
BeforeSend | https://docs.sentry.io/platforms/go/configuration/options/
DisableTelemetryBuffer | https://docs.sentry.io/platforms/go/configuration/options/
UserInfo | https://docs.sentry.io/platforms/go/configuration/options/
QueryParams | https://docs.sentry.io/platforms/go/configuration/options/
BeforeSendLog | https://docs.sentry.io/platforms/go/logs/
WaitForDelivery | https://docs.sentry.io/platforms/go/guides/gin/
GetHubFromContext | https://docs.sentry.io/platforms/go/guides/gin/
CaptureException | https://docs.sentry.io/platforms/go/usage/
CaptureCheckIn | https://docs.sentry.io/platforms/go/crons/
EventModifier | https://github.com/getsentry/sentry-go/blob/master/CHANGELOG.md
ModulesIntegration | https://docs.sentry.io/platforms/go/integrations/
EnvironmentIntegration | https://docs.sentry.io/platforms/go/integrations/
IgnoreErrorsIntegration | https://docs.sentry.io/platforms/go/integrations/
IgnoreTransactionsIntegration | https://docs.sentry.io/platforms/go/integrations/
GlobalTagsIntegration | https://docs.sentry.io/platforms/go/integrations/
```

## Unconfirmed
- `profiling`, `replay`, `feedback`: unsupported status is inferred from missing Go docs pages and Topics entries (checked 2026-10-20), not from an explicit "not supported" statement; re-check before telling a user a feature is impossible.
- `1.0.0-alpha.1`: described only through the master CHANGELOG; "no change listed" cells mean the CHANGELOG is silent, not that the option is unchanged.
- `sentryfiber`: the Fiber v3 guide (`platforms/go/guides/fiberv3`) was not read; package names and accessors for v3 are unverified.
