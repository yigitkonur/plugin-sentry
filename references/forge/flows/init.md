# Flow: init (units where Sentry is absent)

Init is an audit against an empty baseline. It ends in the same findings ledger and the same implementer.
Precondition: `sentry-ctx flow preamble` is done and `sentry-ctx steer --write` produced `.sentry-plugin/plan.json`.

1. **Skip what must not be initialized.** `library` units are already `n/a: library`. Tell the user once, in one line.
2. **Choose the install route per unit.** Look at `detect` (`wizard`, `docs_platform`, `framework`) and ask (AskUserQuestion, one
   question per distinct route decision, not per unit if they share one):
   - **Manual from the live docs (default when unsure):** the auditor reads the platform module and the current docs page and
     proposes the changes as `add` findings you can review before anything is written. Nothing leaves the machine.
   - **`sentry init` preview:** `sentry init <org>/<project> . --dry-run --yes --features <list> --no-tui` (a hosted wizard that
     uploads file excerpts to a Sentry service; say so, and ask). It changes nothing in dry-run. A real run edits files; the output is
     then audited like any other first-party code (it has written options the installed SDK rejects).
   - **`@sentry/wizard`:** only for integrations that need it (mobile/desktop). It needs their browser login, so give them the exact
     line to run themselves, prefixed with `!`: `! npx @sentry/wizard@latest -i <integration> --disable-telemetry`.
   Wizard routes require: git clean (or a new branch), `node`/`npx` for the wizard, a greenfield unit. Never `--force-install`.
3. **Provision the project** (needs `org_access: read-write`, a login with project:write): this is an `org-write` finding the user
   approves first. Name: the unit's directory name, lowercase with hyphens (show it as the default; a human can change it).
   Platform id: `<language>-<framework>` as Sentry names them (`javascript-nextjs`, `python-fastapi`, `go-gin`, `apple-macos`,
   `ruby-rails`); an unknown id fails the `--dry-run` with "Invalid platform" and creates nothing, so fall back to the language id
   (`node`, `javascript`, `python`, `go`, `apple`, `java`) and say so.
   `sentry project create <org>/<name>:<platform> --dry-run`, show it, then run it, then
   `sentry dsn list <org>/<name> --json`. The DSN goes into an environment variable named per the platform's convention, never a
   literal. With no org access: ask the user for a DSN and use the same variable.
4. **Dispatch auditors in baseline mode** (same dispatch as `sentry-ctx flow audit`, `Mode: baseline`). They create `add` findings:
   - base set, pre-selected: core (init, DSN from env, environment, release), errors, releases (+ release plumbing in CI),
     privacy options from the policy, debug-artifacts upload plan, tracing at the policy's rate;
   - extras, only proposed with the evidence that makes them fit: logs, profiling, replay, crons, uptime, feedback, ai, flags,
     Spotlight. Never over-instrument for a first error.
5. **Barrier, report, approval, hand-off:** steps 3-6 of `sentry-ctx flow audit`.
6. **If an accelerator ran,** treat the unit as present and run the audit flow on its output before approving anything.
