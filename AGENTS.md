# Maintainer notes (plugin-sentry)

Claude Code plugin `sentry` (marketplace `plugin-sentry`). Python 3.9+ standard library only; no runtime dependencies.

## Layout
- `bin/sentry-ctx` -> `engine/` : the deterministic engine (detection, steering, findings ledger, org probes, verification, hooks). Skills and agents call it; they never re-derive what it computes.
- `skills/*/SKILL.md` : thin shells; the instructions live in `references/forge/flows/*.md` and are injected with `` !`sentry-ctx flow <name>` ``.
- `agents/` : `auditor` (read-only), `implementer`, `verifier`. Models are Haiku at `effort: xhigh` on purpose.
- `references/forge/{products,platforms}` : the rubrics. Every Sentry option name in them is declared with the official page that contains it. `references/upstream/` is vendored from getsentry/sentry-for-ai (MIT, see NOTICE); never hand-edit it, run `scripts/sync-upstream.sh`.
- `data/` : detection tables, check catalog (`checks.tsv`), stale-API tables, CLI port map (`cli-map.json`).
- `evals/fixtures` + `evals/expected` : synthetic repos and the recorded engine output / seeded-defect expectations.
- `evals/recordings/events` : scrubbed real Sentry events and what the privacy scan said about each. `scripts/replay-events.py` replays them (and makes each good one worse); make a new one with `scripts/record-event.py` from an event you fetched read-only, and read the printed verdict before committing.

## Rules for changes
1. Official Sentry documentation wins. A new Sentry fact needs a docs URL; a new option name goes in the module's `## Identifiers` block (the gate fetches the page and looks for the name) or under `## Unconfirmed`.
2. Run `scripts/check.sh` before every commit (`--offline` skips the docs-backed stages). Run it with `PYTHON=/usr/bin/python3` too: 3.9 is the floor.
3. `scripts/check-sdk-types.py` compares the JS stale-API rows with the real `@sentry/*` packages. If it fails, the table is wrong or the SDK changed: read the SDK's own types, then fix the row (a row is never kept just to make the check pass).
4. A behavior change to detection means re-recording the affected `evals/expected/*.detect.json` with `python3 scripts/fixtures.py record <name>` after you have read the diff and judged it right.
5. Do not bump the version by hand. After the checks pass on `main`, the `release` job in `.github/workflows/ci.yml` runs `scripts/bump-version.py`: when files inside the plugin changed since its latest tag (README, docs, evals, tests, scripts and CI do not count) it bumps both manifests, makes a `chore(release)` commit, a tag and a GitHub release whose notes are the commit subjects. The level comes from the subjects: `type!:` or a BREAKING CHANGE line is major, `feat:` is minor, anything else is patch. Installed copies update when the version changes, so a shipped change must go through `main`. `python3 scripts/bump-version.py` (no flags) shows the decision; Actions > ci > Run workflow with `dry_run` shows it on the runner.
6. Never commit a token, a DSN key from a real project, a personal path or an email. Commit under the GitHub noreply identity.
7. Live tests create only resources named `sentry-plugin-test-*` and every marker event is sent with `--no-environ`.
8. `sentry issue explain|plan` (Seer) spend money: nothing in this repo may run them unprompted.
