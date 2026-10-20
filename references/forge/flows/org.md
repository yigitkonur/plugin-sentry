# Flow: org (read the Sentry organization; apply approved org writes)

Runs standalone (`/sentry:org`) or as the org half of audit/init. Probes are GET-only and cost no quota. Orchestrator in the main thread.
Read `sentry-ctx ref forge/ground-rules` and `sentry-ctx ref products/org` once. Never print a token; never run `sentry issue explain|plan`.

1. **Tools and login.** `sentry-ctx doctor`. No `sentry` v4 or no login: say that all 17 org rows will be **UNVERIFIED (no login)**, print
   `! sentry auth login --read-only`, and stop unless the user wants the rows recorded as UNVERIFIED (`org probe all --record` does that).
2. **Org and projects.** If the user passed an org slug and project slugs, use them (`sentry-ctx org focus --org <o> --project <p,...>`). The org is the single logged-in org, else ask (AskUserQuestion; headless: the first one from `doctor`). The
   projects that belong to this repo: matched from DSN literals in the code, or ask for slugs (`sentry project list <org>/ --json`
   shows them). Save: `sentry-ctx org focus --org <slug> --project <a,b>`. An unmatched repo is not a reason to probe every project:
   project-level rows stay UNVERIFIED ("no project identified") until the user names them.
3. **Policy and plan.** If there is no run yet: `sentry-ctx flow policy`, `sentry-ctx run start --flow org`, `sentry-ctx steer --write --org-access <policy value, at least read-only>`.
4. **Probe.** `sentry-ctx org probe all --record` (about a minute). It prints the 17 rows (clean / findings / UNVERIFIED with the reason / n/a),
   writes masked summaries to `.sentry-plugin/evidence/org-NN-*.json`, adds each candidate as an open `_org` finding with the exact
   call it read, and sets the four `_org/*` coverage cells (`org`, `quota`, `alerts`, `seer`). A cell is `clean` only if every
   row of it was read; one UNVERIFIED row makes the cell UNVERIFIED with the reason. Re-run one row later with `org probe <row|id> --record`.
5. **Judge.** Read the findings (`sentry-ctx finding list --unit _org`). The probes are objective, the policy decides relevance: a
   finding that does not apply (a deliberately open key, an unused integration) is `finding set-status <id> skipped --reason "..."`
   or `waived`. Do not delete or edit evidence.
6. **Report.** `sentry-ctx report`. Present the 17 rows as a table first (state + one line), then findings P0..P3, then UNVERIFIED rows
   with the exact fix (login scope, project name). Say which findings are UI-only (`kind: manual`: org settings need `org:write`, which the
   default login does not carry; integrations install through the browser).
7. **Org writes (only `kind: org-write` findings).** Show each exact call (`METHOD /path` + body + effect + cost, e.g. an uptime monitor
   is billed per monitor). AskUserQuestion per call: apply / skip. Headless: approve nothing.
   For each yes, approve in the same form the finding holds (REST: `sentry-ctx run approve-write --method <M> <exact path> --finding <id>`; CLI form: `--cli "<full command>"`; it raises a permission prompt, which is the consent), `sentry-ctx finding approve --ids <id>`,
   `sentry-ctx org apply <id>` (prints the `--dry-run` of the call; read it), then `sentry-ctx org apply <id> --run`.
   The engine refuses the call unless it was approved in this run. Never improvise a different `sentry api` write.
8. **Prove it.** Re-probe the row the finding came from: `sentry-ctx org probe <row> --record`. The candidate must be gone; then
   `sentry-ctx finding set-status <id> verified --rung R3 --ran "<probe command>" --saw "<row state and observation, copied>"`. If the row still shows it,
   the finding stays `applied` and the reason goes in the report.
9. **Finish.** `sentry-ctx ledger` must pass. Only resources named `sentry-plugin-test-*` are ever created or removed by this plugin's own tests; for
   a user's org, every write is the user's decision. When the run is done, clean up as the end of the apply flow does: `sentry-ctx clean` (dry run), ask what to keep, then `sentry-ctx clean --yes [--keep policy|all]`.
