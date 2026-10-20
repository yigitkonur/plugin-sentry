# Flow: apply (implement approved findings, then prove them)

Orchestrator in the main thread. Read `sentry-ctx ref forge/fix-safety` if you have not this session.

1. **Preconditions.** `sentry-ctx run status` must show phase `approved` or later. `sentry-ctx finding list --status approved`
   must be non-empty; if it is empty, say so and stop. `kind: manual` and `kind: org-write` findings are not implemented here.
2. **Git.** `sentry-ctx doctor --no-auth` shows whether the tree is clean. If dirty, ask: commit or stash first, or continue on a new
   branch. Then `git switch -c sentry-plugin/<run-id>` (run-id from `sentry-ctx run status`). Not a git repo: say so, there is no
   undo, and ask before continuing. `sentry-ctx run phase implementing`.
3. **Implement, one group at a time.** Group approved fix/add/remove findings by unit x product. The `core` group goes first (install and init: other groups edit init options that
   must already exist), then P0, P1, P2, P3 (SDK major upgrades last). For each group run the Agent tool with `subagent_type: "sentry:implementer"` and this prompt:
   ```
   Run id: <id>   Unit: <id>   Product group: <product>
   Findings to apply (approved): <F-ids>
   Policy digest: <...>
   Read first: sentry-ctx ref forge/fix-safety, sentry-ctx ref forge/ground-rules, the modules in plan.json for this unit.
   Report: commit hash, per finding applied/skipped/blocked with the R0 result (ran/saw).
   ```
   Groups run sequentially: they edit the same tree. If a group's R0 fails and the implementer cannot fix it in two attempts, revert that
   group with `git revert --no-edit <hash>` and mark its findings `blocked` with the reason.
4. **Org writes.** For approved `org-write` findings follow `sentry-ctx flow org` (one exact call at a time, each already approved).
   If an approved finding needs source maps or debug files uploaded to prove it (R4), the user's approval of that finding covers the upload: record it
   once with `sentry-ctx run approve-write --cli "sourcemap upload" --finding <id>` (a permission prompt shows the command) (or `"debug-files upload"`) before the verifier runs.
5. **Prove it.** `sentry-ctx run phase verifying`, then follow `sentry-ctx flow verify` for the findings whose `verify.rung` is R2 or
   higher. R0/R1 results are already on the findings.
6. **Finish.** `sentry-ctx ledger` must pass (no pending cells, no applied-but-unverified findings, no leftover triggers); findings that
   could not be proven are `unverified` with the reason, or `waived` with the user's reason. `sentry-ctx run phase done`.
7. **Clean up (ask).** `sentry-ctx clean --dry-run` lists what would be removed (artifacts, registered temporary triggers, the
   .gitignore line if we added it). Ask: delete everything / keep only policy.md / keep all (reports). Then
   `sentry-ctx clean --yes --keep policy` (or `--keep all`, or no `--keep`). Report: findings per final status, commits, the highest
   verification rung per finding, and everything UNVERIFIED with how to reproduce it.
