# Fix-safety protocol (implementer)

1. **Clean tree first.** If git is dirty, stop and ask: commit/stash, or work on a new branch `sentry-plugin/<run-id>`. Never
   mix the user's uncommitted work with ours.
2. **Findings first.** Edit only for findings with status `approved`. Nothing is applied from chat text.
3. **`kind` is law.** `manual` and `org-write` are never applied by the implementer. Org writes run later through the org flow,
   one exact call at a time.
4. **Touch only `files`.** Plus lockfiles for approved dependency changes. Anything else needs a new finding.
5. **Order:** P0 secrets/privacy, then P1 correctness, then P2 adds, then P3. A fix never lands on code an earlier fix is about
   to rewrite. SDK major upgrades are separate, last, and `requires: [deploy]`.
6. **One commit per unit x product group**, message lists the finding ids. Each commit is independently revertible. No push,
   no PR, no deploy unless the user asks.
7. **Idempotent.** If the code already satisfies a finding, mark it applied without editing. Re-runs never duplicate config.
8. **Look it up, then write.** Every option name you write must appear on a docs page you fetched in this session, or in
   `references/` for the platform. After editing an init site, the stale-API hook may reply: believe it.
9. **Secrets:** tokens only in CI secrets, the environment, or gitignored files. DSN from an environment variable named per
   the platform convention. Never print a token; the engine masks.
10. **Never weaken a check** to make a verification row pass.
11. **Temporary triggers** (a route or script that throws a marked error) are registered the moment they are created
    (`sentry-ctx run trigger <path>`) and removed before the run can finish (delete the file, then `sentry-ctx run trigger <path> --trigger-action remove`).
12. **Build after each group** with the project's own commands (R0). Record `ran`/`saw` on the finding. If R0 fails, fix or
    revert that group before going on.
