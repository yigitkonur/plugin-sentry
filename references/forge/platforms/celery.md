# Celery (module: platforms/celery)

## Detect

Engine entry: framework `celery`, dep `celery`, ecosystem `python`, role `worker`, docs `python/integrations/celery`. Celery is
usually inside a Django or Flask unit, so read the settings module and every process definition, not only the task files.

| Signal | Where | Means |
|---|---|---|
| `celery` in deps | pyproject.toml, uv.lock, requirements*.txt, Pipfile | Celery installed; the lockfile gives the version |
| `Celery(` constructor | `*.py` (often `celery.py` next to settings) | the app object; `config_from_object` decides whether settings-based init covers it |
| task decorators | task modules | tasks whose exceptions become issues |
| `beat_schedule` | Celery config module | periodic tasks: monitor candidates |
| `celery ... worker`, `celery ... beat`, `-B` | Dockerfile, Procfile, compose, supervisord, k8s manifests | which processes need Sentry init |

Fixture `evals/fixtures/django-celery`: `config/celery.py` builds `Celery("config")`, calls
`config_from_object("django.conf:settings", namespace="CELERY")` and has a `beat_schedule` entry `nightly-cleanup`
(crontab 03:00) for `app.tasks.cleanup_sessions`. The engine's init site is `config/settings.py` line 28: a Django integration,
no Celery integration. So the beat job has no monitor (`monitor_beat_tasks` defaults to `False`).

## Install route

- No accelerator: the engine entry has no wizard id. Install by hand from the live page.
- The install step on the page is plain `pip install "sentry-sdk"`, with no Celery extra.
- Read `sentry-ctx docs page platforms/python/integrations/celery --section "Install"`.
- Without Django: `--section "Set up Sentry in Celery Daemon or Worker Processes"` and `--section "Set up Sentry in Your Application"`.
- With Django: `--section "Set up Celery With Django"`, then the Django integration page for the settings init.
- Beat: `sentry-ctx docs page platforms/python/integrations/celery/crons --section "Celery Beat Auto Discovery"`.

## Init placement

| Process | Where Sentry starts | Source |
|---|---|---|
| Worker daemon | `celeryd_init` signal handler; fires at daemon start, before worker processes spawn | celery page, "Set up Sentry in Celery Daemon or Worker Processes" |
| Each worker child process | `worker_init` signal instead, when every process needs its own init | same section |
| Beat in its own process | BOTH `beat_init` and `celeryd_init` | crons page, "Celery Beat Auto Discovery" |
| Beat inside the worker (`-B` / `--beat`) | `celeryd_init` or `beat_init` | same section |
| Producer (web app, script, shell that calls `.delay()`) | `sentry_sdk.init()` in the app entry | celery page, "Set up Sentry in Your Application" |
| Django project | `settings.py` init; no second Celery init when Celery uses `config_from_object` | celery page, "Set up Celery With Django" |

Failures: a worker with no init reports no task events; a producer with no init loses the trace start (the docs example wraps
`.delay()` in a transaction). A task-module init is not a documented placement (see Gotchas).

## Options by SDK major

The Celery pages do not split options by major. The 3.0 column says "page silent", not "same".

| option | 2.x (current docs) | 3.0 alpha | note |
|---|---|---|---|
| `propagate_traces` | default `True` | page silent | `False` makes each task start its own trace |
| `monitor_beat_tasks` | default `False` | page silent | `True` turns on beat auto-discovery in Sentry Crons |
| `exclude_beat_tasks` | default `None`, `list[str]` | page silent | applied only when `monitor_beat_tasks=True`; task names or regex such as `"payment-check-.*"` |

Pass them as `CeleryIntegration(...)` inside `sentry_sdk.init(integrations=[...])`. Add the integration explicitly only to set
options. Stream mode: the page says the same options still work but apply to service spans instead of transactions.

## Product support matrix

Matrix values come from the Python row of the platform matrix (research note), unless the Celery pages say otherwise.

| product | supported | notes |
|---|---|---|
| Errors | yes | task exceptions are captured and reported as issues (celery page, "Capturing Errors") |
| Tracing | yes | `traces_sample_rate` sets sampling; propagation is `propagate_traces`, not sampling |
| Profiling | yes | init example sets `profile_session_sample_rate` and `profile_lifecycle`; the worker needs its own init |
| Replay | no | matrix: Python has no Session Replay page |
| Logs | yes | page says logs are enabled by default (Verify section) |
| Metrics | yes | page example imports metrics (marked NEW) |
| Crons | yes | beat auto-discovery via `monitor_beat_tasks`; per-task decorator `sentry_sdk.monitor` with `monitor_slug` |
| Feedback | yes (API only) | matrix: Python GA via API; the Celery pages are silent |
| AI | yes (matrix) | matrix: Python GA for LLM SDKs; the Celery pages are silent |
| Flags | beta (matrix) | matrix: Python beta; the Celery pages are silent |
| Debug files | unconfirmed | no debug-file route on the pages fetched; see Unconfirmed |

## Release and artifacts

- Default release (releases page, "Setting a Release"): the SDK reads `SENTRY_RELEASE`; if it is unset, it uses the git
  commit SHA when a repository is present. `release="myapp@1.0.0"` in `sentry_sdk.init()` overrides both.
- A container with no `.git` and no `SENTRY_RELEASE` sends worker events with no release. Check the Dockerfile and CI for
  both. Web and worker must send the same string (audit rule, not a docs statement).
- Artifacts: the fetched Celery and Python pages describe no source-map, symbol or debug-file upload for a Celery worker.
  A missing upload is not a finding until the Unconfirmed item is resolved.
- CI: no Celery-specific step.

## Privacy

| Data | Default | Control |
|---|---|---|
| user identity, IP, request headers | the Celery page no longer shows an init example; the Python options page documents `send_default_pii` (to be removed in 3.0) and its replacement `data_collection` | `send_default_pii` or `data_collection` in `sentry_sdk.init()` (Python options page) |
| task arguments and results | page does not say | unconfirmed; check task modules for personal data passed as arguments |

## Verify recipe

1. Add one temporary task in the module the worker imports (fixture: `app/tasks.py`). Name it `debug_sentry`, as in the docs
   example, and give it the decorator the module already uses. Body: `sentry_sdk.capture_message` with a marker such as
   `celery-verify <timestamp>`.
2. Trigger it through the real producer path, not a test runner. From the Django project:

   ```
   python manage.py shell -c "from app.tasks import debug_sentry; debug_sentry.delay()"
   ```

3. Worker log shows the task received and run. In Sentry (the DSN's project), Issues shows the message event with the
   marker. With `propagate_traces` on, the event sits in a trace that starts in the producer.
4. If the worker shows no init output, restart it once with `debug=True` in `sentry_sdk.init()`. Init output must appear at
   worker startup, before any task runs.
5. Remove: delete the `debug_sentry` task, run `grep -rn "celery-verify" app/ config/` (must print nothing), revert any
   `debug=True` you added, restart the worker.

## Gotchas

- `celeryd_init` runs at daemon start, before children spawn. A per-process init needs `worker_init` (celery page).
- Beat monitors need `monitor_beat_tasks=True` on `CeleryIntegration`. Without it, beat tasks are not monitored (crons page).
- A monitor appears only after its task runs for the first time (crons page). A new beat entry creates nothing at deploy.
- Only schedules that `crontab` can parse are created or updated (crons page). The fixture's `nightly-cleanup` qualifies.
- Decorator plus auto-discovery monitors the same task twice. `@sentry_sdk.monitor` goes below `@app.task` (crons page).
- `exclude_beat_tasks` is ignored unless `monitor_beat_tasks=True` (celery page, Options).
- `propagate_traces=False` makes each task start its own trace (celery page, Options). `traces_sample_rate` does not decide
  propagation (celery page, Distributed Traces).
- The per-call header `sentry-propagate-traces` works with `apply_async`. The page says overriding through `.delay()` is not
  possible (celery page, Distributed Traces).
- Research note says an init inside a task module is "too late". The docs show only signal handlers and say nothing about
  module placement. Judge the init by the worker-startup output with `debug=True`, not by file location.
- Redbeat is supported beside the default beat scheduler (crons page).

## Sources

- https://docs.sentry.io/platforms/python/integrations/celery.md
- https://docs.sentry.io/platforms/python/integrations/celery/crons.md
- https://docs.sentry.io/platforms/python/configuration/releases.md
- https://docs.sentry.io/platforms/python/usage.md
- https://docs.sentry.io/platforms/python/configuration/options.md

## Identifiers

```identifiers
CeleryIntegration | https://docs.sentry.io/platforms/python/integrations/celery.md
propagate_traces | https://docs.sentry.io/platforms/python/integrations/celery.md
monitor_beat_tasks | https://docs.sentry.io/platforms/python/integrations/celery.md
exclude_beat_tasks | https://docs.sentry.io/platforms/python/integrations/celery.md
celeryd_init | https://docs.sentry.io/platforms/python/integrations/celery.md
worker_init | https://docs.sentry.io/platforms/python/integrations/celery.md
beat_init | https://docs.sentry.io/platforms/python/integrations/celery/crons.md
sentry_sdk.init | https://docs.sentry.io/platforms/python/integrations/celery.md
sentry_sdk.monitor | https://docs.sentry.io/platforms/python/integrations/celery/crons.md
monitor_slug | https://docs.sentry.io/platforms/python/integrations/celery/crons.md
beat_schedule | https://docs.sentry.io/platforms/python/integrations/celery/crons.md
config_from_object | https://docs.sentry.io/platforms/python/integrations/celery.md
apply_async | https://docs.sentry.io/platforms/python/integrations/celery.md
sentry-propagate-traces | https://docs.sentry.io/platforms/python/integrations/celery.md
debug_sentry | https://docs.sentry.io/platforms/python/integrations/celery.md
debug | https://docs.sentry.io/platforms/python/integrations/celery.md
capture_message | https://docs.sentry.io/platforms/python/usage.md
traces_sample_rate | https://docs.sentry.io/platforms/python/integrations/celery.md
send_default_pii | https://docs.sentry.io/platforms/python/configuration/options.md
data_collection | https://docs.sentry.io/platforms/python/configuration/options.md
profile_session_sample_rate | https://docs.sentry.io/platforms/python/integrations/celery.md
profile_lifecycle | https://docs.sentry.io/platforms/python/integrations/celery.md
release | https://docs.sentry.io/platforms/python/configuration/releases.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/python/configuration/releases.md
-B | https://docs.sentry.io/platforms/python/integrations/celery/crons.md
--beat | https://docs.sentry.io/platforms/python/integrations/celery/crons.md
```

## Unconfirmed
- `retry`: retry noise and how to suppress it. The Celery pages fetched say nothing about retries; verify before writing a rule.
- Debug-file, symbol or source-map upload for a pure-Python worker: no fetched page covers it. Check the Python debug-files page.
- `HEROKU_SLUG_COMMIT`, `SOURCE_VERSION`, `CIRCLE_SHA1`: hosting-provider release fallbacks (research note). The releases page fetched names only `SENTRY_RELEASE` and git.
- Check-in rate limit for crons (research note): not on a fetched page.
- Sentry Dashboards auto-populating Queues for Celery (research note): not checked on an official page.
- Whether task arguments and results reach events: the Celery pages do not say.
