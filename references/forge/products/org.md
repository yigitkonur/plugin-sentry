# Organization, projects, integrations (product id: org)

## Fit
Always read when there is org access: a correct SDK setup still fails if the project has no alert path, a dead key, no uploaded source maps or a scrubber that is off. Not worth proposing: no `sentry` v4 login (every row is UNVERIFIED, never n/a) or no project that can be tied to this repo (project-level rows are UNVERIFIED until the user names the project).

## Properly configured
Seventeen GET-only probe rows (`sentry-ctx org probe`). Each row reads what the API returns for this login and reports clean, findings, UNVERIFIED (with the reason) or n/a (HTTP 404: feature or plan not available).

| Row | Reads | Healthy |
|---|---|---|
| 1 identity | org, project list, `links.regionUrl`, DSN hosts in the code | each project has received an event; DSN region equals the org region |
| 2 keys | project client keys | at least one active key; limits are a decision |
| 3 filters | project inbound filters | localhost on; browser extensions and crawlers on for browser-facing units |
| 4 scrubbing | org and project scrubber settings | scrubbing and default scrubbers on; IP storing off under strict or standard policy |
| 5 spike | project options, sampling mode | spike protection on |
| 6 alerting | detectors and workflows per project | each project's error detector reaches a workflow with an action |
| 7 monitors | cron monitors, uptime detectors | each cron monitor has check-ins; a public URL has an uptime monitor |
| 8 releases | releases, repos | latest release has commits and a deploy |
| 9 artifacts | artifact bundles, debug files | present for the project's platform |
| 10 stacktraces | project flag, three newest events | in-app frames readable |
| 11 ownership | ownership rules, CODEOWNERS sync | rules exist when the team works with owners |
| 12 event-sanity | 7-day event counts | under 5% of events without environment or release |
| 13 usage | 30-day outcomes | no large rate-limited share |
| 14 seer | org Seer and AI settings, GitHub integration | informational; Seer is billed per use and is never started by this plugin |
| 15 replays | replay inventory | informational (masking is an SDK setting) |
| 16 flags | flag-change log | informational |
| 17 integrations | installed integrations | active, not out of date |

Scopes: the default OAuth login carries `project:*`, `org:read`, `event:*`, `alerts:*`, `team:*`, `member:read`; it lacks `org:write`, `org:ci`, `project:releases`, `member:write` (`sentry-ctx doctor` lists what is missing). Organization-level settings therefore stay `manual` findings with the exact UI path.

## Checks
| check id | read | passes when |
|---|---|---|
| org.projects | rows 1 and 17 | one project per deployable unit with a platform that matches; every project has a first event; integrations active |

Other org-side checks live with their products: `core.dsn-region`, `err.noise`, `quota.controls`, `priv.server-scrub`, `alert.coverage`, `cron.coverage`, `uptime.fit`, `rel.commits-deploys`, `rel.sourcemaps`, `rel.debug-files`, `rel.resolve`, `err.ownership`, `core.environment`, `core.release`, `quota.size-billed`, `seer.prereq`, `replay.rates`, `flags.integration`.

## Common mistakes
| Symptom | Cause | Fix |
|---|---|---|
| Probe says UNVERIFIED 403 | The login lacks a scope or the role cannot read it | Name the scope in the report; `sentry auth login` with the broader default scopes, or the UI |
| Every project-level row UNVERIFIED | No project matched the repo | `sentry-ctx org focus --org <o> --project <slug>` |
| Row clean but nothing arrives | Probes read the org, not the app | The verify flow emits a marked event |
| Wrong region assumed | Relative API paths always route through the control silo | Compare the DSN host region with `links.regionUrl` (row 1) |

## Volume, cost and overhead
Probes are reads: no quota is consumed. A full pass makes about 60 GET requests for one project and takes about a minute. Org writes that create billed resources (uptime monitors) say so in the approval prompt.

## Verify (R6)
Re-run the row that produced the finding (`sentry-ctx org probe <row> --record`); the candidate must be gone. For a created monitor, `sentry api -X GET` on the detector list shows it.

## Sources
- https://cli.sentry.dev/exit-codes/
- https://docs.sentry.io/api/

## Identifiers
```identifiers
```

## Unconfirmed
- none
