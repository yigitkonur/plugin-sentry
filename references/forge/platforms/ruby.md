# Ruby (module: platforms/ruby)

Applies to `sentry-ruby` 7.x, the major the Ruby options page calls "this major version". Its `data_collection` table also gives the 8.0.0 defaults, which the docs say apply in the next major. Serves the ruby, sinatra, rack and sidekiq framework ids. Rails has its own module (`platforms/rails`); this file covers what Rails shares with the rest.

## Detect

| Signal | Where | Means |
|---|---|---|
| `gem "sentry-ruby"`, `gem "sentry-sidekiq"` | Gemfile, Gemfile.lock | SDK installed; the lockfile gives the real version |
| `Sentry.init do` with `config.dsn` | `config/initializers/sentry.rb` (Rails convention), or the entry file of a Rack, Sinatra or worker app | the init site(s); see Init placement |
| `use Sentry::Rack::CaptureExceptions` | `config.ru` or the rackup file | Rack exception middleware is wired |
| Sidekiq in Gemfile, a worker line in `Procfile`, `config/sidekiq.yml` | repo root, `config/` | a Sidekiq server process; it must load the same init as the web process |
| `Raven.configure` (legacy raven gem) | initializers, Gemfile | legacy SDK, not `sentry-ruby`; see Unconfirmed |

Library-only gems with no app entry point should not call `Sentry.init`: report and move on.
Fixture for this stack: `evals/fixtures/rails-sidekiq` (has `config/initializers/sentry.rb`, `config/sidekiq.yml`, `Procfile`). The engine's expected result is `evals/expected/rails-sidekiq.detect.json`: init site at line 1 with `Sentry.init do |config|`.

## Install route

Manual. The Ruby pages fetched document no accelerator, so do not paste install steps from memory.

| Need | Docs path for `sentry-ctx docs page` |
|---|---|
| core SDK (`gem "sentry-ruby"`) | `platforms/ruby` with `--section "Install"` |
| Sidekiq (`gem "sentry-sidekiq"`) | `platforms/ruby/guides/sidekiq` |
| Rack, or Sinatra on rackup | `platforms/ruby/guides/rack` |
| Sinatra specifically | no page: `platforms/ruby/guides/sinatra` returned Page Not Found on 2026-10-20; use the Rack guide's "Without Rackup" section |
| profiling (`stackprof` gem, or Vernier) | `platforms/ruby/profiling` |
| Rails apps | `platforms/ruby/guides/rails` (its install section was not read for this module) |

## Init placement

| Setup | Where `Sentry.init` goes | Source |
|---|---|---|
| Rack with rackup | in the rackup file or the file it loads, above the app. Add `use Sentry::Rack::CaptureExceptions` in `config.ru` | rack guide, "With Rackup" |
| Sinatra without rackup | before `require 'sinatra'`. The docs say this order is required | rack guide, "Without Rackup" |
| Sidekiq | "as early as possible" in the app's entry point. Check that the Sidekiq server command (Procfile, Dockerfile, CI) loads the same initializer as the web process. The docs do not name the file | sidekiq guide, "Initialize" |
| Rails | `config/initializers/sentry.rb` (the file the engine detects) | Rails guide (not read here) |

A second init inside a job or request file, rather than the entry point, is a finding: the docs want init at the entry point.

## Options by SDK major

| option | 7.x (current) | 8.0.0 (next, per docs) | note |
|---|---|---|---|
| `send_default_pii` | default `false`; deprecated | not stated | backfills `data_collection` in 7.x; migrate to `data_collection` |
| `data_collection` | available since 7.0.0; defaults in the table below | user_info true, cookies deny_list, url_query_params deny_list, http_bodies all, database_query_data true, queues true | set every key the privacy answers need |
| `include_local_variables` | default `false`; deprecated | not stated | use `data_collection.stack_frame_variables` |
| `context_lines` | default `3`; deprecated | not stated | use `data_collection.frame_context_lines` |
| `traces_sample_rate` | default `nil` (tracing off) | not stated | needs a deliberate value |
| `profiles_sample_rate` | default `nil`; relative to `traces_sample_rate` | not stated | `profiles_sample_interval` default `1e6 / 101` |
| `environment` | default `development` | not stated | fallback order below |
| `release` | no default string | not stated | detection order below |
| `breadcrumbs_logger` | set to e.g. `[:sentry_logger, :http_logger]` in the docs | not stated | the docs' examples set it; the default was not read |

## Product support matrix

Product ids are the `data/products.json` ids. "no" comes from the Ruby platform matrix (research) or the absence of any Ruby page.

| product | supported | notes |
|---|---|---|
| errors | yes | "Issues (always enabled)" on the install section; `Sentry.capture_exception` in Verify |
| tracing | yes | `traces_sample_rate` (default `nil`); `Sentry.start_transaction` and `Sentry.with_child_span` in Verify |
| profiling | yes, beta, transaction-based | StackProf or Vernier (profiling page); sampled relative to `traces_sample_rate` (init comment). Research matrix says beta, transaction-based |
| replay | no | research matrix; no Ruby replay page |
| logs | yes | enabled by installing the SDK ("Logs" on the install section); `Sentry.logger`; stdlib Logger integration at `platforms/ruby/integrations/logging` |
| metrics | yes | enabled by install ("Application Metrics (always enabled)"); `Sentry.metrics` count, gauge, distribution in Verify |
| crons | yes | Check-Ins (recommended) and Heartbeat; `enabled_patches` for `sidekiq_cron` or `sidekiq_scheduler`; `Sentry::Cron::MonitorCheckIns` mixin on a Sidekiq or ActiveJob class |
| feedback | yes | page exists (`platforms/ruby/user-feedback`); its mechanics were not read |
| ai | unconfirmed | see Unconfirmed; no Ruby AI page found |
| flags | no | research matrix; no Ruby flags page |
| debug-artifacts | unconfirmed | no Ruby upload route in the pages read; see Release and artifacts |

## Release and artifacts

- `release` detection, in order (options page): `SENTRY_RELEASE`; `KAMAL_VERSION`; git SHA of the last commit; the `REVISION` file in the app root (Capistrano); `HEROKU_SLUG_COMMIT` (Heroku Labs). Detection runs automatically in Kamal, Heroku and Capistrano; set `release` otherwise. Shape in the docs: `my-project-name@2.3.12`. Inference from the chain: a container built without `.git`, `SENTRY_RELEASE` or `REVISION` has no release; check the Dockerfile and CI.
- `environment` fallback (options page): `SENTRY_CURRENT_ENV`, then `SENTRY_ENVIRONMENT`, `RAILS_ENV`, `RACK_ENV`, else `development`. Worker containers that set none of these report as `development`.
- Debug files, symbols and source maps: the Ruby pages read (`platforms/ruby`, releases, options) describe no upload step. Source lines are captured by the SDK per frame (`frame_context_lines`, default `3`).
- CI: the releases page says to set the release name at build and deploy time and to tell Sentry about a release before events arrive. It documents no Ruby-specific CLI step.

## Privacy

Defaults for 7.x, from the `data_collection` table (backfilled from `send_default_pii`, default `false`). The docs' default-collection statement: no user identity (IP, ID), no HTTP bodies, no URL query parameters.

| Data | 7.x default | Control |
|---|---|---|
| user identity, IP inferred from Rack | off | `data_collection.user_info` |
| cookies | `:off` | `data_collection.cookies` |
| request and response headers | `deny_list` | `data_collection.http_headers` |
| HTTP bodies | `[]` (none) | `data_collection.http_bodies` |
| URL query params | `:off` | `data_collection.url_query_params` |
| database query data (bound params, Redis args) | off | `data_collection.database_query_data` |
| queue and ActiveJob args | off | `data_collection.queues` |
| local variables in frames | off | `data_collection.stack_frame_variables` |

`send_default_pii: true` (the rails-sidekiq fixture sets it) turns on the permissive backfill. Compare with the privacy answers, not with the Ruby default.

## Verify recipe

Use the real code path that serves the stack, not a bare `Sentry.init` call.

1. Rack or Sinatra: add a temporary route (e.g. `get "/__sentry_probe"`) behind the same middleware as production. In it, raise an exception whose message includes a unique marker, or use the docs' divide-by-zero test (`1 / 0`) rescued and passed to `Sentry.capture_exception`, with the marker added.
2. Sidekiq: add a temporary job class with the same probe body; enqueue it through the app's normal path so the real worker runs it.
3. Hit the route or run the job; find the marker on the Issues page ("View Captured Data in Sentry"). Run both: an event from the worker proves the worker loaded the init.
4. Remove the route and job file; `git diff` must show no probe.

## Gotchas

| Trap | Why it matters | Source |
|---|---|---|
| Doc snippets set `traces_sample_rate = 1.0` and `profiles_sample_rate = 1.0` | copied into production they trace and profile everything | ruby and sidekiq guide init examples |
| `send_default_pii` is deprecated, default `false` in 7.x | the 8.0.0 `data_collection` defaults are permissive (user_info, http_bodies, database_query_data, queues) | options page, `data_collection` |
| Logs and Application Metrics are on after install | volume and quota exist without an opt-in step | ruby install section |
| `environment` defaults to `development` | workers without `RAILS_ENV` or `RACK_ENV` report as development | options page, `environment` |
| No Sinatra guide page | the auditor should read the rack guide for Sinatra | rack guide; sinatra path returned Page Not Found |
| Rackup without `Sentry::Rack::CaptureExceptions` | the rack guide adds this middleware in `config.ru` as the step that catches exceptions | rack guide, "With Rackup" |

## Sources

- https://docs.sentry.io/platforms/ruby/
- https://docs.sentry.io/platforms/ruby/configuration/options/
- https://docs.sentry.io/platforms/ruby/configuration/releases/
- https://docs.sentry.io/platforms/ruby/guides/rack/
- https://docs.sentry.io/platforms/ruby/guides/sidekiq/
- https://docs.sentry.io/platforms/ruby/crons/
- https://docs.sentry.io/platforms/ruby/profiling/
- https://docs.sentry.io/platforms/ruby/integrations/logging/
- https://docs.sentry.io/platforms/ruby/user-feedback/
- https://docs.sentry.io/platforms/ruby/guides/rails/

## Identifiers

```identifiers
sentry-ruby | https://docs.sentry.io/platforms/ruby/
sentry-sidekiq | https://docs.sentry.io/platforms/ruby/guides/sidekiq/
stackprof | https://docs.sentry.io/platforms/ruby/
Sentry.init | https://docs.sentry.io/platforms/ruby/
Sentry.capture_exception | https://docs.sentry.io/platforms/ruby/
Sentry.start_transaction | https://docs.sentry.io/platforms/ruby/
with_child_span | https://docs.sentry.io/platforms/ruby/
Sentry.metrics | https://docs.sentry.io/platforms/ruby/
Sentry::Rack::CaptureExceptions | https://docs.sentry.io/platforms/ruby/guides/rack/
sidekiq_cron | https://docs.sentry.io/platforms/ruby/crons/
sidekiq_scheduler | https://docs.sentry.io/platforms/ruby/crons/
enabled_patches | https://docs.sentry.io/platforms/ruby/crons/
Sentry::Cron::MonitorCheckIns | https://docs.sentry.io/platforms/ruby/crons/
send_default_pii | https://docs.sentry.io/platforms/ruby/configuration/options/
data_collection | https://docs.sentry.io/platforms/ruby/configuration/options/
user_info | https://docs.sentry.io/platforms/ruby/configuration/options/
http_headers | https://docs.sentry.io/platforms/ruby/configuration/options/
http_bodies | https://docs.sentry.io/platforms/ruby/configuration/options/
url_query_params | https://docs.sentry.io/platforms/ruby/configuration/options/
database_query_data | https://docs.sentry.io/platforms/ruby/configuration/options/
stack_frame_variables | https://docs.sentry.io/platforms/ruby/configuration/options/
frame_context_lines | https://docs.sentry.io/platforms/ruby/configuration/options/
include_local_variables | https://docs.sentry.io/platforms/ruby/configuration/options/
context_lines | https://docs.sentry.io/platforms/ruby/configuration/options/
traces_sample_rate | https://docs.sentry.io/platforms/ruby/configuration/options/
profiles_sample_rate | https://docs.sentry.io/platforms/ruby/configuration/options/
profiles_sample_interval | https://docs.sentry.io/platforms/ruby/configuration/options/
breadcrumbs_logger | https://docs.sentry.io/platforms/ruby/configuration/options/
sentry_logger | https://docs.sentry.io/platforms/ruby/configuration/options/
http_logger | https://docs.sentry.io/platforms/ruby/configuration/options/
deny_list | https://docs.sentry.io/platforms/ruby/configuration/options/
SENTRY_DSN | https://docs.sentry.io/platforms/ruby/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/ruby/configuration/options/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/ruby/configuration/options/
SENTRY_CURRENT_ENV | https://docs.sentry.io/platforms/ruby/configuration/options/
RAILS_ENV | https://docs.sentry.io/platforms/ruby/configuration/options/
RACK_ENV | https://docs.sentry.io/platforms/ruby/configuration/options/
KAMAL_VERSION | https://docs.sentry.io/platforms/ruby/configuration/options/
HEROKU_SLUG_COMMIT | https://docs.sentry.io/platforms/ruby/configuration/options/
REVISION | https://docs.sentry.io/platforms/ruby/configuration/options/
```

## Unconfirmed

- AI monitoring on Ruby: the research matrix says "manual module", but no Ruby AI page was found on 2026-10-20 at `platforms/ruby/tracing/instrumentation/ai-agents-module`, `platforms/ruby/tracing/instrumentation/ai-agents`, `platforms/ruby/ai-agents` or `platforms/ruby/integrations/ai-agents-module` (all Page Not Found). Verify before proposing AI monitoring.
- Debug files, symbols and source-map upload for Ruby: no page found that documents one. Do not propose an upload step.
- Legacy raven detection (`Raven.configure`): from research notes only; no official Ruby page fetched for it.
