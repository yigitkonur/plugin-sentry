# Laravel (module: platforms/laravel)

Framework id `laravel`: the `sentry/sentry-laravel` package on top of the PHP SDK. Docs page: `platforms/php/guides/laravel`. Most configuration lives in `.env`; extra keys go in `config/sentry.php` (laravel-options page). PHP-wide option names are on `platforms/php/configuration/options`. The only older-version floor on the pages read is the crons minimum (sentry-laravel 3.3.1); everything else is stated for the current docs.

## Detect

| Signal | Where | Means |
|---|---|---|
| `laravel/framework` (or `laravel/laravel`) | composer.json, composer.lock | Laravel app; the engine's dep match for id `laravel` |
| `sentry/sentry-laravel` | composer.json, composer.lock | SDK present; the lock gives the real version |
| `Integration::handles(` | bootstrap/app.php | exception capture wired; the engine's PHP init pattern matches this |
| `SENTRY_LARAVEL_DSN` | config/sentry.php (`'dsn' => env('SENTRY_LARAVEL_DSN')`), .env | DSN source |
| `->sentryMonitor()` | routes/console.php (Laravel 11+), app/Console/Kernel.php (8-10) | scheduled-task monitors (crons) |
| `config/sentry.php` | config/ | option keys, see Options by SDK major |

Read first: bootstrap/app.php, config/sentry.php, .env, composer.lock, and the scheduler file. The fixture `evals/fixtures/laravel` detects Laravel 11.31.0 with init sites `bootstrap/app.php:17` and `config/sentry.php:4`, and pins `sentry/sentry-laravel` 4.10.0 (declared ^4.10).

## Install route

Manual only. `data/detect/frameworks.json` gives `laravel` no wizard id (its docs platform is `php/guides/laravel`). Read the steps from the live page, not from memory: `sentry-ctx docs page platforms/php/guides/laravel --section Install` and `--section Configure`. `php artisan sentry:publish --dsn=...` creates `config/sentry.php` and writes `SENTRY_LARAVEL_DSN` to `.env`.

## Init placement

| Where | Right looks like | Source |
|---|---|---|
| `bootstrap/app.php`, inside `->withExceptions(function (Exceptions $exceptions) {...})` | calls `Integration::handles($exceptions);` | guide, Install |
| `config/sentry.php` | exists; `'dsn' => env('SENTRY_LARAVEL_DSN')` | guide, Configure |
| `.env` | `SENTRY_LARAVEL_DSN` set in every deployed environment | guide, Configure |
| `routes/console.php` (Laravel 11/12) or `app/Console/Kernel.php` (8-10) | `->sentryMonitor()` on each scheduled task | crons page |
| Queue workers | no separate init; job transactions come with tracing (`queue_job_transactions`, default `true`) | laravel-options |

The DSN in `config/sentry.php` is a config key, not a second init site.

## Options by SDK major

| option (env) | v3 (N-1) | v4 (current) | note |
|---|---|---|---|
| `dsn` (`SENTRY_LARAVEL_DSN` here; `SENTRY_DSN` in PHP docs) | not read | set | empty DSN: "the SDK will just not send any events" (PHP options) |
| `traces_sample_rate` (`SENTRY_TRACES_SAMPLE_RATE`) | not read | default `null` = tracing off | greater than 0.0 enables; guide says lower it in production |
| `traces_sampler` | not read | callable | per-request decision |
| `profiles_sample_rate` | not read | sample rate relative to `traces_sample_rate` | profiling page |
| `send_default_pii` | not read | default `false` (PHP options) | "remains fully supported until the next major version" |
| `data_collection` | not read | default `null`; "Available since 4.33.0" (PHP SDK) | when set, `send_default_pii` is ignored; more permissive |
| `log_flush_threshold` (`SENTRY_LOG_FLUSH_THRESHOLD`) | not read | unset = no auto flush | laravel-options |
| `release` (`SENTRY_RELEASE`) | not read | read from env by default | PHP options |
| `environment` (`SENTRY_ENVIRONMENT`) | not read | default `production` | PHP options |

The v3 column is blank on purpose: the pages read do not describe v3 differences.

## Product support matrix

| product | supported | notes |
|---|---|---|
| Errors | yes | `Integration::handles` is required for unhandled exceptions; `zend.exception_ignore_args` must be Off for argument values in traces |
| Tracing | yes | `SENTRY_TRACES_SAMPLE_RATE` above 0.0 enables; default null disables; queue jobs are traced with it by default |
| Profiling | yes for PHP; Laravel wiring unconfirmed | PHP profiling page: install the extension (Installation section), then `profiles_sample_rate`; the Laravel guide does not mention profiling |
| Replay | no | research matrix shows no PHP session replay page |
| Logs | yes | `sentry_logs` channel in `LOG_STACK`; `SENTRY_LOG_LEVEL` defaults to `LOG_LEVEL`; sentry-laravel 4.16.0 and below need a manual channel |
| Metrics | unconfirmed | PHP options page has a Metrics Options section; no Laravel page read |
| Crons | yes | `->sentryMonitor()` on scheduled tasks; needs sentry-laravel 3.3.1+; each monitor counts against quota |
| Feedback | yes | crash-report modal guide exists at `platforms/php/guides/laravel/user-feedback`; not read in detail |
| AI monitoring | unconfirmed | see Unconfirmed |
| Feature flags | unconfirmed | see Unconfirmed |

## Release and artifacts

- Release string: the PHP options page says the SDK reads `SENTRY_RELEASE` by default. It says some SDKs set a release automatically but that setting it manually is "a better idea". It documents no git-SHA or hosting fallback for PHP. Right looks like: `config/sentry.php` keeps `'release' => env('SENTRY_RELEASE')` and the deploy sets the same string it reports to Sentry. The fixture has this shape.
- Environment: `SENTRY_ENVIRONMENT`, default `production`. Staging and dev must set it.
- Source maps, debug files, symbols: no upload step on the guide or options pages read. Do not require one.
- CI release creation for PHP is not on the pages read (see Unconfirmed).

## Privacy

| Data | Default | Control |
|---|---|---|
| User id, email, IP, cookies, request and response bodies (added by active integrations) | off: `send_default_pii` is `false` | `send_default_pii`, or `data_collection`. Once a `data_collection` array is passed it is more permissive (IP, cookies, bodies collected); keys such as `auth`, `token`, `password` are scrubbed. If both are set, `send_default_pii` is ignored. |
| Breadcrumbs: logs, cache, Livewire, SQL queries, queue info, commands, HTTP client requests, notifications | on (each is `env(..., true)` in the laravel-options code) | `breadcrumbs` array in `config/sentry.php`; per-breadcrumb env vars |
| SQL bindings (parameters) in breadcrumbs and spans | off | `SENTRY_BREADCRUMBS_SQL_BINDINGS_ENABLED`, `SENTRY_TRACE_SQL_BINDINGS_ENABLED` |
| Fixture `config/sentry.php` | `send_default_pii => true` | audit finding unless the team chose it; the options page links the Sensitive Data page for scrubbing |

## Verify recipe

1. Transport check: `php artisan sentry:test` (guide, Verify With Artisan). The guide does not say which code path it exercises, so it does not prove the exception handler.
2. Real path: add a temporary route to `routes/web.php` that throws a marked exception:

```php
Route::get('/debug-sentry', function () {
    throw new Exception('sentry-verify 2026-10-20');
});
```

Request it over HTTP. The exception goes through the `bootstrap/app.php` handler, so `Integration::handles` is exercised. Find the event in Issues by the marker text.

3. Remove: delete the route block, and clear cached routes if you built them (`php artisan route:clear`). Queue jobs and scheduled commands are not covered by the route; check them with a separate temporary trigger only when the audit needs it, and remove that trigger too.

## Gotchas

- Missing `Integration::handles`: unhandled exceptions are not reported. Guide, Install: the change is what "enable[s] capturing unhandled exception". The research note agrees.
- Silent off-switches: an empty DSN means "the SDK will just not send any events" (PHP options); tracing stays off at the default null. Check `.env` in the deployed environment, not only the repo.
- Fixture `config/sentry.php` sets `traces_sample_rate => 1.0` and `send_default_pii => true`. The guide warns to lower the traces rate in production, and `send_default_pii` adds PII (see Privacy).
- `zend.exception_ignore_args` must be Off in php.ini for argument values to appear in stack traces (guide, Configure).
- `send_default_pii` and `data_collection`: when both are set, `send_default_pii` is ignored (PHP options).
- Scheduler: `sentryMonitor()` does not support Laravel's `between`, `unlessBetween`, `when`, or `skip`. Use the `cron` method for frequency (crons page). Each monitor counts against quota.
- Logs: `sentry_logs` must be in `LOG_STACK`. sentry-laravel 4.16.0 and below need the channel configured by hand (logs page).
- Job tracing: `Sentry\Laravel\Jobs\Middleware\SentryTracesSampleRate` can only lower the rate of jobs already sampled; it does not upsample (laravel-options).
- Disagreement with the research notes: they say the guide is Laravel 11+ only. The guide text does not say that. The crons page documents Laravel 8-10 (`app/Console/Kernel.php`), and the `other-versions` page exists but was not read. For an app older than 11, read that page before recommending the `bootstrap/app.php` snippet.

## Sources

- https://docs.sentry.io/platforms/php/guides/laravel.md
- https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
- https://docs.sentry.io/platforms/php/guides/laravel/crons.md
- https://docs.sentry.io/platforms/php/guides/laravel/logs.md
- https://docs.sentry.io/platforms/php/guides/laravel/user-feedback.md (listing only)
- https://docs.sentry.io/platforms/php/guides/laravel/other-versions.md (listing only)
- https://docs.sentry.io/platforms/php/configuration/options.md
- https://docs.sentry.io/platforms/php/profiling.md
- https://docs.sentry.io/platforms/php/crons.md (listing only)

## Identifiers

```identifiers
sentry/sentry-laravel | https://docs.sentry.io/platforms/php/guides/laravel.md
Integration::handles | https://docs.sentry.io/platforms/php/guides/laravel.md
withExceptions | https://docs.sentry.io/platforms/php/guides/laravel.md
SENTRY_LARAVEL_DSN | https://docs.sentry.io/platforms/php/guides/laravel.md
SENTRY_TRACES_SAMPLE_RATE | https://docs.sentry.io/platforms/php/guides/laravel.md
traces_sample_rate | https://docs.sentry.io/platforms/php/guides/laravel.md
zend.exception_ignore_args | https://docs.sentry.io/platforms/php/guides/laravel.md
sentry:publish | https://docs.sentry.io/platforms/php/guides/laravel.md
sentry:test | https://docs.sentry.io/platforms/php/guides/laravel.md
Route::get | https://docs.sentry.io/platforms/php/guides/laravel.md
sentryMonitor | https://docs.sentry.io/platforms/php/guides/laravel/crons.md
unlessBetween | https://docs.sentry.io/platforms/php/guides/laravel/crons.md
traces_sampler | https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
queue_job_transactions | https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
Sentry\Laravel\Jobs\Middleware\SentryTracesSampleRate | https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
sql_bindings | https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
SENTRY_TRACE_SQL_BINDINGS_ENABLED | https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
SENTRY_BREADCRUMBS_SQL_BINDINGS_ENABLED | https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
log_flush_threshold | https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
SENTRY_LOG_FLUSH_THRESHOLD | https://docs.sentry.io/platforms/php/guides/laravel/configuration/laravel-options.md
sentry_logs | https://docs.sentry.io/platforms/php/guides/laravel/logs.md
LOG_STACK | https://docs.sentry.io/platforms/php/guides/laravel/logs.md
LOG_LEVEL | https://docs.sentry.io/platforms/php/guides/laravel/logs.md
SENTRY_LOG_LEVEL | https://docs.sentry.io/platforms/php/guides/laravel/logs.md
SENTRY_DSN | https://docs.sentry.io/platforms/php/configuration/options.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/php/configuration/options.md
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/php/configuration/options.md
send_default_pii | https://docs.sentry.io/platforms/php/configuration/options.md
data_collection | https://docs.sentry.io/platforms/php/configuration/options.md
profiles_sample_rate | https://docs.sentry.io/platforms/php/profiling.md
```

## Unconfirmed
- `laravel-ai`: AI monitoring for Laravel. The research matrix says beta, Laravel only; no fetched page confirms it.
- Metrics on Laravel: the research matrix says GA from 4.19; no Laravel metrics page was read.
- Feature flags for PHP and Laravel: the research matrix says beta (generic); no page read.
- `sentry-laravel 4.29.0`: current version per research notes; no fetched page states it.
- Release fallback for PHP (git SHA or hosting env): not on the pages read.
- PHP CI release-creation step: not on the pages read; the options page links the releases docs at `https://docs.sentry.io/product/releases.md`, which was not fetched.
- Whether `php artisan sentry:test` runs the exception handler: the guide does not say.
- `data_collection` in the Laravel package: the options page says "Available since 4.33.0" for the PHP SDK; the Laravel package pins its own `sentry/sentry`, which was not checked.
