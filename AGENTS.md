# Maintainer notes (plugin-sentry)

Claude Code and Codex plugin `sentry` (marketplace `plugin-sentry`). The Codex side is `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` and `hooks/codex-hooks.json`; the skills, engine and `hooks/run.sh` are shared. Keep the two manifests and the Claude marketplace entry on one version (`scripts/check-codex.py` checks it; the release script writes all three). Python 3.9+ standard library only; no runtime dependencies.

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
5. Never commit a token, a DSN key from a real project, a personal path or an email. Commit under the GitHub noreply identity.
6. Live tests create only resources named `sentry-plugin-test-*` and every marker event is sent with `--no-environ`.
7. Codex has no subagents and no question tool: the Codex addendum lives in `registry.py` (`CODEX_FLOW_NOTE`, appended to every `sentry-ctx flow` output when the host is Codex), not in the flow files. File writes reach hooks as `apply_patch`; `hooks/common.py:written` is the one place that reads both shapes.
8. `sentry issue explain|plan` (Seer) spend money: nothing in this repo may run them unprompted.

<!-- kit:agents:start -->
## Releases, versions and installs (shared by every plugin repo)

- **Never bump a version by hand.** `.github/workflows/release.yml` runs after `ci` is green on `main`. `scripts/kit/release.py` reads the conventional-commit subjects since the last release tag (`feat` is a minor, `fix`/`perf`/unprefixed a patch, `type!:` or a BREAKING CHANGE line a major, a minor while the version is 0.x; docs, ci, chore, test, style, build and refactor release nothing) and counts only commits that touch shipped files. It writes every manifest, the marketplace entries and CHANGELOG.md, commits `chore(release): vX [skip ci]`, tags `vX` and `<plugin>--vX` (several plugins: `<plugin>--vX` only) and publishes the GitHub release. `python3 scripts/kit/release.py` with no flags prints what it would do; Actions > release > Run workflow forces a level or a dry run.
- **One version source: the manifests** (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, the marketplace entry). Never a constant in code; read the manifest at runtime.
- Installed copies update only when the version string changes, so a change users should get must reach `main` as a releasing commit type (`feat`, `fix`, `perf`, or `!`).
- **Install policy:** installed globally and off (`"defaultEnabled": false`), switched on per project with `plugin on <name>`. Never document a project-scope install as the way in.
- `scripts/kit/*`, `scripts/kit.sha256`, `.github/workflows/release.yml`, the `kit:manifests` job in `ci.yml` and the blocks between `kit:` markers in README.md and AGENTS.md are copies from [yigitkonur/plugin-kit](https://github.com/yigitkonur/plugin-kit). Change them there and run its `sync.sh`; `scripts/kit/check-manifests.py` fails CI on a local edit.
- Before pushing: `python3 scripts/kit/check-manifests.py --validate`, `python3 scripts/kit/secret-scan.py --tree`, `python3 scripts/kit/check-links.py`, then this repo's own checks.
<!-- kit:agents:end -->
