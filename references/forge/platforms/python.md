# Python (module: platforms/python)

Applies to `sentry-sdk` 2.x (stable, 2.72.0 on 2026-10-20) and calls out the 3.0 alpha. Framework modules (django, fastapi, flask,
celery, ...) add to this one. Removed/renamed 3.0 names are in data/stale-apis/python.tsv: believe those rows.

## Detect

| Signal | Where | Means |
|---|---|---|
| `sentry-sdk` / `sentry-sdk[fastapi]` | pyproject.toml, requirements*.txt, Pipfile, uv.lock, poetry.lock | SDK installed; the lockfile gives the real major (2 vs 3) |
| `sentry_sdk.init(` or `init_sentry(` | `*.py` | the init site(s); more than one is normal for Celery (app + worker), a problem elsewhere |
| `DjangoIntegration`, `LoggingIntegration(level=..., event_level=...)`, `_experiments={...}` | init call | 2.x idioms: read them against the options table below |
| `celery`, `apscheduler`, `@monitor`, `monitor_beat_tasks` | deps and code | scheduled work (crons row below); `raven` = legacy SDK |
| uWSGI config (`--enable-threads`, `--py-call-uwsgi-fork-hooks`) | Dockerfile, uwsgi.ini, Procfile | threading flags, see Gotchas |

Library-only repos (no app entrypoint) do not initialize Sentry: report and move on.

## Install route

No wizard integration for Python. Use `sentry init` (hosted, experimental) only for a new project, then audit its output; otherwise
manual from the live page: `sentry-ctx docs page platforms/python`, framework pages
`sentry-ctx docs page platforms/python/integrations/<django|flask|fastapi|starlette|celery>`.

## Init placement

Docs: "as early as possible"; env fallbacks `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_RELEASE`.

| Framework | Where `sentry_sdk.init()` goes | Evidence / note |
|---|---|---|
| Django | `settings.py` (docs) | Celery+Django with `config_from_object` needs no second init |
| Flask | app entry point, before requests; plugin convention: above `Flask(__name__)` | docs: integration hooks Flask signals, not the app object, so order vs the app object is not fatal |
| FastAPI / Starlette | app entry point; plugin convention: above `FastAPI()` / `Starlette()` | integration auto-enables when `fastapi` / `starlette` is installed |
| Celery without Django | `celeryd_init` signal handler (worker daemon) AND the producing application process | `worker_init` instead if each worker process needs its own init |
| Celery beat | `beat_init` and `celeryd_init` when beat is a separate process; either when `-B` | init loaded on worker startup, not only where tasks are defined |
| Plain script / asyncio | top of the entry module (asyncio: inside the first `async` function); exit normally | atexit integration flushes; `shutdown_timeout=0` disables the wait |

Two init sites in one process, or init inside a task module only, are findings. Init in a worker but never in the web process
(or the reverse) loses half the trace.

## Options by SDK major

| option | 2.x (2.72.0) | 3.0 (alpha) | note |
|---|---|---|---|
| `send_default_pii` | default `None`; supported | removed | replaced by `data_collection` |
| `data_collection` | `dict`, default `None`; opting in is MORE permissive than `send_default_pii=False`; if both set, `send_default_pii` is ignored with a DeprecationWarning | the only control; defaults permissive | set every key from the privacy answers |
| `include_local_variables` | default `True` | removed | use `stack_frame_variables` |
| `include_source_context` | default `True` | removed | use `frame_context_lines` (default `5`) |
| `event_scrubber` | runs only when `data_collection` is undefined | removed | use `data_collection` and `before_send` |
| `enable_tracing` | not on the 2.x options page | removed | set `traces_sample_rate` |
| `traces_sample_rate` | default `None`; `0` still continues incoming traces, `None` disables tracing | same | needs a deliberate value |
| `trace_lifecycle` | since 2.62.0; `"static"` default, `"stream"` opt-in | option gone, stream is the only mode | |
| `before_send_transaction` | supported | removed | use `before_send_span` |
| `profiles_sample_rate` | deprecated (legacy; not available in stream mode) | removed | continuous: `profile_session_sample_rate` + `profile_lifecycle` |
| `enable_logs` | default `False`, deprecated since 2.68.1 | removed (logs work without it) | |
| `attach_stacktrace` | default `False` | default `True` | changes grouping |
| `transaction_style` | per web integration | removed | |
| `include_prompts` | per AI integration, default `True` | removed | use `gen_ai` key of `data_collection` |
| `trace_propagation_targets` | default `['.*']` | same | narrow it when third-party hosts are called |

3.0 alpha needs Python 3.7+ (migration page) and self-hosted Sentry 26.4.2+. The 3.0 logging integrations are not auto-enabled.

## Product support matrix

| product | 2.x | 3.0 alpha | notes |
|---|---|---|---|
| Errors | yes | yes | `data_collection` / `send_default_pii` decide user, headers, bodies |
| Tracing | yes | yes | 2.x transactions (or `trace_lifecycle="stream"`); 3.0 span streaming only |
| Profiling | continuous since 2.24.1; legacy transaction-based deprecated | continuous only | needs `profile_session_sample_rate` non-zero; `profile_lifecycle` is `manual` or `trace` |
| Logs | `sentry_sdk.logger` standalone; stdlib capture needs `capture_sentry_logs` (or deprecated `enable_logs`) on the integration | logging integration must be added to `integrations`; sends logs and breadcrumbs, no events unless `event_level` set | see Gotchas |
| Metrics | yes ("always enabled" on the guide) | `enable_metrics` removed | |
| Crons | `@monitor` decorator / context manager, `capture_checkin`, Celery beat auto-discovery | same | `monitor_beat_tasks` + decorator on one task = double monitoring |
| AI / agents | auto-enabled: Anthropic, OpenAI, OpenAI Agents, LangChain, LangGraph, Google GenAI, Hugging Face Hub, Pydantic AI, MCP; not auto: LiteLLM, Mistral, TypeSafe AI | prompts collected by default | `stream_gen_ai_spans` default `True` since 2.64.0; set `False` for self-hosted |

Integrations auto-enable when the library is importable (Django, Flask, FastAPI, Starlette, Celery, Redis, SQLAlchemy, ...);
`disabled_integrations`, `auto_enabling_integrations`, `default_integrations` switch them off. `default_integrations=False`
also disables auto-enabling ones. 3.0 adds `UnraisablehookIntegration` by default.

## Release and artifacts

- `release`: SDK order is `SENTRY_RELEASE`, then git SHA of the latest commit, then hosting-provider env (`HEROKU_SLUG_COMMIT`,
  `SOURCE_VERSION`, `CIRCLE_SHA1`, ...). Recommended shape `mypackage@1.0.0`; max 200 chars, no `/` or `\`. A container build
  without `.git` and without `SENTRY_RELEASE` ends up with no release: check the Dockerfile and CI.
- `environment` defaults to `production`; staging/dev must set it.
- No source-map or symbol upload for pure Python: source context travels with the event (`frame_context_lines`, 2.x
  `include_source_context`). Native extensions would need debug files (see the native module, not this one).
- Optional CI: `sentry release create`, `release set-commits <org>/<version> --auto`, `release finalize`, `release deploy`
  (cli.md).

## Privacy

| Data | 2.x default (`data_collection` undefined) | 3.0 / `data_collection` set |
|---|---|---|
| user id/email/IP | not sent unless `send_default_pii=True` | `user_info` default `True` |
| cookies, request headers, query params | cookies off; headers filtered; query string sent | `cookies`, `http_headers`, `url_query_params`: mode `denylist` by default; `"off"` / `"allowlist"` available |
| request/outgoing bodies | size-gated by `max_request_body_size` | `http_bodies` default both types |
| LLM prompts/outputs | off | `gen_ai` inputs/outputs both `True` |
| SQL, queue messages, GraphQL | SQL values never sent (parameterized query only); page gives no 2.x default for queues/GraphQL | `database_query_data`, `queues`, `graphql` default `True` |
| local variables | sent (`include_local_variables`) | `stack_frame_variables` default `True`, no scrubbing in 3.0 |

Fixture pattern to flag: `send_default_pii=True` plus `include_local_variables=True` plus AI integration = prompts and variables
leave the process. Under `data_collection`, user IPs can still arrive via `X-Forwarded-For` unless denylisted.

## Verify recipe

R2: add a temporary route/management command/task in the real app (never a side script, it skips the init under test) that
calls `sentry_sdk.set_tag("plugin_marker", "<run-id>-1")` then `sentry_sdk.capture_message(...)`. Short-lived jobs rely on the
atexit integration to flush. Run with a non-production `environment`, then `sentry-ctx verify wait --marker ...`. Remove the
trigger afterwards. For Celery send the marker from a task AND from the producer. Do not verify from IPython (not captured).

## Gotchas

| Symptom | Cause | Source |
|---|---|---|
| Worker events missing | init only in web process, or only imported by task modules | celery page |
| Every INFO log becomes an issue | 2.x `LoggingIntegration(event_level=logging.INFO)`; default `event_level` is `ERROR`, `level` default `INFO` is the breadcrumb threshold | logging page |
| Logs missing in 2.x | `capture_sentry_logs` unset and `enable_logs` unset: stdlib capture is off | options page |
| After upgrade to 3.0 no log events | integrations not auto-enabled; `level` renamed `breadcrumb_level`, `sentry_logs_level` renamed `level`; add `event_level` | migration page |
| Duplicate cron check-ins | `monitor_beat_tasks=True` and `@monitor` on one task; auto-discovery creates the monitor on first run and handles crontab schedules only | celery crons page |
| uWSGI crashes or missing data | threads off by default: needs `--enable-threads` and `--py-call-uwsgi-fork-hooks` | django, flask pages |
| `_experiments={"enable_logs": True}` | experimental idiom; in 3.0 experimental options are top-level only | migration page |
| 3.0: locals unscrubbed | `event_scrubber` removed; use denylist `mode` under `stack_frame_variables` | migration page |
| Starlette/FastAPI bodies absent in 3.0 | body only attached if handler called `Request.json()`/`Request.form()` first | migration page |

## Sources
- https://docs.sentry.io/platforms/python/
- https://docs.sentry.io/platforms/python/configuration/options/
- https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
- https://docs.sentry.io/platforms/python/data-management/data-collected/
- https://docs.sentry.io/platforms/python/integrations/ (and the django, flask, celery, logging, default-integrations, agent-tracing/openai pages under it)
- https://docs.sentry.io/platforms/python/integrations/celery/
- https://docs.sentry.io/platforms/python/integrations/celery/crons/
- https://docs.sentry.io/platforms/python/crons/ , .../profiling/ , .../configuration/releases/

## Identifiers
```identifiers
send_default_pii | https://docs.sentry.io/platforms/python/configuration/options/
data_collection | https://docs.sentry.io/platforms/python/configuration/options/
include_local_variables | https://docs.sentry.io/platforms/python/configuration/options/
include_source_context | https://docs.sentry.io/platforms/python/configuration/options/
event_scrubber | https://docs.sentry.io/platforms/python/configuration/options/
traces_sample_rate | https://docs.sentry.io/platforms/python/configuration/options/
trace_lifecycle | https://docs.sentry.io/platforms/python/configuration/options/
before_send_transaction | https://docs.sentry.io/platforms/python/configuration/options/
profiles_sample_rate | https://docs.sentry.io/platforms/python/configuration/options/
profile_session_sample_rate | https://docs.sentry.io/platforms/python/configuration/options/
profile_lifecycle | https://docs.sentry.io/platforms/python/configuration/options/
enable_logs | https://docs.sentry.io/platforms/python/configuration/options/
attach_stacktrace | https://docs.sentry.io/platforms/python/configuration/options/
trace_propagation_targets | https://docs.sentry.io/platforms/python/configuration/options/
stream_gen_ai_spans | https://docs.sentry.io/platforms/python/configuration/options/
disabled_integrations | https://docs.sentry.io/platforms/python/configuration/options/
auto_enabling_integrations | https://docs.sentry.io/platforms/python/configuration/options/
default_integrations | https://docs.sentry.io/platforms/python/configuration/options/
max_request_body_size | https://docs.sentry.io/platforms/python/configuration/options/
shutdown_timeout | https://docs.sentry.io/platforms/python/configuration/options/
enable_tracing | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
enable_metrics | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
transaction_style | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
before_send_span | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
include_prompts | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
breadcrumb_level | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
set_tag | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
capture_message | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
_experiments | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
stack_frame_variables | https://docs.sentry.io/platforms/python/data-management/data-collected/
frame_context_lines | https://docs.sentry.io/platforms/python/data-management/data-collected/
user_info | https://docs.sentry.io/platforms/python/data-management/data-collected/
cookies | https://docs.sentry.io/platforms/python/data-management/data-collected/
http_headers | https://docs.sentry.io/platforms/python/data-management/data-collected/
url_query_params | https://docs.sentry.io/platforms/python/data-management/data-collected/
http_bodies | https://docs.sentry.io/platforms/python/data-management/data-collected/
gen_ai | https://docs.sentry.io/platforms/python/data-management/data-collected/
database_query_data | https://docs.sentry.io/platforms/python/data-management/data-collected/
queues | https://docs.sentry.io/platforms/python/data-management/data-collected/
graphql | https://docs.sentry.io/platforms/python/data-management/data-collected/
capture_sentry_logs | https://docs.sentry.io/platforms/python/integrations/logging/
sentry_logs_level | https://docs.sentry.io/platforms/python/integrations/logging/
event_level | https://docs.sentry.io/platforms/python/integrations/logging/
monitor_beat_tasks | https://docs.sentry.io/platforms/python/integrations/celery/crons/
capture_checkin | https://docs.sentry.io/platforms/python/crons/
DjangoIntegration | https://docs.sentry.io/platforms/python/integrations/django/
config_from_object | https://docs.sentry.io/platforms/python/integrations/celery/
celeryd_init | https://docs.sentry.io/platforms/python/integrations/celery/
worker_init | https://docs.sentry.io/platforms/python/integrations/celery/
beat_init | https://docs.sentry.io/platforms/python/integrations/celery/crons/
before_send | https://docs.sentry.io/platforms/python/configuration/options/
UnraisablehookIntegration | https://docs.sentry.io/platforms/python/integrations/default-integrations/
```

## Unconfirmed
- `data_collection` first release: 2.72.0 docs list it as a stable top-level option, but the exact 2.x version that promoted it from `_experiments` was not confirmed; read the lockfile version before assuming it exists.
