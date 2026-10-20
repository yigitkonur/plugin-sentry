# Cron monitoring (product id: crons)

## Fit
Propose when the repo runs scheduled work and a missed, late or hung run would go unnoticed. The applicability rule is in data/signals.tsv (row crons): it needs the scheduler signal (cond jobs, sig:scheduler). With no scheduler found the reason is "no scheduled jobs found" and the product does not apply.

Scheduler evidence to scan for, and the route each one takes (details in Properly configured):

| Repo evidence | Where to look | Route |
|---|---|---|
| Celery beat | `beat_schedule` in the Celery app module; a beat process in Procfile, compose or Helm files | Celery integration with `monitor_beat_tasks` |
| APScheduler | add_job calls and scheduler setup | no automatic route on the pages read; decorator, manual check-ins or CLI |
| node-cron, cron, node-schedule | package.json; schedule and CronJob calls | `Sentry.cron.instrumentNodeCron`, `Sentry.cron.instrumentCron`, `Sentry.cron.instrumentNodeSchedule` |
| Vercel Cron Jobs on Next.js | `crons` in `vercel.json` | `_experimental.vercelCronsMonitoring` |
| Laravel scheduler | Schedule entries in routes/console.php or app/Console/Kernel.php | `sentryMonitor` on the schedule entry |
| sidekiq-cron, sidekiq-scheduler | Gemfile; schedule definitions | `enabled_patches` with `sidekiq_cron` or `sidekiq_scheduler` |
| Kubernetes CronJob, GitHub Actions schedule trigger, host crontab | manifests of kind CronJob; `.github/workflows/*.yml` with a schedule trigger; crontab files | CLI wrapper, `sentry-cli monitors run`, around the command |

Worth proposing: a job whose silent failure matters (money, mail, data sync, backups) and that has no failure alert today. Monitors also show "missed" and "failed by timeout", which error tracking does not see on its own.

Not worth proposing:
- no scheduler signal (the rule above), or schedules only in tests, examples, fixtures or dev-only compose files;
- a schedule that already has one monitor route (add no second one);
- no org access: monitor and alert state cannot be checked (the repo-side checks still run).

## Properly configured
One mechanism per job. Pick the row that matches the code and never stack two.

| SDK route | Right setup | Version and limits |
|---|---|---|
| Python decorator or context manager | `monitor` wraps the whole job with `monitor_slug` and `monitor_config`; `schedule` is the only required key | `monitor_config` needs SDK 1.45.0+; async functions 1.44.1+ |
| Python with Celery beat | `CeleryIntegration` with `monitor_beat_tasks` set to True, initialised in `celeryd_init`, and in `beat_init` when beat runs in its own process. No `sentry_sdk.monitor` on those tasks. `exclude_beat_tasks` skips tasks | Monitor is created on the task's first run only |
| Python manual | `capture_checkin` with status IN_PROGRESS, then status OK using the returned `check_in_id`; send `monitor_config` on the first call | Use when neither the decorator nor the Celery route fits |
| Node wrapper | `Sentry.withMonitor` takes the slug, the job function and the config as third argument | `failureIssueThreshold` and `recoveryThreshold` need SDK 8.7.0+ |
| Node manual | `Sentry.captureCheckIn` with `monitorSlug` and status `in_progress`; the closing call passes `checkInId` and status `ok` | Config is the second argument |
| Node library hooks | `Sentry.cron.instrumentCron` (cron, 7.92.0+), `Sentry.cron.instrumentNodeCron` (node-cron, 7.92.0+), `Sentry.cron.instrumentNodeSchedule` (node-schedule, 7.93.0+). The schedule goes with each check-in, so Sentry creates the monitor | node-cron needs an IANA zone name, not a luxon zone |
| Next.js on Vercel | `_experimental.vercelCronsMonitoring` set to true in the Sentry options in next.config.js; instrumented jobs are read at runtime from `vercel.json` `crons` | Experimental. The older `webpack.automaticVercelMonitors` works only with Webpack and the Pages Router |
| Ruby | `enabled_patches` gets `sidekiq_cron` or `sidekiq_scheduler`; ActiveJob or Sidekiq jobs include the MonitorCheckIns mixin with `sentry_monitor_check_ins`; manual check-ins use `capture_check_in` | A slug with no monitor and no `monitor_config` is dropped |
| Laravel | `sentryMonitor` on each scheduled entry, named arguments `monitorSlug`, `checkInMargin`, `maxRuntime`, `failureIssueThreshold`, `recoveryThreshold`, `updateMonitorConfig` | With `updateMonitorConfig` false a `monitorSlug` is required |
| Any other command (shell, CronJob, CI step) | `sentry-cli monitors run` with the command after the separator; `--schedule`, `--check-in-margin`, `--max-runtime`, `--timezone` create or update the monitor; short forms -s and -e | Authorise with the DSN (`SENTRY_DSN` or the CLI config file). Auth-token check-ins are deprecated from CLI 2.16.1 |

Monitor config keys (same meaning, SDK spelling differs; do not mix spellings):

| Meaning | Python | Node / Next.js | Laravel | Rule |
|---|---|---|---|---|
| schedule | schedule | schedule | inferred from the entry | crontab or interval; an interval `value` is an integer, not a string |
| zone | `timezone` | `timezone` | not in the example | IANA name of the zone the scheduler runs in |
| grace before missed | `checkin_margin` | `checkinMargin` | `checkInMargin` | Node recommends a margin at most the interval |
| max runtime | `max_runtime` | `maxRuntime` (max 10080) | `maxRuntime` | minutes before an in-progress run counts as failed |
| issue after N failures | `failure_issue_threshold` | `failureIssueThreshold` | `failureIssueThreshold` | consecutive failed check-ins before an issue opens |
| resolve after N OK | `recovery_threshold` | `recoveryThreshold` | `recoveryThreshold` | consecutive OK check-ins before the issue resolves |

- Unset keys have no default (Python page). Set margin and max runtime from the job's real timing.
- One slug per job. Environments share one monitor and one schedule; each environment has its own status and its own rate budget. Use a separate slug only when the schedules differ.
- The check-in environment comes from the SDK environment setting. A single monitor environment cannot be paused, and there is no aggregate status across environments (job-monitoring page).
- Alerts: filter on `monitor.slug` and scope to the environments that matter.

## Checks
| check id | read | passes when |
|---|---|---|
| cron.coverage | Scheduler registrations: `beat_schedule` in the Celery config; add_job calls; node-cron, cron and node-schedule calls; `crons` in `vercel.json`; Schedule entries in routes/console.php and app/Console/Kernel.php; sidekiq-cron and sidekiq-scheduler entries; CronJob manifests; schedule triggers in `.github/workflows/*.yml`. For each registration grep its file and init for one monitor route: `Sentry.withMonitor`, `Sentry.captureCheckIn`, `Sentry.cron.instrumentCron`, `Sentry.cron.instrumentNodeCron`, `Sentry.cron.instrumentNodeSchedule`, `sentryMonitor`, `sentry_monitor_check_ins`, `enabled_patches`, `monitor_beat_tasks`, `_experimental.vercelCronsMonitoring`, `sentry-cli monitors run`, `capture_checkin`, and the `monitor` decorator | Every scheduler registration has exactly one monitor route from Properly configured (platform auto-instrumentation, one decorator or call, or one CLI wrapper). A registration with none, or with two, is a finding, reported with file and line |
| cron.config | Each monitor call and wrapper: the slug literal; the schedule argument against the scheduler's own expression (crontab string or interval `value`); `timezone`, `checkin_margin` or `checkinMargin`, `max_runtime` or `maxRuntime`; SDK version in pyproject.toml, requirements files, package.json or Gemfile; the Celery init for `monitor_beat_tasks`; `sentry-cli monitors run` lines for the slug and the `-e` flag | Slugs are unique string literals. Each schedule equals the scheduler's cadence, and an interval `value` is an integer. Margin and max runtime are set. `timezone` names the zone the scheduler runs in. No task carries both `monitor_beat_tasks` and a manual monitor. SDK versions meet the key minimums (Python 1.45.0; JS 8.7.0 for thresholds, 7.92.0 for `Sentry.cron`). CLI steps authenticate with a DSN, not an auth token |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Job ran, Sentry reports missed or late | Monitor schedule, timezone or margin differs from the real scheduler | Match `schedule`, `timezone` and `checkin_margin` to the scheduler's config | python crons; node crons |
| No monitor appears, check-ins missing | Slug has no monitor and the check-in carries no `monitor_config`; Sentry drops it | Send the config on the first check-in | ruby crons |
| Celery task shows no monitor until it runs | Beat auto-discovery creates the monitor on the first run only | Run the task once after deploy and confirm the row appears | celery crons |
| Duplicate check-ins for one Celery task | `monitor_beat_tasks` plus `sentry_sdk.monitor` on the same task | Remove the manual decorator; keep the beat integration | celery crons |
| Interval monitor wrong or missing | Interval `value` sent as a string | Use an integer `value` | python crons |
| Check-ins dropped, rate-limited in Usage Stats | More than 6 check-ins per minute per monitor environment | Lower the frequency or fix the job; a per-minute job is not a cron monitor | python crons; node crons |
| Failure happened, no issue opened | `failure_issue_threshold` above 1, so the consecutive count was not reached | Set the threshold on purpose | python crons |
| Failures happen, no notification | Alert rule not filtered on the `monitor.slug` tag | Filter the alert on `monitor.slug` equal to the slug | python crons (Alerts) |
| Pause wanted for one environment only | Not possible; each environment is its own row | Scope alerts to environments instead | job-monitoring |
| Monitor silent for weeks, no alerts | Automatic muting after a long broken period; muting does not stop billing | Find and fix the cause; mute is not a fix | job-monitoring |
| Vercel auto check-ins missing | Flag off, job not listed in `vercel.json` `crons`, or the old `webpack.automaticVercelMonitors` option on Turbopack or the App Router | Set `_experimental.vercelCronsMonitoring` and list the job | nextjs crons |
| Laravel check-ins unmatched | `updateMonitorConfig` false without a `monitorSlug` | Pass `monitorSlug` | laravel crons |
| CLI check-ins rejected after an upgrade | Auth token used; deprecated from CLI 2.16.1 | Authorise with the project DSN | cli crons |

## Volume, cost and overhead
| Category | Billed as | Included | Beyond that |
|---|---|---|---|
| Cron monitors | monitors | one cron monitor on every plan | PAYG budget only |

- Pricing page: "All Sentry plans include one cron monitor and one uptime monitor. Additional monitors can only be purchased with your PAYG budget."
- A repo with many scheduled jobs needs a PAYG budget before every job gets a monitor: propose the critical jobs first (Fit).
- Muting does not stop billing (job-monitoring page).
- Overhead: a wrapped run sends a start check-in and an outcome check-in over HTTP; the cap is 6 per minute per monitor environment (python crons, node crons).

## Verify (R6)
1. CLI proof, on a throwaway slug: `sentry-cli monitors run --schedule "0 0 1 1 *" <test-slug> -- true`, then the same with a failing command (`-- sh -c "exit 1"`). The monitor row shows an OK check-in, then an error check-in. Delete the test monitor in the UI (no deletion route is on the pages read).
2. Real entry point: run the job's own command once in the target environment. The row for that environment shows `in_progress`, then `ok`.
3. Failure path, non-production only: make the job raise once. Expect an error check-in and, with `failure_issue_threshold` at 1, an issue tagged with `monitor.slug`. Remove the forced raise afterwards.
4. Drops: after a run, Usage Stats (UI) shows no rate-limited check-ins for the monitor. Record as UNVERIFIED without org access.

## Sources
- https://docs.sentry.io/pricing/
- https://docs.sentry.io/product/monitors-and-alerts/monitors/crons/
- https://docs.sentry.io/product/monitors-and-alerts/monitors/crons/job-monitoring/
- https://docs.sentry.io/platforms/python/crons/
- https://docs.sentry.io/platforms/python/integrations/celery/crons/
- https://docs.sentry.io/platforms/javascript/guides/node/crons/
- https://docs.sentry.io/platforms/javascript/guides/nextjs/crons/
- https://docs.sentry.io/platforms/php/guides/laravel/crons/
- https://docs.sentry.io/platforms/ruby/crons/
- https://docs.sentry.io/cli/crons/

## Identifiers
```identifiers
monitor_slug | https://docs.sentry.io/platforms/python/crons/
monitor_config | https://docs.sentry.io/platforms/python/crons/
capture_checkin | https://docs.sentry.io/platforms/python/crons/
MonitorStatus | https://docs.sentry.io/platforms/python/crons/
IN_PROGRESS | https://docs.sentry.io/platforms/python/crons/
check_in_id | https://docs.sentry.io/platforms/python/crons/
checkin_margin | https://docs.sentry.io/platforms/python/crons/
max_runtime | https://docs.sentry.io/platforms/python/crons/
failure_issue_threshold | https://docs.sentry.io/platforms/python/crons/
recovery_threshold | https://docs.sentry.io/platforms/python/crons/
monitor.slug | https://docs.sentry.io/platforms/python/crons/
monitor_beat_tasks | https://docs.sentry.io/platforms/python/integrations/celery/crons/
exclude_beat_tasks | https://docs.sentry.io/platforms/python/integrations/celery/crons/
CeleryIntegration | https://docs.sentry.io/platforms/python/integrations/celery/crons/
beat_schedule | https://docs.sentry.io/platforms/python/integrations/celery/crons/
beat_init | https://docs.sentry.io/platforms/python/integrations/celery/crons/
celeryd_init | https://docs.sentry.io/platforms/python/integrations/celery/crons/
sentry_sdk.monitor | https://docs.sentry.io/platforms/python/integrations/celery/crons/
Sentry.withMonitor | https://docs.sentry.io/platforms/javascript/guides/node/crons/
Sentry.captureCheckIn | https://docs.sentry.io/platforms/javascript/guides/node/crons/
Sentry.cron.instrumentCron | https://docs.sentry.io/platforms/javascript/guides/node/crons/
Sentry.cron.instrumentNodeCron | https://docs.sentry.io/platforms/javascript/guides/node/crons/
Sentry.cron.instrumentNodeSchedule | https://docs.sentry.io/platforms/javascript/guides/node/crons/
checkinMargin | https://docs.sentry.io/platforms/javascript/guides/node/crons/
checkInId | https://docs.sentry.io/platforms/javascript/guides/node/crons/
monitorSlug | https://docs.sentry.io/platforms/javascript/guides/node/crons/
in_progress | https://docs.sentry.io/platforms/javascript/guides/node/crons/
maxRuntime | https://docs.sentry.io/platforms/javascript/guides/node/crons/
failureIssueThreshold | https://docs.sentry.io/platforms/javascript/guides/node/crons/
recoveryThreshold | https://docs.sentry.io/platforms/javascript/guides/node/crons/
_experimental.vercelCronsMonitoring | https://docs.sentry.io/platforms/javascript/guides/nextjs/crons/
webpack.automaticVercelMonitors | https://docs.sentry.io/platforms/javascript/guides/nextjs/crons/
sentryMonitor | https://docs.sentry.io/platforms/php/guides/laravel/crons/
checkInMargin | https://docs.sentry.io/platforms/php/guides/laravel/crons/
updateMonitorConfig | https://docs.sentry.io/platforms/php/guides/laravel/crons/
enabled_patches | https://docs.sentry.io/platforms/ruby/crons/
sidekiq_cron | https://docs.sentry.io/platforms/ruby/crons/
sidekiq_scheduler | https://docs.sentry.io/platforms/ruby/crons/
sentry_monitor_check_ins | https://docs.sentry.io/platforms/ruby/crons/
capture_check_in | https://docs.sentry.io/platforms/ruby/crons/
sentry-cli monitors run | https://docs.sentry.io/cli/crons/
--schedule | https://docs.sentry.io/cli/crons/
--check-in-margin | https://docs.sentry.io/cli/crons/
--max-runtime | https://docs.sentry.io/cli/crons/
--timezone | https://docs.sentry.io/cli/crons/
SENTRY_DSN | https://docs.sentry.io/cli/crons/
```

## Unconfirmed
- `add_job`: APScheduler route; no Sentry page read covers APScheduler. Verify before proposing an automatic route.
- Vercel auto check-ins outside Next.js: no page read covers it.
- Per-environment billing (environments of one monitor count once): research note only; the pricing page read does not state it.
- Monitor deletion route (API or CLI): no page read documents it; UI-only until confirmed.
- Check-in data residency (stored in the US): research note only; no page read states it.
- PHP, Go, Java and Quartz or Hangfire routes: not read in this run, so not stated here.
