# Django (module: platforms/django)

## Detect

| Signal | Where | Means |
|---|---|---|
| Django dependency (engine dep regex `[Dd]jango`) | pyproject.toml, requirements*.txt, uv.lock, poetry.lock, Pipfile | Django app; the lockfile gives the real framework version |
| `manage.py` and a settings module (`settings.py`) | project root and the package that holds settings | the init site is in the settings module |
| `sentry_sdk.init(` | settings.py | the expected init (docs placement) |
| `DjangoIntegration` in `integrations=[...]` | settings.py | explicit integration; only needed to change its options |
| `celery` imports, `config/celery.py`, `app/tasks.py` | deps and code | a worker is a separate process with its own init (see Init placement) |

Engine entry (`data/detect/frameworks.json`, id `django`): ecosystem python, role backend, docs_platform `python/integrations/django`, module `platforms/django`.

Fixture `evals/fixtures/django-celery`: detected as django 5.1.4 (uv, pyproject.toml) with init site `config/settings.py` line 28. The config snapshot reads `DjangoIntegration()`, `send_default_pii` True and `traces_sample_rate` 1.0. Use it to confirm detection works, not as the target values.

## Install route

Manual, from the live page. No wizard id exists for Django in `frameworks.json`, so do not run a wizard.

- `sentry-ctx docs page platforms/python/integrations/django --section "Install"` for the install steps (do not paste them from memory).
- `sentry-ctx docs page platforms/python/integrations/django --section "Configure"` for the init snippet.
- Generic Python options and SDK majors: `sentry-ctx ref platforms/python`.

## Init placement

- Docs: "Configuration should happen as early as possible", initialized in `settings.py` (django page, Configure).
- Right: one module-level `sentry_sdk.init(...)` in the settings module that Django imports at startup, before any view or task code runs.
- Wrong: init inside a view, a middleware, a signal handler, or any module that loads after requests start.
- Two init sites in one process is a finding (see platforms/python). Web and worker processes each need their own init. Celery worker init: check platforms/python/integrations/celery (not fetched for this module).
- ASGI and WSGI entry points: no docs section fetched. See Unconfirmed.

## Options by SDK major

The Django page documents the 2.x surface (stable 2.72.0). It states no 3.0 change for the integration options, so the 3.0 column says "not stated" unless the migration page says otherwise.

| option | 2.x (stable, 2.72.0) | 3.0 alpha | note |
|---|---|---|---|
| `DjangoIntegration` `transaction_style` | default "url"; alternative "function_name" | not stated | "url" names the transaction by route path; "function_name" by view |
| `middleware_spans` | default False | not stated; migration page: middleware span op is `middleware` (was `middleware.django`) | off by default; one span per middleware layer |
| `signals_spans` | default True | not stated | synchronous receivers only |
| `signals_denylist` | default empty list | not stated | page example excludes pre_init and post_init |
| `cache_spans` | default False | not stated | read operations only, with hit/miss |
| `http_methods_to_capture` | default CONNECT, DELETE, GET, PATCH, POST, PUT, TRACE; since 2.15.0 | not stated | OPTIONS and HEAD excluded by default |
| `failed_request_status_codes` | default 5xx range | not stated | see Gotchas: 4xx are not reported by default |
| `send_default_pii` | page example True; user fields on errors need `django.contrib.auth` too | removed; use `data_collection` (migration page) | see Privacy |
| `traces_sample_rate` | page example 1.0; default not stated on this page | same key; `enable_tracing` removed (migration page) | sampling is a deliberate value, not a default |
| `profile_session_sample_rate` and `profile_lifecycle` | page example 1.0 and "trace" | continuous profiling only (research matrix; not on a 3.0 page fetched here) | |
| `data_collection` | not a Django option; set on `init` | defaults more permissive than `send_default_pii=False` (migration page) | see Privacy |

## Product support matrix

Source for "yes": the Django page unless the note says otherwise. "no" and "beta" come from the research platform matrix (Python row), which is not an official page; "unconfirmed" means neither source settles it.

| product | supported | notes |
|---|---|---|
| errors | yes | Issues always on (Configure list). Request data attached to all events |
| tracing | yes | `traces_sample_rate`. Automatic spans: middleware (off by default), signals (on), database, Redis, caches (off by default). Stream mode: options apply to service spans, not transactions |
| profiling | yes | continuous: `profile_session_sample_rate` with `profile_lifecycle` "trace" (page example). Research matrix: Python GA continuous since 2.24.1 |
| replay | no | research matrix: Python row has no Session Replay page (replay is browser-side) |
| logs | yes | `sentry_sdk.logger` for explicit logs. Stdlib log records become breadcrumbs by default through the Logging integration (page, Capturing Errors) |
| metrics | yes | `metrics.count`, gauge, distribution (Verify section). Always enabled per Configure list |
| crons | yes | Python-wide (research matrix GA). No Django section on the page; Celery beat has its own route (platforms/python/integrations/celery) |
| feedback | yes | research matrix: Python GA through the API only; no Django page section |
| ai | yes | research matrix: GA via supported AI libraries; Django adds no AI-specific section |
| flags | beta | research matrix: Python beta; no Django page section |
| debug files | unconfirmed | pure Python ships no debug files; no fetched page says either way |

## Release and artifacts

- `release` option: default None. `SENTRY_RELEASE` env var. The explicit `release` option takes precedence over the env var (options page). If unset, the SDK tries to configure one itself (options page); the order it tries is unconfirmed (see Unconfirmed).
- Set `release` explicitly from the same value the deploy step uses, so error releases match the deploy record.
- No source-map or debug-file upload for pure Python. Source context travels inside the event: `frame_context_lines` default 5 (data-collected page).
- Release-creation CI steps are not covered by pages fetched for this module.

## Privacy

| Data | Default | Control |
|---|---|---|
| user id, email, username on errors | only with `django.contrib.auth` and `send_default_pii=True` (page, 2.x) | 3.0 alpha: `data_collection` `user_info`, default True (data-collected page) |
| request method, URL, headers, form data, JSON payloads | sent on every event (page) | `data_collection` `http_headers`, `url_query_params`, `cookies` (denylist modes); `http_bodies` |
| request bodies | page: raw bodies and multipart file uploads excluded (2.x wording) | `http_bodies` default lists incoming_request and outgoing_request (data-collected page); see Gotchas |
| local variables in frames | `stack_frame_variables` default True (data-collected page) | set False or an allowlist |
| database query data | `database_query_data` default True; parameter values never sent (data-collected page) | set False |

## Verify recipe

Goal: one marked error and one transaction from the real request path (WSGI dev server or the ASGI server you deploy with), not a shell.

1. Add a temporary route to the project URL module (fixture: `config/urls.py`): `path('sentry-debug/', trigger_error)` with a view that raises `RuntimeError("sentry-verify django <token>")`. The docs use `1 / 0`; the marker string is this recipe's addition so the event is findable.
2. Start the server and request it: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/sentry-debug/`. Expect `500`. Unhandled exceptions are always reported (page, `failed_request_status_codes`).
3. In Sentry Issues, find the RuntimeError with the token. The same request appears as a transaction named by `transaction_style` (default route path `/sentry-debug/`).
4. Remove: delete the route and the view from `config/urls.py`, then confirm `grep -rn "sentry-debug" <repo>` returns nothing. Do not leave the route in the commit.

## Gotchas

| Symptom | Cause | Fix / source |
|---|---|---|
| Error from `manage.py shell` not captured | IPython and interactive shells do not trigger error monitoring | run the check from a file (page, Verify) |
| uWSGI workers crash or thread features fail | uWSGI does not support threads by default | enable `--enable-threads` and `--py-call-uwsgi-fork-hooks` (page, Instrumenting) |
| Handled 4xx never reach Sentry | default `failed_request_status_codes` is 5xx only; exceptions with no status_code are always reported | add codes such as {400, *range(500, 600)} (page example) |
| No user on errors | `django.contrib.auth` absent or `send_default_pii` unset (2.x) | set `send_default_pii` or use `data_collection` (page; migration page) |
| No middleware or cache spans | both default False | enable deliberately: `middleware_spans`, `cache_spans` (page) |
| OPTIONS or HEAD requests missing from transactions | `http_methods_to_capture` excludes them by default | intended unless the list is changed (page) |
| 3.0 alpha init fails on `send_default_pii` or `enable_tracing` | both removed | `data_collection` and `traces_sample_rate` (migration page) |
| 3.0 alpha: middleware spans renamed | op `middleware` replaces `middleware.django` | update dashboards and queries that filter on the old op (migration page) |
| 3.0 alpha: `capture_message()` events now have stack traces | `attach_stacktrace` default True in 3.0 | expected; check grouping before rollout (migration page) |
| Options set but nothing changes under stream mode | options apply to service spans instead of transactions | audit as span settings (page, Options) |
| Automatic tracing missing on file responses | automatic tracing is disabled when `offloading` is configured | instrument manually (page, Instrumenting) |
| Django 3.x crashes on older Django | 3.x needs Django 2.0 or newer | migration page |

Disagreement to check: the Django page says raw bodies are excluded (2.x wording). The data-collected page documents `http_bodies` defaults that include incoming requests. Check the installed major and the live pages before asserting either.

## Sources
- https://docs.sentry.io/platforms/python/integrations/django/
- https://docs.sentry.io/platforms/python/configuration/options/
- https://docs.sentry.io/platforms/python/data-management/data-collected/
- https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/

## Identifiers
```identifiers
DjangoIntegration | https://docs.sentry.io/platforms/python/integrations/django/
transaction_style | https://docs.sentry.io/platforms/python/integrations/django/
middleware_spans | https://docs.sentry.io/platforms/python/integrations/django/
signals_spans | https://docs.sentry.io/platforms/python/integrations/django/
signals_denylist | https://docs.sentry.io/platforms/python/integrations/django/
cache_spans | https://docs.sentry.io/platforms/python/integrations/django/
http_methods_to_capture | https://docs.sentry.io/platforms/python/integrations/django/
failed_request_status_codes | https://docs.sentry.io/platforms/python/integrations/django/
send_default_pii | https://docs.sentry.io/platforms/python/integrations/django/
traces_sample_rate | https://docs.sentry.io/platforms/python/integrations/django/
profile_session_sample_rate | https://docs.sentry.io/platforms/python/integrations/django/
profile_lifecycle | https://docs.sentry.io/platforms/python/integrations/django/
sentry_sdk.init | https://docs.sentry.io/platforms/python/integrations/django/
sentry_sdk.logger | https://docs.sentry.io/platforms/python/integrations/django/
metrics.count | https://docs.sentry.io/platforms/python/integrations/django/
--enable-threads | https://docs.sentry.io/platforms/python/integrations/django/
--py-call-uwsgi-fork-hooks | https://docs.sentry.io/platforms/python/integrations/django/
data_collection | https://docs.sentry.io/platforms/python/data-management/data-collected/
user_info | https://docs.sentry.io/platforms/python/data-management/data-collected/
http_headers | https://docs.sentry.io/platforms/python/data-management/data-collected/
http_bodies | https://docs.sentry.io/platforms/python/data-management/data-collected/
url_query_params | https://docs.sentry.io/platforms/python/data-management/data-collected/
stack_frame_variables | https://docs.sentry.io/platforms/python/data-management/data-collected/
frame_context_lines | https://docs.sentry.io/platforms/python/data-management/data-collected/
database_query_data | https://docs.sentry.io/platforms/python/data-management/data-collected/
release | https://docs.sentry.io/platforms/python/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/python/configuration/options/
enable_tracing | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
attach_stacktrace | https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
```

## Unconfirmed
- ASGI: `platforms/python/integrations/django/asgi` returns Page Not Found and the Django page has no ASGI section. ASGI init location and async behaviour are unverified.
- Caches page: `platforms/python/integrations/django/caches` returns Page Not Found. Cache behaviour is taken from the Options section only.
- Template render spans: not on the Django page; do not assert.
- Init ordering relative to MIDDLEWARE: no fetched page states it.
- Release derivation order (env var, then git SHA, then hosting env): research note only, not on a fetched page.
- Source maps and debug files for Python: no fetched page either way.
- Feature flags, feedback, AI, and crons on Django: research matrix only, no Django page section.
- `traces_sample_rate` default: not stated on the Django page.
- Celery worker init: platforms/python/integrations/celery not fetched for this module.
