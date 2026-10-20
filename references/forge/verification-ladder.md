# Verification ladder: claim only the rung you reached

| Rung | Proves | How | Needs |
|---|---|---|---|
| R0 static | the change builds / type-checks / lints | the project's own commands (read them from scripts, Makefile, Gradle, Xcode) | - |
| R1 boot | the app starts with the new init and reports no init error | run the app or its test target; SDK `debug` output if needed | a runnable app |
| R2 emit | a marked event leaves the real code path | a temporary trigger inside the real app (never an isolated script: it bypasses the init being verified) | - |
| R3 arrive | the event reached Sentry with the right `release`, `environment`, tags | `sentry-ctx verify wait --marker M --org O --project P` (polls the CLI) | CLI login |
| R4 usable | the stack trace is readable: at least one `in_app` frame from your own code with a `context_line`, a source file name (not a bundle chunk) and no `symbolicator_status` problem. A trace made only of framework or `node_modules` frames proves nothing: the marker must be thrown from a named function in your own file | `sentry event view <org>/<project>/<id> --json > f.json`, then read frames with `jq`; needs a production-like build with artifacts uploaded for that exact release | R3 + upload |
| R5 private | the arrived payload honors the policy: no IP, cookies, auth headers, emails, tokens, `/Users/<name>` paths, no `context.environ`, no unexpected `user.geo` | `sentry-ctx verify scan <event.json>`. A home path inside stack-frame file names is only a warning (it is what a run on this machine looks like); anywhere else it is a violation. `user.geo` is inferred from the connecting IP at ingest and survives "prevent storing of IP addresses"; only an Advanced Data Scrubbing rule on `$user.geo.**` removes it: under a strict or standard policy that is an org-write finding on the project, proposed by `org probe scrubbing` (wait about two minutes after applying it before the marker) | R3 |
| R6 product | cron check-in seen, uptime check passed, replay present, log linked to a trace, metric listed, alert routes | the product module's "Verify (R6)" section | varies |

Marker events: unique per run (`plugin_marker:<run-id>-<n>`), sent from the app, `environment` set to a non-production value
unless the user says otherwise, never resolved or archived by the plugin. When a marker must come from the CLI use
`sentry event send ... --no-environ` (see `sentry-ctx cli-map --intent marker_event`).

Note on `user.geo`: Sentry infers country/city from the connecting IP at ingest even when `user.ip_address` is null. If the
policy forbids location data, "prevent storing of IP addresses" is not enough (live: geo stayed). The server-side scrubbing page's control is an Advanced Data Scrubbing
rule `[Remove] [Anything] from [$user.geo.**]` on the project (`org probe scrubbing` proposes both settings as one org write). Project config reaches Relay in about
two minutes (live: a marker 16 s after the change still had geo, one after 2 min had none): send the marker after that.

Never end with "check your dashboard". The report lists, per finding, the highest rung reached and the evidence. A rung that
could not be reached is **UNVERIFIED** with the reason and the exact steps to reproduce.
