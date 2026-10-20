# PHP (module: platforms/php)

Applies to the `sentry/sentry` SDK, 4.x major. The pages read document 4.x (`data_collection` since 4.33.0; `enable_logs` and `enable_metrics` are deprecated and removed in 5.0). Framework ids served: `php` (plain SDK) and `symfony` (`sentry/sentry-symfony`, a bundle with its own config). `wordpress` has no official page (see Init placement). Laravel is not served here: the engine routes it to `platforms/laravel`.

## Detect

| Signal | Where | Means |
|---|---|---|
| `sentry/sentry` | composer.json, composer.lock | plain SDK; the lockfile gives the real major |
| `sentry/sentry-symfony` | composer.json, composer.lock | Symfony bundle; config in `config/packages/sentry.yaml` |
| `sentry/sentry-laravel`, `laravel/framework` | composer.json | Laravel; engine fixture `evals/fixtures/laravel` is detected as framework `laravel` with framework module `platforms/laravel` (evals/expected/laravel.detect.json). Not this module |
| `\Sentry\init` | `*.php` | plain-SDK init site; read it and the entry file it sits in |
| `SENTRY_DSN` | `.env`, config files | DSN source; without a DSN the SDK sends no events |

Audit a WordPress repo with the same signals. No WordPress-specific Sentry fact is documented on the pages read.

## Install route

| Case | Route | Docs path (`sentry-ctx docs page <path>`) |
|---|---|---|
| Plain PHP | `composer require sentry/sentry`; prerequisites: PHP 7.2 or later, Composer | `platforms/php` (Install, Configure) |
| Profiling | `pecl install excimer`; Linux or macOS only, not Windows | `platforms/php/profiling` (Installation) |
| Symfony | `composer require sentry/sentry-symfony`, then `SENTRY_DSN` in `.env` | `platforms/php/guides/symfony` (Install, Configure) |
| Symfony + Monolog | see the Monolog integration page | `platforms/php/guides/symfony/integrations/monolog` |
| Laravel | not this module | `platforms/php/guides/laravel` |

No wizard or `sentry init` accelerator route for PHP appears on the pages read. Install from the live page; never paste install steps from memory.

## Init placement

| Case | Where Sentry must start | Right looks like |
|---|---|---|
| Plain PHP | the entry file every request or job loads (front controller, CLI bootstrap) | `\Sentry\init([...])` runs before the app boots. Docs: initialize "as soon as possible" so startup errors are captured |
| Symfony | bundle config `config/packages/sentry.yaml` plus `SENTRY_DSN` in `.env`; the Symfony page shows no `\Sentry\init` call | Bundle is enabled in every environment you deploy. Flex enables `prod` only; change this in `config/packages/sentry.yaml` and `config/bundles.php` |
| WordPress | no official page (`platforms/php/guides/wordpress` returns Page Not Found) | Audit as plain PHP and mark placement findings unconfirmed |
| Octane / Swoole / other long-running workers | no text on the pages read | see Unconfirmed |

## Options by SDK major

The pages read give 4.x defaults only; the v3.x column stays `—` until a 3.x page is fetched.

| option | v3.x | v4.x | note |
|---|---|---|---|
| `SENTRY_DSN` / `dsn` | — | env var read by default; no DSN means no events | silent no-send |
| `environment` | — | default `production`; env `SENTRY_ENVIRONMENT` | staging and dev must set it |
| `release` | — | env `SENTRY_RELEASE` | see Release and artifacts |
| `send_default_pii` | — | default `false`; supported until the next major | ignored when `data_collection` is also set |
| `data_collection` | — | since 4.33.0; default `null` | an array opts into permissive defaults |
| `traces_sample_rate` | — | default `null` | tracing is off unless this or `traces_sampler` is set |
| `traces_sampler` | — | function; default `null` | same enable rule as `traces_sample_rate` |
| `profiles_sample_rate` | — | default `null`; non-null enables profiling | relative to `traces_sample_rate` |
| `attach_stacktrace` | — | default `false` | changes grouping |
| `max_breadcrumbs` | — | default `100` | |
| `enable_logs` | — | default `false`; deprecated, no effect; removed in 5.0 | disable logs with `before_send_log` returning null |
| `enable_metrics` | — | default `true`; deprecated, no effect; removed in 5.0 | disable metrics with `before_send_metric` returning null |
| `trace_propagation_targets` | — | default `null` (headers to every outgoing request) | `[]` disables |
| `context_lines` | — | ignored when `data_collection` is set | use `frame_context_lines` |

## Product support matrix

| product | supported | notes |
|---|---|---|
| errors | yes | `captureException` in try/catch; `captureLastError` for the last PHP error (platforms/php Verify) |
| tracing | yes | needs `traces_sample_rate` or `traces_sampler`; `before_send_transaction` for filtering |
| profiling | yes, transaction-based | Excimer extension; tracing must be on; `profiles_sample_rate` |
| logs | yes | page `platforms/php/logs`; `enable_logs` is a no-op; drop logs in `before_send_log` |
| metrics | yes | page `platforms/php/metrics`; `enable_metrics` is a no-op; drop in `before_send_metric` |
| crons | yes | page `platforms/php/crons`; `before_send_check_in` option |
| feedback | yes | page `platforms/php/user-feedback` |
| feature flags | yes, beta | page `platforms/php/feature-flags`; matrix marks beta (generic) |
| replay | no | no PHP page (`platforms/php/session-replay` Page Not Found); research matrix shows no integration |
| AI monitoring | unconfirmed | research matrix: beta, Laravel only; no PHP AI page found |
| debug files | unconfirmed | no upload route on the pages read; see Release and artifacts |

## Release and artifacts

- `release`: the options page says the SDK reads `SENTRY_RELEASE` by default. No git-SHA or hosting-provider fallback is documented for PHP. Right = `SENTRY_RELEASE` (or `release`) set in the deploy environment and in CI; check the Dockerfile for it.
- `environment`: default `production`; `SENTRY_ENVIRONMENT` overrides only if the option is unset.
- Source maps, debug files, symbols: none uploaded for PHP on the pages read. Source context is captured at runtime: on an unhandled exception a snapshot of the lines around each stack frame is sent with the event (`frame_context_lines`, default `5`). Right = no PHP artifact upload step in CI; a finding if one is present and unexplained.
- No PHP-specific release CLI step is documented on the pages read. Do not invent one.

## Privacy

| Data | Default | Control |
|---|---|---|
| IP and user fields | not added by integrations while `send_default_pii` is `false` | `data_collection.user_info` (default `true` once `data_collection` is set) |
| Cookies | `denyList` once `data_collection` is set | `data_collection.cookies` |
| HTTP headers | `denyList` | `data_collection.http_headers` |
| URL query parameters | `denyList` | `data_collection.url_query_params` |
| Request and response bodies | all four body types | `data_collection.http_bodies` (`[]` disables) |
| Stack frame variables | `true` | `data_collection.stack_frame_variables` |
| Source context | 5 lines each side | `data_collection.frame_context_lines` |

Passing a `data_collection` array opts into these defaults, which are more permissive than `send_default_pii` set to `false`. Right = `data_collection` set explicitly from the privacy answers. Values whose keys match the built-in denylist (`auth`, `token`, `password`, and similar) are scrubbed. Remove more with `before_send` and `before_send_transaction` (sensitive-data page).

## Verify recipe

1. Add a temporary route, console command or script that runs the same bootstrap as production (Symfony: a controller or command; plain PHP: a route in the front controller or a CLI entry).
2. Inside it, throw a caught exception whose message contains a unique marker and send it with `\Sentry\captureException($exception)` in a `catch (\Throwable $exception)` block, as in the platforms/php Verify example.
3. Run it with the production DSN, environment and release. Confirm the event in Sentry with the marker in its title and the expected environment and release.
4. Remove the route, command or script and the marker. Check that `git status` shows no leftover file.

## Gotchas

- Silent no-send: no DSN means the SDK "will just not send any events" (options page). Tracing is off with `traces_sample_rate` `null` and no `traces_sampler`.
- Stack-trace arguments: set `zend.exception_ignore_args` to `Off` in php.ini, or errors arrive without argument values (platforms/php Configure; Symfony Configure).
- Profiling needs tracing on, `traces_sample_rate` set, and the Excimer extension. `profiles_sample_rate` is relative to `traces_sample_rate` (profiling page).
- `enable_logs` and `enable_metrics` look like switches but do nothing; the page says to disable with `before_send_log` / `before_send_metric` returning `null`.
- Setting both `data_collection` and `send_default_pii` silently ignores `send_default_pii`. An array is more permissive than `false`.
- `trace_propagation_targets` unset attaches `sentry-trace` and `baggage` headers to every outgoing HTTP request. Set it to your own hosts.
- Tracing adds to response time because PHP sends from inside the request. The profiling page recommends a local Relay (managed mode) to offload.
- Symfony Flex enables the bundle in `prod` only, so staging errors go unreported until `config/packages/sentry.yaml` and `config/bundles.php` change.
- The research notes list a PHP "source context" question and a Symfony Messenger item; the pages read answer the first (runtime, see Release) and do not cover the second (see Unconfirmed).

## Sources

- https://docs.sentry.io/platforms/php/ (Prerequisites, Install, Configure, Verify, Frameworks)
- https://docs.sentry.io/platforms/php/configuration/options/ (Core, Tracing, Profile, Logs, Metrics, Transport, Cron options)
- https://docs.sentry.io/platforms/php/guides/symfony/ (Install, Configure)
- https://docs.sentry.io/platforms/php/profiling/ (Installation, Enable Tracing, Enabling Profiling, Improve Response Time)
- https://docs.sentry.io/platforms/php/data-management/data-collection/ (Source Context, Keys)
- https://docs.sentry.io/platforms/php/data-management/sensitive-data/ (headings)
- https://docs.sentry.io/platforms/php/crons/, https://docs.sentry.io/platforms/php/logs/, https://docs.sentry.io/platforms/php/metrics/, https://docs.sentry.io/platforms/php/user-feedback/, https://docs.sentry.io/platforms/php/feature-flags/ (existence and headings)

## Identifiers

```identifiers
SENTRY_DSN | https://docs.sentry.io/platforms/php/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/php/configuration/options/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/php/configuration/options/
send_default_pii | https://docs.sentry.io/platforms/php/configuration/options/
data_collection | https://docs.sentry.io/platforms/php/configuration/options/
traces_sample_rate | https://docs.sentry.io/platforms/php/configuration/options/
traces_sampler | https://docs.sentry.io/platforms/php/configuration/options/
profiles_sample_rate | https://docs.sentry.io/platforms/php/configuration/options/
attach_stacktrace | https://docs.sentry.io/platforms/php/configuration/options/
max_breadcrumbs | https://docs.sentry.io/platforms/php/configuration/options/
enable_logs | https://docs.sentry.io/platforms/php/configuration/options/
enable_metrics | https://docs.sentry.io/platforms/php/configuration/options/
before_send | https://docs.sentry.io/platforms/php/configuration/options/
before_send_transaction | https://docs.sentry.io/platforms/php/configuration/options/
before_send_log | https://docs.sentry.io/platforms/php/configuration/options/
before_send_metric | https://docs.sentry.io/platforms/php/configuration/options/
before_send_check_in | https://docs.sentry.io/platforms/php/configuration/options/
trace_propagation_targets | https://docs.sentry.io/platforms/php/configuration/options/
context_lines | https://docs.sentry.io/platforms/php/configuration/options/
frame_context_lines | https://docs.sentry.io/platforms/php/data-management/data-collection/
user_info | https://docs.sentry.io/platforms/php/data-management/data-collection/
http_headers | https://docs.sentry.io/platforms/php/data-management/data-collection/
http_bodies | https://docs.sentry.io/platforms/php/data-management/data-collection/
url_query_params | https://docs.sentry.io/platforms/php/data-management/data-collection/
stack_frame_variables | https://docs.sentry.io/platforms/php/data-management/data-collection/
zend.exception_ignore_args | https://docs.sentry.io/platforms/php/
captureException | https://docs.sentry.io/platforms/php/
captureLastError | https://docs.sentry.io/platforms/php/
\Sentry\init | https://docs.sentry.io/platforms/php/
sentry/sentry-symfony | https://docs.sentry.io/platforms/php/guides/symfony/
denyList | https://docs.sentry.io/platforms/php/data-management/data-collection/
```

## Unconfirmed

- `isolate_context_by_message`: research note only (Symfony Messenger workers); no fetched page states it.
- Symfony callbacks must be service references: research note only; no fetched page states it.
- Octane / Swoole / long-running workers: the event flush and shutdown behaviour is not stated on the PHP pages read (grep for octane, swoole, flush, shutdown returned nothing).
- Event flush at process exit for plain PHP and CLI: not stated on the pages read.
- WordPress integration and init placement: no page (`platforms/php/guides/wordpress` Page Not Found).
- `sentry.yaml` keys under the bundle root: the Symfony configuration index lists no child pages; check the bundle's own config tree before auditing keys.
- AI monitoring on PHP: research matrix says beta, Laravel only; no PHP AI page found (`platforms/php/tracing/instrumentation/ai-agents-module` Page Not Found).
- Debug files, source maps, symbol upload: none documented on the pages read.
- Release fallback beyond `SENTRY_RELEASE` (git SHA or hosting env): not documented for PHP on the pages read.
- `Raven_Client`: legacy-SDK marker from the research notes; no fetched page states it.
- v3.x defaults for every option: pages read give 4.x only.
