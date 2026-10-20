# Ruby on Rails (module: platforms/rails)

Applies to `sentry-rails` and `sentry-ruby` 7.x (current major on 2026-10-20). The 8.0.0 defaults are noted only where the docs
table gives them. Sidekiq jobs are covered by `platforms/ruby/guides/sidekiq`, which uses the same initializer pattern.

## Detect

| Signal | Where | Means |
|---|---|---|
| `sentry-rails` and `sentry-ruby` gems | Gemfile, Gemfile.lock | SDK installed; the lockfile gives the real version |
| `rails` or `railties` dependency | Gemfile, Gemfile.lock | framework id `rails` (engine rule `Gemfile:deps:rails`) |
| `Sentry.init` block with `config` | config/initializers/sentry.rb | the one init site; the engine matches `Sentry\.init\s+do` |
| `sentry-sidekiq` gem | Gemfile | Sidekiq jobs; read the Sidekiq guide as well |
| `stackprof` gem | Gemfile | profiling is wanted; must load before `sentry-ruby` |
| `worker:` line and `config/sidekiq.yml` | Procfile, config/ | a second process that needs the SDK too |

Fixture `evals/fixtures/rails-sidekiq`: Gemfile declares `rails`; init at line 1 of `config/initializers/sentry.rb`; Procfile has
`web` (puma) and `worker` (sidekiq); job in `app/jobs/nightly_report_job.rb`.

## Install route

No generator or wizard step is on the Rails page. Install is manual: `sentry-ctx docs page platforms/ruby/guides/rails --section
"Install the Sentry SDK"`, then `--section "Initialize the Sentry SDK"`. Sidekiq: `platforms/ruby/guides/sidekiq` (adds
`sentry-sidekiq`). Profiling: `platforms/ruby/profiling`. Do not paste install steps from memory.

## Init placement

| Process | Where | Note |
|---|---|---|
| Rails app (web) | `config/initializers/sentry.rb` | docs: "as early as possible in your application's lifecycle" |
| Sidekiq worker | same initializer when the worker boots the Rails app | check the `worker:` Procfile line and `config/sidekiq.yml`; if the worker never loads the initializer, job errors are missing |
| Profiling | Gemfile order | `stackprof` listed before `sentry-ruby` (profiling page) |

Two `Sentry.init` blocks in one process, or init only in a job file, are findings.

## Options by SDK major

Only 7.x values were fetched for the `v(N-1)` column, so it shows `—`.

| option | v(N-1) | v(N) 7.x | note |
|---|---|---|---|
| `send_default_pii` | — | default `false`, deprecated | 7.x backfills `data_collection` from it; migrate; fixture sets `true` |
| `data_collection` | — | `user_info` false; `cookies` off; `http_headers.request` and `.response` `deny_list`; `http_bodies` `[]`; `url_query_params` off; `database_query_data` false; `queues` false; `stack_frame_variables` false; `frame_context_lines` 3 | 8.0.0 column: `user_info` true, all body types, `database_query_data` true, `queues` true, `cookies` and `url_query_params` `deny_list` |
| `excluded_exceptions` | — | default `Sentry::Configuration::IGNORE_DEFAULT` | append with `+=`; `=` drops the defaults |
| `release` | — | string, auto-detected when unset | order in Release and artifacts |
| `environment` | — | default `development` | read from `SENTRY_CURRENT_ENV`, `SENTRY_ENVIRONMENT`, `RAILS_ENV`, `RACK_ENV`, in that order |
| `sample_rate` | — | default `1.0` (error events) | |
| `traces_sample_rate` | — | default nil (tracing off) | `0` still continues incoming traces; nil disables all tracing |
| `profiles_sample_rate` | — | default nil | relative to `traces_sample_rate`; both must be non-zero |
| `breadcrumbs_logger` | — | Rails page: `[:active_support_logger, :http_logger]`; Sidekiq page: `[:sentry_logger, :http_logger]` | the two pages differ; both documented |

## Product support matrix

| product | supported | notes |
|---|---|---|
| Errors | yes | `sample_rate`; suppression via `excluded_exceptions` |
| Tracing | yes | needs `traces_sample_rate`; Verify uses `Sentry.start_transaction` and `Sentry.with_child_span` |
| Profiling | yes, beta | StackProf (beta from SDK 5.9.0) or Vernier, per profiling page; `stackprof` gem |
| Replay | no | no Ruby replay page; platform matrix shows `—` |
| Logs | yes | `Sentry.logger` (Rails Verify); stdlib Logger capture on the logging integration page |
| Metrics | yes | Rails Verify lists Metrics (NEW); metrics API page not read |
| Crons | yes | `platforms/ruby/crons`: job monitoring, check-ins (recommended), heartbeat |
| Feedback | yes | crash-report modal needs dynamic error pages (`exceptions_app`); also the User Feedback API |
| AI monitoring | unconfirmed | matrix says "manual module"; see Unconfirmed |
| Feature flags | no | platform matrix shows `—` (no integration) |
| Debug files and source maps | unconfirmed | no upload page read; see Release and artifacts |

## Release and artifacts

- Release resolution, first match wins (`release` option): `SENTRY_RELEASE`; `KAMAL_VERSION` (Kamal); git SHA of the last commit;
  `REVISION` file in the app root (Capistrano); `HEROKU_SLUG_COMMIT` (Heroku, only with Heroku Labs enabled).
- Right: `SENTRY_RELEASE` set by the deploy, or one of the auto sources present. A container build with no `.git`, no
  `SENTRY_RELEASE` and no `KAMAL_VERSION` gets no release from this list; check the Dockerfile and CI. The page does not say what
  the SDK sends in that case.
- Environment: see `environment` above; set it explicitly for staging.
- Source context: read from the app's files at runtime (`frame_context_lines`, 3 by default in 7.x). No upload step.
- Source maps and debug files: none documented on the pages read; see Unconfirmed.

## Privacy

Rails page: by default the SDK sends no user identity, HTTP bodies, or URL query parameters. The 7.x `data_collection` defaults:

| Data | 7.x default | control |
|---|---|---|
| user identity (IP, id) | off | `data_collection.user_info` |
| request and response headers | on, `deny_list` mode | `data_collection.http_headers.request` / `.response` |
| cookies | off | `data_collection.cookies` |
| HTTP bodies | none | `data_collection.http_bodies` |
| URL query params | off | `data_collection.url_query_params` |
| DB query data (bound params, Redis args) | off | `data_collection.database_query_data` |
| queue and job arguments | off | `data_collection.queues` |
| stack frame locals | off | `data_collection.stack_frame_variables` |

Built-in sensitive denylist (`auth`, `token`, `password`, and similar) is scrubbed in every mode. Right: each category set on
purpose from the privacy answers, with `send_default_pii` removed.

## Verify recipe

1. Request path (preferred). Add one temporary line to `config/routes.rb`:
   `get "/sentry-verify" => proc { raise "sentry-verify-marker" }`. Run the app in a non-production environment with the DSN
   configured, then `curl -i http://localhost:3000/sentry-verify`; expect HTTP 500. In Sentry the issue title contains
   `sentry-verify-marker`, with the expected environment and release.
2. Worker path. Add a temporary `raise "sentry-verify-marker"` at the top of one job's `perform` (fixture: `app/jobs/nightly_report_job.rb`),
   enqueue it the way the app already does, and check the worker log and the Sentry issue.
3. Fallback only (no request path reachable): `bin/rails runner` with the docs snippet, `begin; 1 / 0; rescue ZeroDivisionError =>
   exception; Sentry.capture_exception(exception); end`. This proves the DSN and transport, not the request path.
4. Remove: delete the route line and the `raise` line; `grep -rn "sentry-verify" config app` must print nothing.

## Gotchas

- `send_default_pii` is deprecated (options page). The fixture sets it `true`; treat as a finding and migrate to `data_collection`.
- `excluded_exceptions =` replaces the default list; the docs say append with `+=`. The docs example suppresses
  `ActionController::RoutingError` and `ActiveRecord::RecordNotFound` by appending them. The default list is not printed on the
  page; read it from the installed gem.
- The Rails init example sets `traces_sample_rate = 1.0` and `profiles_sample_rate = 1.0` and says to adjust in production. The
  fixture ships `1.0`; finding unless deliberate.
- `environment` defaults to `development` when none of the four variables is set.
- Profiling: `stackprof` must come before `sentry-ruby` in the Gemfile; the profile rate is a share of traced transactions.
- Crash-report modal: `config.exceptions_app` must render a dynamic page, since the event id reaches the page as `request.env`
  key `sentry.error_event_id`. A static `500.html` cannot carry it.
- The Rails and Sidekiq pages use different `breadcrumbs_logger` values. Both are documented; not a bug.
- Research notes and the pages agree on the `send_default_pii` deprecation, `stackprof`, and `excluded_exceptions` appending.
  No disagreement found.

## Sources

- https://docs.sentry.io/platforms/ruby/guides/rails/
- https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
- https://docs.sentry.io/platforms/ruby/guides/rails/user-feedback/
- https://docs.sentry.io/platforms/ruby/guides/rails/data-management/
- https://docs.sentry.io/platforms/ruby/guides/sidekiq/
- https://docs.sentry.io/platforms/ruby/profiling/
- https://docs.sentry.io/platforms/ruby/crons/

## Identifiers

```identifiers
sentry-rails | https://docs.sentry.io/platforms/ruby/guides/rails/
sentry-ruby | https://docs.sentry.io/platforms/ruby/guides/rails/
sentry-sidekiq | https://docs.sentry.io/platforms/ruby/guides/sidekiq/
stackprof | https://docs.sentry.io/platforms/ruby/profiling/
Sentry.init | https://docs.sentry.io/platforms/ruby/guides/rails/
Sentry.start_transaction | https://docs.sentry.io/platforms/ruby/guides/rails/
Sentry.with_child_span | https://docs.sentry.io/platforms/ruby/guides/rails/
Sentry.capture_exception | https://docs.sentry.io/platforms/ruby/guides/rails/
Sentry.get_current_scope | https://docs.sentry.io/platforms/ruby/guides/rails/
Sentry.logger | https://docs.sentry.io/platforms/ruby/guides/rails/
breadcrumbs_logger | https://docs.sentry.io/platforms/ruby/guides/rails/
active_support_logger | https://docs.sentry.io/platforms/ruby/guides/rails/
http_logger | https://docs.sentry.io/platforms/ruby/guides/rails/
sentry_logger | https://docs.sentry.io/platforms/ruby/guides/sidekiq/
showReportDialog | https://docs.sentry.io/platforms/ruby/guides/rails/user-feedback/
exceptions_app | https://docs.sentry.io/platforms/ruby/guides/rails/user-feedback/
sentry.error_event_id | https://docs.sentry.io/platforms/ruby/guides/rails/user-feedback/
send_default_pii | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
data_collection | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
user_info | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
http_headers | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
deny_list | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
cookies | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
http_bodies | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
url_query_params | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
database_query_data | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
queues | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
stack_frame_variables | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
frame_context_lines | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
excluded_exceptions | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
Sentry::Configuration::IGNORE_DEFAULT | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
ActionController::RoutingError | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
ActiveRecord::RecordNotFound | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
release | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
KAMAL_VERSION | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
REVISION | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
HEROKU_SLUG_COMMIT | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
environment | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
SENTRY_CURRENT_ENV | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
RAILS_ENV | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
RACK_ENV | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
sample_rate | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
traces_sample_rate | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
profiles_sample_rate | https://docs.sentry.io/platforms/ruby/guides/rails/configuration/options/
```

## Unconfirmed
- `ActiveJob` capture: what is captured by default and whether it is automatic. No fetched page says; the `queues` option only says "where the integration supports it".
- `AI monitoring` for Ruby: platform matrix says "manual module"; `platforms/ruby/tracing/instrumentation/ai-agents-module` returned Page Not Found.
- `Raven.configure` and `sentry-raven`: legacy gem, from engine data only; no migration page fetched.
- Source maps and debug files for Ruby: no upload page fetched; none documented on the pages read.
