# Flow: audit (units where Sentry is present, partial or legacy)

Precondition: `sentry-ctx flow preamble` is done and `sentry-ctx steer --write` produced `.sentry-plugin/plan.json`.

1. **Phase.** `sentry-ctx run phase auditing`.
2. **Dispatch auditors in parallel**, at most 4 at a time, with the Agent tool, `subagent_type: "sentry:auditor"`. One per
   unit x group, for each group that has at least one `applicable` cell in `plan.json`:
   `foundation` (core, errors, releases, debug-artifacts, mobile-builds, dev-spotlight) - `telemetry` (tracing, profiling, logs,
   metrics, ai, mcp, flags, otlp, cf-observability) - `client` (replay, feedback) - `jobs` (crons, uptime) - `privacy` (always).
   The org half is not an auditor: when the policy allows org access and the CLI is logged in, run `sentry-ctx flow org` steps 2-5 yourself
   (`sentry-ctx org probe all --record` fills the four `_org/*` cells deterministically).
   Every prompt carries (fill from `plan.json` and the policy; do not paste file contents):
   ```
   Mode: <baseline for a unit whose Sentry status is absent, audit otherwise>
   Unit: <id>   Root: <root>   Ecosystem/framework: <eco>/<framework> <version>   Role: <role>
   Group: <group>   Products to audit: <the applicable products in this group>
   Read first: sentry-ctx ref forge/ground-rules, then each of these (sentry-ctx ref <name>): <the unit's modules[]>
   Detected Sentry state: <status>; SDK <pkg> <resolved>; init sites <files>; build wiring <ids>
   Policy digest: <preset, ai_io, replay_mask, environments, release_owner, volume, cloudflare.owner (unset = ask, never guess)>
   Org access: <none|read-only|read-write>; CLI: <sentry vX | sentry-cli vX | none>; login: <ok|none>
   Cells you own (coverage): <unit>/<product> for each product above. Every one must end clean, findings, n/a or unverified.
   ```
   Do not summarize the audit rules into the prompt: the agent's own definition carries them.
3. **Barrier and completeness.** When all auditors return, run `sentry-ctx ledger`. For each pending cell re-dispatch once
   (same prompt, only those cells). Cells still pending afterwards: `sentry-ctx coverage set --unit U --product P --state unverified --reason "<why>"`.
   (The Stop hook enforces the same check.)
3b. **Links** (only when `plan.json` has a `links` cell). After the per-unit audits, dispatch one more `sentry:auditor` for the whole repo:
   `Unit: _links   Group: links   Products to audit: links   Read first: sentry-ctx ref forge/ground-rules, sentry-ctx ref products/links`, with the
   `links` section of `.sentry-plugin/detect.json` (edges, cors_allowed_origins, shared_dsns, environment_names) and `sentry-ctx finding list`
   (what the unit auditors already filed, so an edge problem is filed once). It owns the cell `_links/links`, files findings with `--unit _links`,
   and re-runs the barrier above for that cell.
4. **Report.** `sentry-ctx report`. Present: P0 and P1 in full (id, unit/product, one-line what, the evidence, the fix in one line),
   P2/P3 as counts per product, the coverage table with its three different states, org writes awaiting approval, and anything
   UNVERIFIED with the reason. Never blend clean with n/a or unverified.
5. **Approval gate** (AskUserQuestion; ask, do not assume):
   - "Which findings should I apply?" - All P0+P1 fixes / Also the adds your policy allows / Let me pick by product / Report only.
   - Org writes get their own question listing each exact call (`METHOD /path` and its effect). Only after a yes run
     `sentry-ctx run approve-write --method <M> <exact path> --finding <id>` (CLI form: `--cli "<full command>"`) for that call. That command raises a
     permission prompt showing the exact line: it is the user's consent, so run it only after their yes, and never to approve something they did not ask for.
     An approval is bound to this run, this session and the finding's exact call (method, path, body).
   Then `sentry-ctx finding approve --ids F-001,F-004` (or `--severity P0,P1 --kinds fix,add,remove`; `manual` and `org-write` findings are never bulk-approved: org writes are approved per call in `sentry-ctx flow org` step 7), and `sentry-ctx run phase approved`.
6. **Hand-off.** If they want it now, run `sentry-ctx flow apply` and follow it. Otherwise tell them `/sentry:apply` continues later
   (the findings stay on disk).
