# Maintainer notes (plugin-sentry)

Claude Code plugin `sentry` (marketplace `plugin-sentry`). Python 3.9+ standard library only; no runtime dependencies.

## Layout
- `bin/sentry-ctx` -> `engine/` : the deterministic engine (detection, steering, findings ledger, org probes, verification, hooks). Skills and agents call it; they never re-derive what it computes.
- `skills/*/SKILL.md` : thin shells; the instructions live in `references/forge/flows/*.md` and are injected with `` !`sentry-ctx flow <name>` ``.
- `agents/` : `auditor` (read-only), `implementer`, `verifier`. Models are Haiku at `effort: xhigh` on purpose.
- `references/forge/{products,platforms}` : the rubrics. Every Sentry option name in them is declared with the official page that contains it. `references/upstream/` is vendored from getsentry/sentry-for-ai (MIT, see NOTICE); never hand-edit it, run `scripts/sync-upstream.sh`.
- `data/` : detection tables, check catalog (`checks.tsv`), stale-API tables, CLI port map (`cli-map.json`).
- `evals/fixtures` + `evals/expected` : synthetic repos and the recorded engine output / seeded-defect expectations.

## Rules for changes
1. Official Sentry documentation wins. A new Sentry fact needs a docs URL; a new option name goes in the module's `## Identifiers` block (the gate fetches the page and looks for the name) or under `## Unconfirmed`.
2. Run `scripts/check.sh` before every commit (`--offline` skips the docs-backed stages). Run it with `PYTHON=/usr/bin/python3` too: 3.9 is the floor.
3. A behavior change to detection means re-recording the affected `evals/expected/*.detect.json` with `python3 scripts/fixtures.py record <name>` after you have read the diff and judged it right.
4. Bump the version in `.claude-plugin/plugin.json` **and** `.claude-plugin/marketplace.json` together with any shipped change (the manifest, skills, agents, hooks, engine, references, data).
5. Never commit a token, a DSN key from a real project, a personal path or an email. Commit under the GitHub noreply identity.
6. Live tests create only resources named `sentry-plugin-test-*` and every marker event is sent with `--no-environ`.
7. `sentry issue explain|plan` (Seer) spend money: nothing in this repo may run them unprompted.
