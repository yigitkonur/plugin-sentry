# Flow: verify (prove applied findings with a live event)

Orchestrator in the main thread. Read `sentry-ctx ref forge/verification-ladder` if you have not this session.

1. **What to prove.** `sentry-ctx finding list --status applied` (and `--status unverified` to retry). Each finding's `verify.rung` is its
   target. R0/R1 may already be recorded by the implementer. Anything with a target of R2 or higher goes to the verifier.
2. **Which org and project.** The events must go to a project the user owns. From the policy and `sentry-ctx doctor`, pick the org;
   the project comes from the unit's DSN source (the project the DSN belongs to) or a project created in the init flow. If a project
   was never created or no DSN exists, the finding stays `unverified` ("no destination for events"); say so.
3. **Dispatch** the Agent tool, `subagent_type: "sentry:verifier"`, one verifier per unit (units run one after the other: they run
   the app and edit a trigger file). Prompt:
   ```
   Run id: <id>   Org: <org>   Project: <project>   Unit: <id> (root <root>)
   Findings to prove: <F-ids with their target rungs>
   Marker events use environment: <non-production value>   Policy digest: <...>
   ```
4. **After it returns:** `sentry-ctx ledger` must show no live triggers (`git status` shows only the intended changes). If a trigger is
   still registered, remove it yourself: delete the file, then `sentry-ctx run trigger <path> --trigger-action remove`.
5. **Verification never edits approved code.** If a proof fails because of the change itself (a duplicate event, a missing frame, a leaked field),
   set the finding `blocked --reason "<what was observed>"` and say what a fix would be as a new finding; do not patch it here. Run the app on a free
   port you pick with the OS (a failed bind sends an error event to the project); markers go to a route that is not health-check shaped.
   R4 and R5 are run against the production-like build and the artifacts of that exact release.
6. **Report per finding:** the highest rung reached, the evidence (`ran`/`saw`), and for every rung not reached the reason and the
   exact reproduction steps. Never write "check your dashboard".
