# Monitors and alerts (product id: alerts)

## Fit
Propose this when the repo shows at least one of these; the org check then confirms or refutes it.

| Repo evidence | Why it matters | Where to look |
|---|---|---|
| Calls to the legacy `/rules/` or `/alert-rules/` routes, or Sentry alerts kept as code | Legacy routes are removed; highest priority | IaC, scripts, CI config (alert.legacy-api) |
| A production scheduled job (cron entry, scheduler config, scheduled CI workflow) that runs a Sentry SDK | Cron monitor candidate; a job that silently stops is invisible without one | job definitions, SDK init in the job entry point |
| A public HTTP service with a health or status route | Uptime monitor candidate; the docs name downtime as a case for an alert | router files, deploy health-check config |
| Production services with a Sentry SDK but no alert config and no notification destination in the repo | Errors become issues, and nothing tells a person | SDK init per service; env names for Slack, PagerDuty or webhooks; CODEOWNERS or on-call files |
| Several production services that would share one channel or one catch-all | Routing shape needs a decision | service list, deploy config |

Not worth proposing:
- No org access. `data/signals.tsv` marks `alerts` as org-level with the note "UNVERIFIED: no org access". Report UNVERIFIED, not n/a; only alert.legacy-api can run from the repo.
- No Sentry SDK in the repo and no scheduled job or public endpoint to watch.
- Only dev, test or staging projects; there is no production traffic to alert on.
- Every production project and monitor already has an alert (alert.coverage passes) and no legacy call exists.

## Properly configured
Alerts and monitors are configured in Sentry, not through SDK options. The repo's part is the job and endpoint side, plus any alerts kept as code.

| Layer | Right | Source |
|---|---|---|
| Default monitors | Issue Stream Monitor and Error Monitor exist on every project and need no setup. They create issues; notifying the team is done by Alerts | monitors "Default Monitors"; alerts "When to Notify the Team" |
| Issue alert | Sources are the production projects; triggers include new issues (and regressions if the team wants them); filters keep only the issues the team must act on; at least one action reaches a destination people read | alerts "Creating Alerts", "Alerts Best Practices" |
| Routing shape | One alert per service or team channel, or one catch-all team channel, chosen on purpose | alerts "Alerts Best Practices" |
| Metric monitor | Dataset is errors, spans, logs, releases or application metrics. Fixed threshold where the good or bad line is known (docs example: crash rate above 1%); percentage change or dynamic anomaly where traffic is seasonal or grows | monitors "Metric Monitor Settings" |
| Cron monitor | One monitor per production scheduled job; schedule, check-in margin, max runtime and failure tolerance match the job's real timing; connected to an alert | monitors "Cron Monitor Settings", "Managing Monitors" |
| Uptime monitor | URL and HTTP request of the public health endpoint; interval, timeout, headers and failure tolerance set on purpose; connected to an alert | monitors "Uptime Monitor Settings"; alerts "When to Notify the Team" |
| Ownership | Every action names a team or channel that is watched. "Let Members Create and Edit Monitors and Alerts" is a deliberate choice (enabled by default). Alerts scoped to all projects are limited to Org Owners and Org Managers | alerts "Creating Alerts"; monitors "Managing Monitors" |
| Personal delivery | User Settings > Notifications tunes personal delivery only; it does not replace an org alert | alerts "Sentry Notifications" |

## Checks
| check id | read | passes when |
|---|---|---|
| alert.legacy-api | Repo: `grep -rn -e "alert-rules" -e "rules/" <repo>` over IaC (`*.tf`, `*.yaml`, `*.json`), scripts and CI config; review each hit by hand (paths, not Sentry calls, can match) | No file calls the legacy `/rules/` or `/alert-rules/` routes. Any alert-management code uses the detector and workflow routes. Time-window values in IaC are read as seconds, not minutes (see Unconfirmed) |
| alert.coverage | Org side, needs `alerts:read` (or `org:read`); without org access, UNVERIFIED. `sentry api -X GET "/organizations/<org>/detectors/?project=<project-id>"` per production project; `sentry api -X GET "/organizations/<org>/workflows/?project=<project-id>"`; `sentry api -X GET "/organizations/<org>/monitors/"` for cron monitors. Compare the scheduled jobs and public endpoints found in the repo with those lists | Every detector and cron monitor on each production project is attached to at least one workflow (no detector with an empty workflow list). Each production project has at least one issue alert whose action goes to an installed integration (docs: available actions depend on installed integrations). Each production scheduled job found in the repo has its own cron monitor. Each public health endpoint found in the repo has an uptime monitor with an alert |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Errors appear as issues; nobody is messaged | No alert sources the production project, or its only action goes nowhere | Add an alert: source the production project, trigger on new issues, action to a watched channel | alerts "Creating Alerts" |
| Alert exists and never fires | Filters narrower than the issues it was meant for | Review filters; keep only the triggers the action needs | alerts "Alerts Best Practices" |
| Alert never reaches anyone | Action's integration is not installed or was removed; actions depend on installed integrations | Confirm each action's integration is installed and the channel still exists | alerts "Creating Alerts" |
| Cron job stops and nobody hears | Monitor exists with no alert connected | Connect an alert with the monitor as a source; check "connected automations" on the monitor | monitors "Managing Monitors" |
| Uptime outage, no page | Uptime monitor has no alert connected | Add an alert triggered on downtime | alerts "When to Notify the Team" |
| Several alerts send the same issue to the same place | Overlapping sources and triggers, often one alert per engineer or per project | Merge into one alert per service or team channel | alerts "Alerts Best Practices" |
| Member cannot create or edit alerts | Org setting "Let Members Create and Edit Monitors and Alerts" is off; all-projects alerts need Owner or Manager | Ask an org Owner or Manager; decide the setting on purpose | alerts "Creating Alerts" |
| Alert scripts or IaC fail after the migration | Calls to legacy `/rules/` or `/alert-rules/` routes; time-window units changed | Move to detector and workflow routes; read windows in seconds | see Unconfirmed |

## Volume, cost and overhead
| Category | Billed as | Note |
|---|---|---|
| Metric monitors | Not billed per monitor (research notes) | Not on a fetched docs page; see Unconfirmed |
| Cron monitors | Per monitor | 1 included each on paid plans, pay-as-you-go beyond (quota module's pricing row); see Unconfirmed |
| Uptime monitors | Per monitor | Same as cron monitors |
| Alerts (detectors, workflows) | No separate billing line on the fetched pages | Configuration only |

- Alerts run server-side; alerting adds no runtime cost to the app. The only runtime code is cron check-ins inside the job.
- Each cron or uptime monitor beyond the included count needs a pay-as-you-go budget. Check it before adding one per job.

## Verify (R6)
Proof is a configuration read plus a result, not "an alert was created".
1. Repo: `grep -rn -e "alert-rules" -e "rules/" <repo>` returns nothing relevant in IaC and scripts.
2. Org, GET only: `sentry api -X GET "/organizations/<org>/detectors/?project=<project-id>"` per production project. Each detector lists its attached workflows; an empty list is the zero-alert case.
3. `sentry api -X GET "/organizations/<org>/workflows/?project=<project-id>"`. Each workflow names its detectors and action types; an action type with no installed integration is a dead route.
4. `sentry api -X GET "/organizations/<org>/monitors/"`. Each cron monitor shows a status; a monitor with no check-in recorded (semantics UNCONFIRMED) is the case an alert must catch.

The field names in these reads were read from the spec in the spike, not from a docs page (see Unconfirmed). Check them against the live JSON once before quoting them. Record each read as C evidence. Creating or changing an alert, detector or workflow is a manual step or an approved call (`references/forge/fix-safety`), never a probe.

## Sources
- https://docs.sentry.io/product/monitors-and-alerts/
- https://docs.sentry.io/product/monitors-and-alerts/alerts/
- https://docs.sentry.io/product/monitors-and-alerts/monitors/

## Identifiers
```identifiers
Let Members Create and Edit Monitors and Alerts | https://docs.sentry.io/product/monitors-and-alerts/alerts/
Issue Stream Monitor | https://docs.sentry.io/product/monitors-and-alerts/monitors/
```

## Unconfirmed
- `workflowIds`: detector field from the spike's reading of the API spec (research notes); no fetched docs page names it on 2026-10-20. Check the live JSON.
- `detectorIds`: workflow field, same status as `workflowIds`.
- `timeWindow`: unit change from minutes to seconds (research notes); no fetched docs page states it on 2026-10-20.
- `metric_issue`: detector type name (research notes); not on a fetched docs page on 2026-10-20.
- Legacy removal dates (brownout 2026-05-14; alert-rules retired 2026-08-17; legacy routes removed 2026-09-24; rule-history 2026-09-29): from research notes. The changelog URL the notes cite did not resolve through `docs page` on 2026-10-20, so the dates are not docs-confirmed.
- Billing: metric monitors not billed per monitor, cron and uptime billed per monitor (research notes). Re-check the pricing page before quoting numbers.
- Metric alerts were migrated automatically at GA on 2026-05-07 (research notes), so a migrated rule and a new one can duplicate. No fetched page documents the migration result.
