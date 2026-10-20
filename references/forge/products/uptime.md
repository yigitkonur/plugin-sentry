# Uptime monitoring (product id: uptime)

## Fit
Propose a monitor when the repo shows a public production host that answers anonymously:
- The host is in deploy or hosting config, the README, the deploy section of `AGENTS.md` or `CLAUDE.md`, or an env var whose name ends in URL, SITE_URL or BASE_URL. Take the host from there; never guess it.
- The repo serves a public API or a separately deployed service on its own host. The docs say one monitor per public service, not per route.
- The repo already sends Sentry errors. Automatic detection builds a monitor from the most frequent hostname in error data, so a monitor may already exist for that host. Check before proposing a second one.
- Applicability rule: the `uptime` row of `data/signals.tsv` (rule `url&notlib|policy:uptime`). When it finds no public URL, ask the user for one; do not propose a monitor.

Not worth proposing:
- No public HTTP URL: libraries, CLIs, workers with no HTTP endpoint.
- Only auth-protected URLs, or URLs that redirect to a login page. The default criterion is a 2xx final response, so a 401, a 403 or a login page fails the check.
- Only `localhost`, a preview deployment, or a host you guessed.
- A host that is not live yet. An issue opens after three consecutive failed checks, so the monitor would open a downtime issue right away.

## Properly configured
Uptime is configured on the server, not in code. The pages fetched describe no SDK setup step; the backend SDK matters only when Allow Sampling is on. Right values:

| Setting | Right | Source |
|---|---|---|
| URL | Public production host plus a cheap route that answers anonymously with 2xx (a health route); the site root suits a site | product page, Request |
| Method | GET for a health route. Body is available only for POST, PUT and PATCH | Request |
| Headers | No API tokens or personal data (the docs warn). Sentry adds `User-Agent` and `Sentry-Trace` itself | Request |
| Interval | 1, 5, 10, 20, 30 minutes or 1 hour | Request |
| Timeout | Maximum wait before a check counts as failed, up to 30 seconds. Read the configured value (see Common mistakes) | Request |
| Failure Tolerance | 3 consecutive failures by default before an issue is created | Thresholds |
| Recovery Tolerance | 1 consecutive success by default to resolve the issue | Thresholds |
| Redirects | Followed; the final destination must return 2xx | Uptime Check Criteria |
| Failure causes | A timeout, a DNS resolution failure or a non-2xx response each count as a failed check | Uptime Check Criteria |
| Allow Sampling | Off unless the backend SDK should decide the sampling of the check's trace. It defers the sampling decision to your SDK so the check can join distributed tracing | Request |
| Verification | Assertions on status, headers or JSON body are Early Adopter only. The default check is 2xx only | Verification |

## Checks
| check id | read | passes when |
|---|---|---|
| uptime.fit | (1) Production host: the sources listed under Fit. (2) `sentry api -X GET "/organizations/<org>/detectors/?project=<project>"`: keep the uptime-type detector, then its workflows from `sentry api -X GET "/organizations/<org>/workflows/?project=<project>"` (route names are Unconfirmed). (3) Sentry UI, Alerts: rules that match outage or downtime issues, and their actions (Notifications section of the docs) | Uptime monitor exists with an alert: a monitor whose URL host equals the production host from (1), not `localhost`, a preview host or a guessed host, and an alert rule matches outage or downtime issues and has at least one action. If (1) found no public URL, record "ask the user", not a failure |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Downtime issue while the app works in a browser | The check gets a 401, a 403, a login redirect or a non-2xx final page; the checker sends no credentials | Monitor an anonymous URL that returns 2xx | Uptime Check Criteria |
| Checks fail while the site answers in a browser | A WAF or bot protection blocks the `SentryUptimeBot/1.0` User-Agent | Allow that User-Agent (IP ranges: see Unconfirmed) | troubleshooting, User Agent |
| A monitor nobody created keeps checking every minute | Automatic detection built it from the most frequent error hostname and checks the root path with GET | Delete it on the Monitors page; it is not re-created. Blocking the User-Agent does not disable the monitor | automatic-detection; troubleshooting, Stop Unwanted Uptime Checks |
| Timeout reads as 10 s in one place and up to 30 s in another | The Request section makes the timeout configurable up to 30 s; the Uptime Check Criteria section says each request has a 10 s timeout threshold. The two pages disagree | Read the monitor's configured value and report it; do not state a default | Request; Uptime Check Criteria |
| An issue opens after one blip | Failure Tolerance set to 1 | Restore the default of 3 unless the URL is known to be flaky; tuning is for reducing noise | Thresholds |
| Secret leaks through the monitor | A token placed in Headers or Body | Use an anonymous URL; keep secrets out of Headers (the docs warn about this) | Request |
| Downtime happens and nobody is told | No alert matches outage or downtime issues, or the alert has no action | Add an alert with actions for those issues; the docs say to configure it | Notifications |

## Volume, cost and overhead
| Item | Fact | Source |
|---|---|---|
| Billing | Per monitor. The included count and the pay-as-you-go rule are not on any page fetched (see Unconfirmed) | none fetched |
| `uptime.request` span | Free; does not count against the span quota. Always created, even with sampling disabled | Uptime Request Spans |
| Check traffic | One request per interval from Sentry's checker regions: a 1-minute monitor sends 1,440 requests a day. Automatic monitors run once a minute | Request; automatic-detection |
| Automatic onboarding | Hourly requests for three days; a host that fails three times is dropped and re-evaluated after seven days | automatic-detection |
| App overhead | The pages fetched describe no SDK setup. The app-side cost is the check requests, plus the traces the backend SDK samples when Allow Sampling is on | Request |

## Verify (R6)
1. Anonymous check from a shell, sending the checker's User-Agent:
```bash
curl -sL -D - -o /dev/null -A SentryUptimeBot/1.0 "<production URL>"
```
The last `HTTP/` status line must be 2xx. A redirect chain must end in 2xx.
2. Sentry side: in trace search, filter spans to the `uptime.request` name in the production project. One root span appears per check. None yet means the first check has not run.
3. Alerts: open the rule in the Sentry UI and confirm it matches outage or downtime issues and lists an action. The troubleshooting page has a section "Verify That Alerts Match Downtime Issues" that was not read; read it before writing this check.
4. Removing the trigger: delete the monitor on the Monitors page. An automatically detected monitor is not re-created after deletion.

## Sources
- https://docs.sentry.io/product/monitors-and-alerts/monitors/uptime-monitoring/
- https://docs.sentry.io/product/monitors-and-alerts/monitors/uptime-monitoring/automatic-detection/
- https://docs.sentry.io/product/monitors-and-alerts/monitors/uptime-monitoring/troubleshooting/

## Identifiers
```identifiers
User-Agent | https://docs.sentry.io/product/monitors-and-alerts/monitors/uptime-monitoring/
Sentry-Trace | https://docs.sentry.io/product/monitors-and-alerts/monitors/uptime-monitoring/
uptime.request | https://docs.sentry.io/product/monitors-and-alerts/monitors/uptime-monitoring/
SentryUptimeBot/1.0 | https://docs.sentry.io/product/monitors-and-alerts/monitors/uptime-monitoring/troubleshooting/
```

## Unconfirmed
- `uptime_domain_failure`: uptime detector type name from research/07; no fetched official page has it (2026-10-20). Do not filter on it until verified.
- `create_uptime_monitor`, `find_uptime_monitors`: MCP tool names from the vendored upstream note; no fetched official page has them (2026-10-20). Check the live tool list before use.
- `intervalSeconds`, `timeoutMs`, `downtimeThreshold`: payload field names from the vendored upstream note; no fetched official page has them (2026-10-20). Do not send them as field names.
- `/organizations/<org>/detectors/` and `/workflows/` list routes used in the uptime.fit read: research/07 only; not on any fetched official page (2026-10-20). Use them only as an approved `sentry api` call.
- `monitor billing`: included count per plan and the pay-as-you-go rule. The `pricing/monitors` path returned Page Not Found on 2026-10-20, though the pricing index lists Monitors Pricing. Verify on that page before quoting a number.
- `default alert`: research says new projects get an alert for high-priority issues and that uptime issues open as high priority; no fetched page says so (2026-10-20).
- `timeout default`: the upstream note gives 5000 ms; no fetched page states a default (2026-10-20).
- `checker regions`: the docs say checks rotate across "a variety of geographical locations" and do not list them (2026-10-20).
- `IP allowlisting`: the troubleshooting section "IP Addresses" (under Verify Firewall Configuration) was not read on 2026-10-20. Read it before recommending IP ranges.
- `monitor environment`: the upstream note says to set the production environment name; no fetched page documents an environment field (2026-10-20).
