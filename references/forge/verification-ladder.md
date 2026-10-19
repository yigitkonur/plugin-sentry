# Verification ladder: claim only the rung you reached

| Rung | Proves | How | Needs |
|---|---|---|---|
| R0 static | the change builds / type-checks / lints | the project's own commands (read them from scripts, Makefile, Gradle, Xcode) | - |
| R1 boot | the app starts with the new init and reports no init error | run the app or its test target; SDK `debug` output if needed | a runnable app |
| R2 emit | a marked event leaves the real code path | a temporary trigger inside the real app (never an isolated script: it bypasses the init being verified) | - |
| R3 arrive | the event reached Sentry with the right `release`, `environment`, tags | `sentry-ctx verify wait --marker M --org O --project P` (polls the CLI) | CLI login |
| R4 usable | the stack trace is readable (source context, not minified, symbolicated) | `sentry event view <org>/<project>/<id> --json`, inspect frames; needs a production-like build with artifacts uploaded | R3 + upload |
| R5 private | the arrived payload honors the policy: no IP, cookies, auth headers, emails, tokens, `/Users/<name>` paths, no `context.environ`, no unexpected `user.geo` | `sentry-ctx verify scan <event.json>` | R3 |
| R6 product | cron check-in seen, uptime check passed, replay present, log linked to a trace, metric listed, alert routes | the product module's "Verify (R6)" section | varies |

Marker events: unique per run (`plugin_marker:<run-id>-<n>`), sent from the app, `environment` set to a non-production value
unless the user says otherwise, never resolved or archived by the plugin. When a marker must come from the CLI use
`sentry event send ... --no-environ` (see `sentry-ctx cli-map --intent marker_event`).

Note on `user.geo`: Sentry infers country/city from the connecting IP at ingest even when `user.ip_address` is null. If the
policy forbids location data, the only control is the server-side "prevent storing of IP addresses" setting (org/project).

Never end with "check your dashboard". The report lists, per finding, the highest rung reached and the evidence. A rung that
could not be reached is **UNVERIFIED** with the reason and the exact steps to reproduce.
