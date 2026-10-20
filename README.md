# sentry — a Claude Code plugin for setting up and auditing Sentry

Detects whether Sentry is set up in your repo, **audits** an existing setup or **initializes** a missing one through one findings ledger, applies only what you approve, and proves each change with a live event. Works on any language and platform. CLI-first on the new `sentry` v4 CLI (the successor of `sentry-cli`); no MCP server, no telemetry.

```
/plugin marketplace add yigitkonur/plugin-sentry
/plugin install sentry@plugin-sentry
```

Or in one step on Claude Code 2.1.275+: `/plugin install sentry --marketplace yigitkonur/plugin-sentry`.

> Sentry also publishes an official plugin that is *also named* `sentry`. Both can be enabled together: every command here is `/sentry:<verb>` and the skill names do not overlap with its `sentry-*` skills. `/sentry:doctor` tells you when both are present.

## Quick start

```
/sentry:start      # detect the stack, ask a few questions, then audit or initialize
/sentry:doctor     # is this machine ready? CLI, login, scopes, region, git state
```

`start` looks at the repo and decides for you: Sentry present, partial or legacy → audit; absent → init. You always answer the same short set of questions first (privacy, AI prompt capture, replay masking, org access, environments, volume, who owns releases). It never reuses an old answer silently.

## Commands

| Command | What it does |
|---|---|
| `/sentry:start` | Router: detect → policy → audit or init → report → approval |
| `/sentry:audit` | Audit what is there: SDK version, init, options removed in your major, sampling, environments, releases, source maps, privacy, noise, ownership, crons, replay, logs, profiling, AI monitoring, and more (60 checks) |
| `/sentry:init` | Propose the base setup plus extras that fit, from the live docs, as reviewable findings |
| `/sentry:apply` | Implement the findings you approved, one commit per group, build-checked; then verify |
| `/sentry:verify` | Prove applied changes with a marked event: arrival, readable stack trace, privacy scan of the arrived payload |
| `/sentry:org` | Read the Sentry organization behind the repo with 17 read-only probes; apply approved org changes |
| `/sentry:policy` | Answer (or change) the policy questions |
| `/sentry:doctor` | Tools, login, scopes, region, git, coexistence |
| `/sentry:clean` | Remove `.sentry-plugin/`, leftover trigger files, the `.gitignore` line it added |
| `triage` (model-invoked) | "Why is this failing in production?" Walks the CLI funnel: rank → view → corroborate. Seer only on request |
| `ground-rules` (model-invoked) | Look options up instead of recalling them; keep tokens out of files; claim only what was verified |

## How it works

1. **Detect** (`sentry-ctx detect`, pure Python 3.9+ standard library): units, ecosystem, framework and resolved versions, Sentry packages, init sites, DSN sources, release and CI wiring, secrets in tracked files. Libraries are never told to initialize Sentry.
2. **Steer**: which of 25 products apply to each unit, and why — `applicable`, `n/a` (with the reason) or `unknown`. Three different states are never merged: **clean**, **n/a**, **UNVERIFIED**.
3. **Audit / init**: read-only `auditor` agents (one per unit × product group) apply the module rubrics and the check catalog, and record findings with `ran`/`saw` evidence. The engine validates every finding; an unlisted check, a file outside the repo, a doc link off the allow-list or an org write without its exact call is rejected.
4. **Approve**: you pick findings by severity (P0–P3) or product. Org writes are listed as exact calls.
5. **Apply**: `implementer` edits only the files a finding names, builds, commits per group. Nothing is pushed.
6. **Verify**: a separate `verifier` sends a marked event from the real code path, waits for it, checks release, environment, stack-trace readability and privacy. A change is **verified** only up to the rung it reached (R0 build … R6 product).

### Several projects in one repo

When a repo holds more than one deployable unit (a site, a mobile app, an API, an MCP server), detect also records how they relate (`links` in `detect.json`: which unit calls which, CORS allow-lists, DSNs shared between units, `environment` spellings, Cloudflare service bindings between Workers), and one extra auditor judges the relations as the pseudo-unit `_links`: the trace chain from client to server (browser `tracePropagationTargets` and CORS headers, not asked of mobile or server clients), Worker-to-Worker RPC trace propagation, `prod` vs `production`, one project per app. Every edge is a static candidate that the auditor confirms by reading both sides.

### Cloudflare

Workers has its own Logs, Traces and Issues, on by default. If a unit runs on Cloudflare, one extra policy question (`cloudflare.owner`) decides which system owns which signal (Cloudflare logs and Sentry errors and traces, everything in Sentry, both on purpose, or Cloudflare exporting to Sentry over OTLP), and the `cf-observability` checks hold the configuration to that answer instead of adding a second copy of everything. Astro on Cloudflare is handled as a Worker (`@sentry/astro` plus `@sentry/cloudflare`, wrangler `main` pointing at the wrapped entry), not as a Node app.

The ledger lives in `.sentry-plugin/` (gitignored on your say-so): `policy.md`, `detect.json`, `plan.json`, `findings/`, `coverage.json`, `report.md`, `evidence/`.

## What it will not do

- It never reads or prints the CLI's credential and never asks for a token. It reuses your `sentry` login through `sentry api`.
- No Seer: `sentry issue explain|plan` spend money, so they run only if you ask.
- No write to Sentry without your approval of that exact call (a hook enforces it, and the engine checks it again).
- Marker events always use `--no-environ`; without it the CLI ships your whole shell environment to Sentry.
- No MCP server, no network calls except to `docs.sentry.io`/`cli.sentry.dev` (docs, cached 24 h) and your own `sentry` CLI.
- No guessing: every option name in the rubrics is declared with the official docs page that contains it, and CI re-checks that weekly.

### Hooks (five, deterministic, set `hook_mode` to `quiet` or `off`)

| Hook | Does |
|---|---|
| SessionStart | restores the run digest after `/compact`, resume or clear |
| Write guard | denies writing a Sentry token into a file git would track |
| Stale-API | after an edit, tells the model when it wrote an option your SDK major removed |
| Bash gate | denies token paste, `auth token`, `event send` without `--no-environ`, printing a credential file (`.sentryclirc`, `.env.sentry-build-plugin`, `sentry.properties`) by `cat`, a loop, a glob, a pipe or the Read/Grep tools, a credential file written where git would track it, and hand edits of the run state; asks before every Sentry mutation not approved in this run and session (every segment of a compound command is checked), and before an approval is recorded. CI and eval harnesses opt in with `SENTRY_PLUGIN_APPROVE_WRITES=1` in their own environment |
| Stop gate | refuses to finish while the run you own has unproven applied findings or leftover trigger files (max two blocks) |

## Headless runs (CI, evals, `claude -p`)

No question tool is available there, so two environment variables stand in for the human, both set by whoever runs the session (the model cannot set them for the hooks):

| Variable | Meaning |
|---|---|
| `SENTRY_PLUGIN_POLICY_ANSWERS=/path/answers.json` | the policy answers (`{"privacy.preset": "strict", "org_access": "read-only", ...}`, keys as in `sentry-ctx policy questions`). Without it a headless run stops at the policy step |
| `SENTRY_PLUGIN_APPROVE_WRITES=1` | lets `sentry-ctx run approve-write` pass without a permission prompt. Leave it unset and a headless run can read and report but never change Sentry |

Without these a headless run is report-only: it audits, writes `.sentry-plugin/report.md`, approves nothing and cleans nothing.

## Requirements

`python3` 3.9+, `git`, and the `sentry` CLI v4 (`curl https://cli.sentry.dev/install -fsS | bash`, or `npm install -g sentry`, or `brew install getsentry/tools/sentry`) with `sentry auth login` (`--read-only` is enough for audits). Without the CLI the repo-side audit still runs; every org-side row is reported UNVERIFIED, never skipped or called clean. Node/Go/Swift/etc. are needed only to build and run the code being verified.

## Porting from `sentry-cli` 3.x

`sentry-cli` 3.x and `sentry` v4 are one tool. `sentry-ctx cli-map` carries the full table and the audit emits a `rel.cli-version` finding with the exact v4 command for every v3 call it finds in your CI and scripts. The most common ones:

| 3.x | v4 |
|---|---|
| `sentry-cli releases new V` | `sentry release create ORG/V --project P` |
| `sentry-cli releases set-commits V --auto` | `sentry release set-commits ORG/V --auto` |
| `sentry-cli releases deploys V new -e ENV` | `sentry release deploy ORG/V ENV` |
| `sentry-cli sourcemaps upload DIR -r V` | `sentry sourcemap upload DIR --release V` |
| `sentry-cli upload-dif` / `upload-dsym` | `sentry debug-files upload` |
| `sentry-cli send-event -m MSG` | `sentry event send -m MSG --no-environ` |
| `sentry-cli monitors run SLUG -- CMD` | `sentry monitor run SLUG -- CMD` |
| `sentry-cli login` / `update` | `sentry auth login` / `sentry cli upgrade` |

## Verified against

Sentry documentation and SDK releases as of **2026-10-20**: JavaScript SDK v11 (11.8.0), Python SDK 2.x with the 3.0 alpha, Cocoa 9, React Native 8, `sentry` CLI 0.47. Rubric claims trace to official pages; `scripts/check.sh` re-fetches them.

## Development

```
scripts/check.sh --offline     # compile (3.9 and current), fixtures, plugin validation, secret scan
scripts/check.sh               # + identifiers, stale-API rows and links against the live docs
scripts/run-hook-evals.sh      # hook A/B evals (needs a logged-in claude CLI)
scripts/replay-events.py       # recorded real events through the privacy scan (also in check.sh)
scripts/check-sdk-types.py     # every removed/renamed JS stale-API row against the real @sentry packages (in check.sh, weekly in CI)
```

See `AGENTS.md`. `PORT.md` maps every file of the earlier `use-sentry`, `build-sentry-macos-swift` and `plugin-sentry-cli` material to its new home.

## License

MIT (see `LICENSE`). Vendored reference text from [getsentry/sentry-for-ai](https://github.com/getsentry/sentry-for-ai) is MIT as well; see `NOTICE`. Not affiliated with Sentry.
