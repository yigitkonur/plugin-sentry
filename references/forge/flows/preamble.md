# Flow: preamble (shared by audit and init)

You are the orchestrator in the main thread. You must stay here: you need `AskUserQuestion`, and subagents cannot ask the user.
`sentry-ctx` finds the project root itself (CLAUDE_PROJECT_DIR or the git root); run it from anywhere in the repo.
Read `sentry-ctx ref forge/ground-rules` once if you have not this session.

**No human to ask?** Headless means `SENTRY_PLUGIN_POLICY_ANSWERS` is set or `AskUserQuestion` is not in your tool list (`-p`, evals, CI).
The policy then comes only from `sentry-ctx policy from-env`; if the answers file is absent, stop at the policy step and report it as missing (never
write a policy from defaults). Every other question takes its recommended default, and you say so in the output. Every approval gate is
"Report only": never approve findings, org writes or cleanup on your own, unless the prompt that started the session names exactly what to approve.
The report is the result.

1. **Tools and login.** Run `sentry-ctx doctor`. Show the user the CLI line, the login/scopes line and the advice lines.
   - No CLI or no login: say plainly that every org-side check will be reported **UNVERIFIED** (not skipped, not clean), print the
     exact command for them to run (`! sentry auth login --read-only` for audits), and continue repo-only unless they stop you.
   - Never install software and never ask for a token.
2. **Existing run.** Run `sentry-ctx run status`. If a run is active, ask (AskUserQuestion): continue it, restart it, or discard it.
   Continue = skip to the phase it is in. Restart/discard = `sentry-ctx clean` (a dry run) first, show the list, ask what to keep (policy only / everything / nothing), then
   `sentry-ctx clean --yes [--keep policy|all]`.
3. **Detect and confirm.** Run `sentry-ctx detect`. Summarize as a table: unit, root, ecosystem, framework (+ version), role, Sentry
   status, installed SDK + resolved version, init sites, DSN source, release/CI wiring, tracked token hits. Call out:
   - `library` units: "do not init Sentry here" (init belongs to the application);
   - `partial` units (declared but not initialized, or initialized but not declared);
   - `legacy` packages (raven, sentry-expo, @sentry/tracing, CocoaPods Sentry, ...);
   - `secrets.tracked_token_hits` > 0 (a P0 candidate; do not print values);
   - `ci.sentry_refs` using `sentry-cli` 3.x (port candidate) or a token on the command line.
   Ask one AskUserQuestion: "Is this what the repo is?" (Yes / A unit is wrong or missing: describe). If wrong, fix the cause
   (usually a path or an unusual layout) or record the correction in the policy notes; do not paper over it.
4. **Policy.** Follow `sentry-ctx flow policy` (it always asks).
5. **Start the run.** Choose the flow: units with Sentry present/partial/legacy -> audit; units with Sentry absent -> init; a repo
   can have both in one run. `sentry-ctx run start --flow audit` (or `init` if every unit is absent).
6. **Artifacts and git.** `.sentry-plugin/` now exists (policy and run state). Ask (AskUserQuestion): "Add `.sentry-plugin/` to
   .gitignore?" (Recommended: yes). Then `sentry-ctx run gitignore add` or `sentry-ctx run gitignore decline`. (If the user named units or ids when starting, limit the run to those.) If they decline, warn
   that the folder will show up in `git status`.
7. **Steer.** Run `sentry-ctx steer --write` (add `--org-access read-only|read-write|none` from the policy). Show the applicability
   table per unit: each product is `applicable` (with the evidence), `n/a` (with the reason), or `unknown` (a question or an
   UNVERIFIED row). The user may add or remove products; apply their changes through the policy (`products.include/exclude`) and
   re-run steer. `n/a` and `unverified` are different states; never merge them.
