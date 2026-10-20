# Elixir and Phoenix (module: platforms/elixir)

## Detect

| Signal | Where | Means |
|---|---|---|
| `{:sentry,` | mix.exs, mix.lock | SDK dependency; the lock gives the real version (docs current line: 14.x) |
| `phoenix` in deps | mix.exs | Phoenix app; framework id `phoenix` is served by this module |
| `config :sentry` | config/config.exs, config/prod.exs, config/runtime.exs | DSN, environment and integrations are read here |
| `use Sentry.PlugCapture`, `plug Sentry.PlugContext` | endpoint.ex, router.ex | Plug wiring |
| `on_mount Sentry.LiveViewHook` | LiveView quote in the `*_web.ex` module | LiveView hook |
| `oban:` or `quantum:` under `integrations` | config files | scheduled-job check-ins (crons row) |

Fixture `evals/fixtures/elixir-phoenix`: engine detects Phoenix 1.7.14 from mix.exs, `config :sentry,` at config/config.exs:7, `use Sentry.PlugCapture` at lib/my_app_web/endpoint.ex:3, and `SENTRY_DSN` read at config/config.exs:8.

## Install route

Manual only. The Elixir landing page documents Install, Configure and Verify; it names no wizard and no `sentry init` route. Audit against the Install block: `sentry-ctx docs page platforms/elixir --section Install`. It lists `{:sentry, "~> 14.0.0"}` and `{:jason, "~> 1.1"}`, plus `{:hackney, "~> 1.8"}` only when the default HTTP client is used.

## Init placement

| Where | What | Source |
|---|---|---|
| config/config.exs or config/runtime.exs | `config :sentry` with `dsn`; load before the app starts | landing Configure ("as early as possible"); logs page names both files |
| endpoint.ex | `use Sentry.PlugCapture` above `use Phoenix.Endpoint` (Cowboy only); `plug Sentry.PlugContext` below `plug Plug.Parsers` | plug_and_phoenix, Phoenix Configuration |
| `*_web.ex`, `live_view` quote | `on_mount Sentry.LiveViewHook` (SDK 10.5.0 or higher) | plug_and_phoenix |
| Plain Plug router | `use Sentry.PlugCapture` at top; `plug Sentry.PlugContext` below `Plug.Parsers` | plug_and_phoenix, Plug Configuration |
| application.ex | OpenTelemetry setup, only when tracing is on; LiveView propagator before `OpentelemetryPhoenix.setup` | tracing |

`SENTRY_DSN` is read when `dsn` is unset (options page). A DSN in config plus the env var is not a conflict.

## Options by SDK major

Only the 14.x docs were fetched and no prior-major column is stated, so v(N-1) is `n/a` throughout.

| option | v(N-1) | v(N) | note |
|---|---|---|---|
| `dsn` | n/a | 14.x | unset: read from `SENTRY_DSN` |
| `release` | n/a | 14.x | unset: read from `SENTRY_RELEASE` |
| `environment` | n/a | 14.x | freeform, "not set by default"; unset: `SENTRY_ENVIRONMENT` |
| `environment_name` | n/a | 14.x | landing Configure example only, not on the options page (see Gotchas) |
| `enable_source_code_context` | n/a | 14.x | landing Configure example sets `true`; no options-page entry |
| `root_source_code_paths` | n/a | 14.x | landing Configure example |
| `before_send` | n/a | 14.x | event callback (Hooks section); filtering page for patterns |
| `traces_sample_rate` | n/a | 14.x | Tracing Options section |
| `logs` | n/a | 14.x | keys `level` (default nil: no logs sent), `excluded_domains` (default `[]`), `metadata` (default `[]`) |
| `before_send_log` | n/a | 14.x | logs page, Options |
| `before_send_metric` | n/a | 14.x | metrics page, Options |
| `integrations` | n/a | 14.x | `oban: [capture_errors: true, cron: [enabled: true]]`; `quantum: [cron: [enabled: true]]` |

## Product support matrix

| product | supported | notes |
|---|---|---|
| errors | yes (GA) | `Sentry.capture_exception` in the Verify block; PlugCapture is documented for Cowboy only |
| tracing | beta (research matrix, >= 11.0) | OpenTelemetry route: `OpentelemetryPhoenix.setup`; endpoint needs `Plug.Telemetry` |
| profiling | unconfirmed | matrix shows no page for Elixir (its dash means "no page"); no profiling page fetched |
| replay | unconfirmed | matrix dash (no page) |
| logs | yes | `logs` config with `level`; handler auto-attached; version claim conflicts (see Gotchas) |
| metrics | yes (GA >= 13.0 per matrix) | `before_send_metric`; counter, distribution and gauge usage on the page |
| crons | yes | automatic check-ins for Oban and Quantum; manual Check-Ins (recommended) and Heartbeats |
| feedback | yes | crash-report modal; `Sentry.get_last_event_id_and_source` returns the event id |
| ai | unconfirmed | matrix dash (no page) |
| flags | unconfirmed | matrix dash (no page) |
| debug files | unconfirmed | no debug-file or symbol page fetched; source context is config only (see Release) |

## Release and artifacts

- Release string: the `release` option, set explicitly in `config :sentry` (releases page example `myapp@1.0.0`). Unset falls back to `SENTRY_RELEASE`. The releases page says how the name reaches the code is up to you, and no derivation from git or a hosting provider is documented for Elixir, so an unset value means no release tag. Audit: the value should come from the same source the deploy uses.
- Source context: no upload step. Config sets `enable_source_code_context: true` and `root_source_code_paths` (landing Configure). Right means the flag is on in the build that ships.
- Debug files, symbols and source maps: none documented for Elixir on the fetched pages. Do not expect a CI upload step. The packaging task in the research notes is unconfirmed (see Unconfirmed).

## Privacy

| Data | Leaves by default | Control |
|---|---|---|
| Source lines around frames | when `enable_source_code_context` is true (the docs' example sets it) | the option; the docs do not define `root_source_code_paths` further |
| Log entries | only when `logs` has a `level`; only metadata keys listed in `metadata` | `level`, `metadata`, `excluded_domains`, `before_send_log` |
| Metric events | when metrics are emitted | `before_send_metric` |
| Every event | yes | `before_send` can drop or edit it |
| Oban job | the job struct is attached as `integration_meta` | check what `before_send` keeps (Oban page) |
| Default PII | not stated on the fetched pages | none documented |

## Verify recipe

1. Add a temporary route in router.ex (for example `get "/sentry-verify"`) to a temporary controller action that raises `"sentry-verify <token>"`, where `<token>` is unique. The request then runs through Plug.Parsers, Sentry.PlugContext and the endpoint, which is the real path.
2. Call the route with curl against the running app. Find the error with the token in the project's Issues, and check that its environment and release match the config.
3. The adapter matters. PlugCapture is documented for Cowboy only; for Bandit, put the Verify snippet inside the action instead: `try do raise ... rescue exception -> Sentry.capture_exception(exception, stacktrace: __STACKTRACE__) end` (landing Verify).
4. Remove: delete the route, the action and the temporary code, then grep for the token and confirm none is left.

## Gotchas

- `environment` vs `environment_name`: the landing Configure example uses `environment_name: Mix.env()`, but the options page documents `environment` (env `SENTRY_ENVIRONMENT`). Expect `environment`. Where the two disagree, the options page wins; a repo using `environment_name` needs checking against the pinned 14.x SDK.
- PlugCapture is documented for Cowboy only. Check the endpoint adapter in mix.lock before flagging a missing `Sentry.PlugCapture`. The tracing page uses `OpentelemetryBandit` for Bandit.
- Plug order: `Sentry.PlugContext` below `Plug.Parsers`; `use Sentry.PlugCapture` above `use Phoenix.Endpoint`. Wrong order is a finding.
- LiveView hook needs SDK 10.5.0 or higher (plug_and_phoenix). Current SDK is 14.x, so it is present whenever the hook is used.
- Logs: a `logs` block without `level` still attaches the handler, so crashes report as errors but no logs are sent. Registering your own `Sentry.LoggerHandler` removes the auto-attached one (logs page).
- Logs version conflict: the research matrix says GA >= 12–14 and flags a docs conflict. The logs page states no minimum version, so do not cite one.
- Oban: unhandled crashes are wrapped in `Oban.CrashError`; error results surface as `Oban.PerformError`. Filter in `before_send` (Oban page), not by removing the integration.
- Tracing: the endpoint needs `plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]`. `Sentry.OpenTelemetry.LiveViewPropagator.setup()` must run before `OpentelemetryPhoenix.setup` (tracing page).
- Cron check-ins: the crons page documents automatic check-ins for Oban and Quantum only; the Manual Setup section covers other schedulers.

## Sources

- https://docs.sentry.io/platforms/elixir/ (Install, Configure, Verify)
- https://docs.sentry.io/platforms/elixir/configuration/options/
- https://docs.sentry.io/platforms/elixir/configuration/releases/
- https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
- https://docs.sentry.io/platforms/elixir/integrations/oban/
- https://docs.sentry.io/platforms/elixir/logs/
- https://docs.sentry.io/platforms/elixir/crons/
- https://docs.sentry.io/platforms/elixir/tracing/
- https://docs.sentry.io/platforms/elixir/metrics/
- https://docs.sentry.io/platforms/elixir/user-feedback/
- https://docs.sentry.io/platforms/elixir/usage/

## Identifiers

```identifiers
dsn | https://docs.sentry.io/platforms/elixir/configuration/options/
release | https://docs.sentry.io/platforms/elixir/configuration/options/
environment | https://docs.sentry.io/platforms/elixir/configuration/options/
before_send | https://docs.sentry.io/platforms/elixir/configuration/options/
traces_sample_rate | https://docs.sentry.io/platforms/elixir/configuration/options/
SENTRY_DSN | https://docs.sentry.io/platforms/elixir/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/elixir/configuration/options/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/elixir/configuration/options/
environment_name | https://docs.sentry.io/platforms/elixir/
enable_source_code_context | https://docs.sentry.io/platforms/elixir/
root_source_code_paths | https://docs.sentry.io/platforms/elixir/
Sentry.capture_exception | https://docs.sentry.io/platforms/elixir/
__STACKTRACE__ | https://docs.sentry.io/platforms/elixir/
hackney | https://docs.sentry.io/platforms/elixir/
Sentry.PlugCapture | https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
Sentry.PlugContext | https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
Sentry.LiveViewHook | https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
Sentry.get_last_event_id_and_source | https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
Plug.Parsers | https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
Phoenix.Endpoint | https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
on_mount | https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
live_view | https://docs.sentry.io/platforms/elixir/integrations/plug_and_phoenix/
logs | https://docs.sentry.io/platforms/elixir/logs/
level | https://docs.sentry.io/platforms/elixir/logs/
metadata | https://docs.sentry.io/platforms/elixir/logs/
excluded_domains | https://docs.sentry.io/platforms/elixir/logs/
before_send_log | https://docs.sentry.io/platforms/elixir/logs/
Sentry.LoggerHandler | https://docs.sentry.io/platforms/elixir/logs/
sentry_log_handler | https://docs.sentry.io/platforms/elixir/logs/
before_send_metric | https://docs.sentry.io/platforms/elixir/metrics/
integrations | https://docs.sentry.io/platforms/elixir/crons/
oban | https://docs.sentry.io/platforms/elixir/integrations/oban/
capture_errors | https://docs.sentry.io/platforms/elixir/integrations/oban/
cron | https://docs.sentry.io/platforms/elixir/crons/
quantum | https://docs.sentry.io/platforms/elixir/crons/
Oban.CrashError | https://docs.sentry.io/platforms/elixir/integrations/oban/
Oban.PerformError | https://docs.sentry.io/platforms/elixir/integrations/oban/
integration_meta | https://docs.sentry.io/platforms/elixir/integrations/oban/
Plug.Telemetry | https://docs.sentry.io/platforms/elixir/tracing/
event_prefix | https://docs.sentry.io/platforms/elixir/tracing/
OpentelemetryPhoenix.setup | https://docs.sentry.io/platforms/elixir/tracing/
OpentelemetryBandit | https://docs.sentry.io/platforms/elixir/tracing/
Sentry.OpenTelemetry.LiveViewPropagator | https://docs.sentry.io/platforms/elixir/tracing/
```

## Unconfirmed

- `mix sentry.package_source_code`: the research notes say run it before `mix release`; no fetched official page confirms it.
- `Sentry.Logger`: the research notes call it the old backend (unverified); no fetched official page covers it.
- Debug-file, symbol and source-map upload for Elixir: no official page fetched.
- Profiling, replay, AI monitoring and feature-flag support: the research matrix shows no page; not confirmed by docs.
