# Flow: apply (implement approved findings, then prove them)

Orchestrator in the main thread. Read `sentry-ctx ref forge/fix-safety` if you have not this session.

0. If the user named finding ids, apply only those; otherwise every approved one.
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
   Groups run sequentially: they edit the same tree. The implementer gets one fix attempt after a failed R0; if it still fails it discards only its
   own group's files (never `git checkout -- .`) and reports `blocked`; you then mark those findings `blocked` with the reason. A group that
   was already committed and later proves wrong is undone with `git revert --no-edit <hash>`.
4. **Org writes.** For each approved `org-write` finding follow `sentry-ctx flow org` step 7: it asks per call (the exact `METHOD /path`, body and effect, or the
   CLI line), then records the approval and runs `sentry-ctx org apply <id> --run`. Never call `sentry project create` or `sentry api -X ...` by hand.
   If proving a finding (R4) needs source maps or debug files uploaded, ask once: "Upload source maps for release <v> to <org>/<project>?" and only after
   a yes record `sentry-ctx run approve-write --cli "sourcemap upload" --finding <id>` (or `"debug-files upload"`); a permission prompt shows the command.
   That two-word approval covers every upload of that kind in this run.
5. **Prove it.** `sentry-ctx run phase verifying`, then follow `sentry-ctx flow verify` for the findings whose `verify.rung` is R2 or
   higher. For findings whose `verify.rung` is R0 or R1, the implementer's R0 result is the proof: `sentry-ctx finding set-status <id> verified --ran "<its R0 command>" --saw "<its result>"`
   (or `unverified --reason "<why R0 did not run>"`).
6. **Finish.** `sentry-ctx ledger` must pass (no pending cells, no applied-but-unverified findings, no leftover triggers); findings that
   could not be proven are `unverified` with the reason, and `waived` (from `unverified`) only with the user's reason. `sentry-ctx run phase done`.
7. **Clean up (ask).** `sentry-ctx clean` (no `--yes`: a dry run) lists what would be removed (artifacts, registered temporary triggers, the
   .gitignore line if we added it). Ask: delete everything / keep only policy.md / keep all (reports). Then
   `sentry-ctx clean --yes --keep policy` (or `--keep all`, or no `--keep`). Report: findings per final status, commits, the highest
   verification rung per finding, and everything UNVERIFIED with how to reproduce it.
