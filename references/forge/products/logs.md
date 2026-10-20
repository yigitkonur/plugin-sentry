# Logs (product id: logs)

## Fit
The `logs` row in data/signals.tsv applies on `sig:logging` or `policy:logs`. With no logging library and no logs policy, the row says "add Sentry logs only if wanted".

Worth proposing when the repo shows:

| Repo evidence | Why it matters |
|---|---|
| A logging library: Python `logging` or loguru; Logback (`logback.xml`); Microsoft.Extensions.Logging, Serilog, NLog or log4net (.NET); a JS console or Consola wrapper | Existing records can be forwarded by an integration, with no new call sites |
| Calls with fields such as `order_id` and `user_id`, not only interpolated text | Fields become searchable attributes; JS values passed through `Sentry.logger.fmt` are extracted as attributes |
| Sentry errors or traces already set up in the same services (`sentry_sdk.init`, `Sentry.init`, `SentrySdk.Init`) | Logs carry the trace ID, so they join the errors and spans of one request |
| An org plan that lists logs, and a PAYG budget set or planned | Logs above the included 5GB are PAYG-only |

Not worth proposing when:
- There is no logging library and no logs policy.
- The only output is `print` or `console.log` in scripts, tests or local tooling that never runs in production.
- The org plan is not one that lists logs (the quota page lists Team, Business and Developer plans). Report it UNVERIFIED instead of proposing logs.
- Code logs once per call or per loop iteration. The JS docs ask for one wide log per operation instead of scattered thin lines, and billing is by volume.

## Properly configured
Check the installed SDK major first. The switch that turns logs on differs by SDK.

| SDK | Logs on when | Logging-integration records | Drop or rewrite hook |
|---|---|---|---|
| JS 10.71.0 and later | On by default; `Sentry.logger` needs nothing | `consoleLoggingIntegration` with an explicit `levels` list (the docs example uses log, warn, error) | `beforeSendLog` receives `level`, `message`, `timestamp`, `attributes`; return `null` to drop |
| JS 9.41.0 to 10.70.x | Opt-in: `enableLogs: true` in `Sentry.init` | Same integration | Same |
| JS 11 | `enableLogs` was removed. Logs are captured when `Sentry.logger` or `Sentry.metrics` is used, or when a logging integration is added | Add the integration explicitly | Same |
| Python | `sentry_sdk.logger` sends automatically | `LoggingIntegration(capture_sentry_logs=True)` or `LoguruIntegration(capture_sentry_logs=True)`; the deprecated `enable_logs` applies only when `capture_sentry_logs` is unset | `before_send_log` receives a dict with `severity_text`, `body`, `attributes`; return `None` to drop |
| Java | Direct `Sentry.logger()` calls need no option since 8.59.0 | `logs.enabled` set to true (required for logging integrations such as Logback) | `getLogs().beforeSend`; return `null` to drop |
| .NET | `SentrySdk.Logger` calls are always sent (since 6.10.0) | `EnableLogs = true` for Microsoft.Extensions.Logging, Serilog, NLog and log4net | `SetBeforeSendLog`; a function from `SentryLog` to `SentryLog` or null |
| Apple, Android | Options page lists `beforeSendLog` | Setup route not read in this pass | `beforeSendLog` |

### Thresholds: which record becomes what
Each route has its own threshold. Raising one does not change the others.

| Route | Python `LoggingIntegration` default | Logback `SentryAppender` default | Result |
|---|---|---|---|
| Error event (issue) | `event_level` = ERROR | `minimumEventLevel` = ERROR | Counts against the errors quota |
| Breadcrumb | `level` = INFO | `minimumBreadcrumbLevel` = INFO | Sent with the next event; not a log entry |
| Log entry | `sentry_logs_level` = INFO, only with `capture_sentry_logs=True` | `minimumLevel` = INFO | Counts against the logs GB quota |

Rules that follow from the table:
- Python: a record reaches the SDK only if its logger's own level allows it. An unset logger defaults to WARNING, so INFO never shows. Set the level on the logger; use `force=True` where a framework such as uvicorn resets logging. Silence a noisy logger with `ignore_logger` (breadcrumbs and events) and `ignore_logger_for_sentry_logs` (logs).
- Logback: the appender must receive records below both thresholds, so its own level must be lower than `minimumBreadcrumbLevel` and `minimumEventLevel`. The docs example sets `minimumEventLevel` to WARN, which turns WARN records into events. Keep it at ERROR unless the team chose otherwise.
- JS: pass `levels` to `consoleLoggingIntegration` explicitly. The page states no default.
- Volume controls, cheapest first: level threshold, then hook, then the inbound log-message filter. No sample-rate option for logs appears on the pages read.

### Hook and attribute hygiene
- `beforeSendLog` (JS, Apple, Android, Java) and `before_send_log` (Python) drop chatty entries and strip secrets. The JS example deletes the `password` attribute and returns the log.
- JS `Sentry.setAttribute` (10.61.0+) adds an attribute to every log. Use it for shared fields such as tenant, not per entry.
- JS console arguments become `message.parameter.N` attributes (10.13.0+). Python `attributes` values are documented as str, bool, float or int, so pass fields, not whole objects.
- One wide log per operation with its context, not several thin lines (JS Best Practices, "Wide Events Over Scattered Logs"). Use one attribute naming convention across services ("Consistent Attribute Naming" on each SDK page).

## Checks
| check id | read | passes when |
|---|---|---|
| log.enabled | Init files that call `sentry_sdk.init`, `Sentry.init` or `SentrySdk.Init`; logging config (`logback.xml`, `LoggingIntegration(` and `LoguruIntegration(` calls); the JS SDK version in `package.json` or the lockfile. Grep the repo for the switch names `enableLogs`, `consoleLoggingIntegration`, `capture_sentry_logs`, `LoguruIntegration`, `logs.enabled` and `EnableLogs` | Each switch matches its SDK major: JS 9.41 to 10.70 sets `enableLogs: true` when logs are wanted; JS 10.71 and later needs none; JS 11 has no `enableLogs` (delete a leftover); Python sets `capture_sentry_logs=True` on each integration that should send logs; Java sets `logs.enabled` true when a logging integration sends logs; .NET sets `EnableLogs = true` only for logging integrations; no switch is set without a logging path that uses it |
| log.hooks | The same init files and `logback.xml`. Grep the repo for the hook names `beforeSendLog`, `before_send_log`, `SetBeforeSendLog` and `beforeSend`. Read the threshold values `event_level`, `sentry_logs_level`, `level`, `minimumLevel`, `minimumEventLevel` and `levels` where they are set | A hook exists where chatty or sensitive records are produced; it returns `null` for dropped entries and the log object otherwise; it removes secret and personal attribute keys before returning; every threshold above is set explicitly rather than left at its default; no ERROR-level record reaches the event route unless the team chose that (`event_level` None or set deliberately, `minimumEventLevel` ERROR) |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Python ERROR log lines show up as issues | `event_level` defaults to ERROR, so each record becomes an error event | Set `event_level` to None, or decide per logger | python/integrations/logging |
| WARN lines create issues on Java | The docs example sets `minimumEventLevel` to WARN | Keep ERROR unless the team chose WARN | java/guides/logback |
| INFO entries flood the logs quota | `sentry_logs_level` and Logback `minimumLevel` both default to INFO | Raise the threshold; drop in the hook; add a log-message inbound filter | python/integrations/logging, java/guides/logback, pricing/quotas/manage-logs-quota |
| Python INFO records never reach Sentry | The logger's level is unset, so it is WARNING | Set the level on the logger; use `force=True` where a framework resets logging | python/integrations/logging |
| Logback records missing with a configured appender | The appender level is not below `minimumBreadcrumbLevel` and `minimumEventLevel`, so it never receives the records | Set the appender level below both thresholds | java/guides/logback |
| Library logs absent after adding the SDK | The integration flag is off: `capture_sentry_logs` (Python), `logs.enabled` (Java), `EnableLogs` (.NET) | Set the flag. The pages require it; the research note that library logs forward automatically is wrong | python/integrations/logging, java/logs, dotnet/logs |
| JS v11 config still sets `enableLogs` | The option was removed in v11; logs come from the API or an integration | Delete the option; add `consoleLoggingIntegration` if console output was meant | javascript/migration/v10-to-v11 |
| Config copied from the quota page | Its JS example still sets `enableLogs: true`; its Python snippet quotes the keyword names and is not valid Python | Use the platform page snippets | pricing/quotas/manage-logs-quota |
| .NET `EnableLogs = false` does not stop `SentrySdk.Logger` output | The option covers logging integrations only; `SentrySdk.Logger` is always sent | Drop in `SetBeforeSendLog` | dotnet/logs |
| Inbound filter on IP or user agent does not drop logs | Log filters are log message (glob) and releases only | Use the hook, or a log-message glob | pricing/quotas/manage-logs-quota |
| Log messages differ on every entry and cannot be grouped | Values interpolated into the message string | JS: `Sentry.logger.fmt`; Python: pass fields in `extra`, which the integration promotes to attributes | javascript/logs, python/integrations/logging |

## Volume, cost and overhead
| Item | Fact | Source |
|---|---|---|
| Unit | Logs are billed in GB. All plans include 5GB of logs; more needs the PAYG budget | pricing |
| Plans | Logs are available on Team, Business and Developer plans | pricing/quotas/manage-logs-quota |
| PAYG | Owners get notification emails as usage nears quota and can raise or lower the PAYG budget | pricing/quotas/manage-logs-quota |
| Spike protection | Covers errors, transactions or spans, and attachments only; logs are not covered | pricing/quotas/spike-protection |
| Inbound filters | Log message (glob) and releases only; filtered logs do not count against quota, but are still sent | pricing/quotas/manage-logs-quota |
| Hook | `beforeSendLog` filters before sending, so dropped entries never leave the SDK | pricing/quotas/manage-logs-quota |
| Per entry | The unit is bytes, so a long message and many attributes cost more (inference from the GB unit) | pricing |
| Overhead | No runtime overhead figure on the pages read; do not quote one | none |
| Prices | Not quoted here; see the pricing page | pricing |

## Verify (R6)
No logs-specific API probe is verified in this module. Use the UI and the outcome probe in the quota module.
1. Marker: emit one `info` line with a marker attribute from a real request or job path, then search Explore > Logs (product/logs, "Viewing and Searching Logs"). Expect the marker as a searchable attribute and a trace link when the request was traced.
2. Hook: emit one entry at a level the hook drops and one it keeps. Only the kept entry appears in Explore > Logs.
3. Threshold to event: emit one ERROR record through the logging integration. It appears as an issue only if `event_level` or `minimumEventLevel` allows it; check Issues for the marker.
4. Volume: after a threshold or hook change, the 30-day outcome probe in the quota module, filtered to the logs category as the response names it, should show accepted logs volume falling.
Remove the trigger: delete the marker lines. No configuration needs reverting.

## Sources
- https://docs.sentry.io/product/logs/
- https://docs.sentry.io/platforms/javascript/logs/
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
- https://docs.sentry.io/platforms/python/logs/
- https://docs.sentry.io/platforms/python/integrations/logging/
- https://docs.sentry.io/platforms/python/integrations/loguru/
- https://docs.sentry.io/platforms/java/logs/
- https://docs.sentry.io/platforms/java/guides/logback/
- https://docs.sentry.io/platforms/dotnet/logs/
- https://docs.sentry.io/platforms/apple/logs/ (headings only)
- https://docs.sentry.io/platforms/android/logs/ (headings only)
- https://docs.sentry.io/pricing/
- https://docs.sentry.io/pricing/quotas/
- https://docs.sentry.io/pricing/quotas/manage-logs-quota/
- https://docs.sentry.io/pricing/quotas/spike-protection/

## Identifiers
```identifiers
enableLogs | https://docs.sentry.io/platforms/javascript/logs/
beforeSendLog | https://docs.sentry.io/platforms/javascript/logs/
consoleLoggingIntegration | https://docs.sentry.io/platforms/javascript/logs/
levels | https://docs.sentry.io/platforms/javascript/logs/
Sentry.init | https://docs.sentry.io/platforms/javascript/logs/
Sentry.logger | https://docs.sentry.io/platforms/javascript/logs/
Sentry.logger.fmt | https://docs.sentry.io/platforms/javascript/logs/
Sentry.setAttribute | https://docs.sentry.io/platforms/javascript/logs/
order_id | https://docs.sentry.io/platforms/javascript/logs/
user_id | https://docs.sentry.io/platforms/javascript/logs/
Sentry.metrics | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
sentry_sdk.init | https://docs.sentry.io/platforms/python/logs/
before_send_log | https://docs.sentry.io/platforms/python/logs/
severity_text | https://docs.sentry.io/platforms/python/logs/
capture_sentry_logs | https://docs.sentry.io/platforms/python/integrations/logging/
LoggingIntegration | https://docs.sentry.io/platforms/python/integrations/logging/
enable_logs | https://docs.sentry.io/platforms/python/integrations/logging/
sentry_sdk.logger | https://docs.sentry.io/platforms/python/integrations/logging/
sentry_logs_level | https://docs.sentry.io/platforms/python/integrations/logging/
event_level | https://docs.sentry.io/platforms/python/integrations/logging/
level | https://docs.sentry.io/platforms/python/integrations/logging/
ignore_logger | https://docs.sentry.io/platforms/python/integrations/logging/
ignore_logger_for_sentry_logs | https://docs.sentry.io/platforms/python/integrations/logging/
force=True | https://docs.sentry.io/platforms/python/integrations/logging/
LoguruIntegration | https://docs.sentry.io/platforms/python/integrations/loguru/
logs.enabled | https://docs.sentry.io/platforms/java/logs/
getLogs().beforeSend | https://docs.sentry.io/platforms/java/logs/
beforeSend | https://docs.sentry.io/platforms/java/logs/
minimumEventLevel | https://docs.sentry.io/platforms/java/guides/logback/
minimumBreadcrumbLevel | https://docs.sentry.io/platforms/java/guides/logback/
minimumLevel | https://docs.sentry.io/platforms/java/guides/logback/
SentryAppender | https://docs.sentry.io/platforms/java/guides/logback/
EnableLogs | https://docs.sentry.io/platforms/dotnet/logs/
SetBeforeSendLog | https://docs.sentry.io/platforms/dotnet/logs/
SentryLog | https://docs.sentry.io/platforms/dotnet/logs/
SentrySdk.Logger | https://docs.sentry.io/platforms/dotnet/logs/
SentrySdk.Init | https://docs.sentry.io/platforms/dotnet/logs/
```

## Unconfirmed
- `winston`: a research note lists it as a JS logging integration; not found on the JS logs page read on 2026-10-20.
- Minimum SDK versions for logs in Python, Java, Apple and .NET: the research notes give numbers, but none appear on the pages read, so none are stated here.
- Apple and Android setup routes and the "Missing Logs for Crashes" troubleshooting section: listed on the pages but not read on 2026-10-20.
