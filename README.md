# sentry: a claude code and codex plugin that sets sentry up right and proves it

tl;dr: point it at any repo. it works out whether sentry is there, audits it or sets it up from scratch, changes only what you approve, then proves every change with a real event landing in your sentry org. no "should work now" vibes. it runs on the new `sentry` v4 cli (the successor to `sentry-cli`), and it has no mcp server and no telemetry. it runs in claude code and in codex (see [codex](#codex)).

## install

from your terminal, two steps:

```sh
claude plugin marketplace add yigitkonur/plugin-sentry
claude plugin install sentry@plugin-sentry
```

or the one-liner (it adds the marketplace for you):

```sh
claude plugin install sentry --marketplace yigitkonur/plugin-sentry
```

already inside a claude code session? same thing as slash commands:

```
/plugin marketplace add yigitkonur/plugin-sentry
/plugin install sentry@plugin-sentry
```

check it landed (and if a claude code session was already open, restart it):

```sh
claude plugin list          # look for sentry@plugin-sentry with Status: ✔ enabled
```

new versions: a release is cut automatically on every shipped change, but claude code only pulls it by itself when auto-update is on for the marketplace, and that is **off by default** for third-party marketplaces. turn it on once: in a session run `/plugin`, open **Marketplaces**, pick `plugin-sentry`, **Enable auto-update**. (or put `"autoUpdate": true` on its `extraKnownMarketplaces` entry in your settings.) `/sentry:doctor` tells you when it's off. if you run with `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, also set `FORCE_AUTOUPDATE_PLUGINS=1`, or the update pass is skipped.

the install may say `1 userConfig option not yet set`. that's `hook_mode`, and it defaults to `on`, so you can ignore it, or set it right away with `--config hook_mode=on` (or `quiet` / `off`).

### installed everywhere, on only where you want it

the plugin adds a few hundred tokens to every session while it's enabled. so install it globally, keep it switched off, and turn it on per project when you actually want it (claude below; codex has its own block right after):

```sh
claude plugin install sentry --marketplace yigitkonur/plugin-sentry     # once per machine, installs switched off (the manifest says defaultEnabled: false)
claude plugin disable sentry@plugin-sentry --scope user                  # only needed on an older copy that installed enabled
```

then in any project:

```sh
claude plugin enable sentry@plugin-sentry --scope project     # on here (restart the session, or /reload-plugins)
claude plugin disable sentry@plugin-sentry --scope project    # off here again
```

`scripts/sp` wraps that (and codex too, if you have it): `sp on`, `sp off`, `sp status` for the folder you're in (`sp on ~/some/project` for another one). copy it to a folder on your PATH (`cp scripts/sp ~/.local/bin/sp`). it installs the plugin globally (disabled) first if the machine doesn't have it yet, writes to `.claude/settings.local.json` instead when the repo tracks `.claude/settings.json`, and adds an untracked settings file to `.git/info/exclude` so `git add -A` can't sweep it in.

checked live through herdr on a scratch project: a fresh claude there answered `NONE` when asked for `sentry:` skills, after `sp on` it listed `sentry:ground-rules` and `sentry:triage`, and after `sp off` it answered `NONE` again.

updating and removing:

```sh
claude plugin marketplace update plugin-sentry
claude plugin update sentry@plugin-sentry
claude plugin uninstall sentry@plugin-sentry
```

heads up: sentry also ships an official plugin that is *also* called `sentry`. you can run both. every command here is `/sentry:<verb>`, and none of our skill names clash with its `sentry-*` skills. `/sentry:doctor` tells you when both are on.

### codex

same repo, same plugin, one extra marketplace file (`.agents/plugins/marketplace.json`). install it globally and switch it off, the same way:

```sh
codex plugin marketplace add yigitkonur/plugin-sentry
codex plugin add sentry@plugin-sentry
scripts/codex-plugin-project.sh global-off sentry@plugin-sentry     # codex has no `plugin disable`, this edits ~/.codex/config.toml
```

on in one project (it writes `<project>/.codex/config.toml`, which codex only reads for a trusted project, so `--trust` adds the project to your trusted list. that also turns on the project's own hooks and rules, so only do it for projects you own):

```sh
codex-plugin-project.sh on sentry@plugin-sentry . --trust       # run inside the project, then start a new codex there
codex-plugin-project.sh off sentry@plugin-sentry                # off again
codex plugin list                                               # "installed, enabled" inside the project, "installed, disabled" elsewhere
```

`sp on --trust` / `sp off` / `sp status` do both hosts at once (copy `scripts/sp` and `scripts/codex-plugin-project.sh` to a folder on your PATH).

update: `codex plugin marketplace upgrade plugin-sentry`, then start a new session. the first time codex loads the plugin's hooks it asks you to review them (`t` trusts all).

what's different in codex: there are no `/sentry:` slash commands, so you name the skill (`$doctor`, `$audit`, or just ask for "the sentry audit"); there are no subagents, so the audit runs inline, one cell at a time; there is no question tool, so questions come as numbered lists and you answer in chat; and the auditor's hard read-only gate is claude-only. the hooks (token paste, `enableLogs` on the wrong sdk major, unapproved sentry writes, unfinished run) work in both, including writes made with `apply_patch`. one difference: codex hooks can't ask you anything (an "ask" decision is rejected and the command then runs anyway), so in codex an unapproved sentry write is *denied* outright, and you record the approval yourself in your own terminal with `sentry-ctx run approve-write` after saying yes in chat. also: the `sentry` cli keeps its login database under your home folder, so codex's `workspace-write` sandbox can't run it (`unable to open database file`); use a mode that can write there.

smoke-tested live: a fresh codex in a trusted scratch project loaded the doctor skill and ran it by full path (`sentry v4 CLI : 0.47.0`, login and region lines on screen), `apply_patch` writing a `sntryu_` token was blocked, and an unapproved `sentry api -X PUT` was blocked.

no github ssh key on the machine? set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`, or background updates fail quietly.

## quick start

```
/sentry:doctor     # is this machine ready? cli, login, scopes, region, git
/sentry:start      # detect the stack, ask a few questions, then audit or init
```

`start` reads the repo and picks the path for you: sentry present, half-done or legacy means audit; no sentry means init. either way you answer the same short set of questions first: privacy, ai prompt capture, replay masking, org access, environments, volume, and who owns releases. it never quietly reuses an old answer.

## commands

| command | what it does |
|---|---|
| `/sentry:start` | the router: detect → policy → audit or init → report → approval |
| `/sentry:audit` | 60 checks on what's there: sdk version, init, options your major removed, sampling, environments, releases, source maps, privacy, noise, ownership, crons, replay, logs, profiling, ai monitoring and more |
| `/sentry:init` | proposes the base setup plus the extras that fit, straight from the live docs, as findings you can review |
| `/sentry:apply` | implements the findings you approved, one commit per group, build-checked, then verifies |
| `/sentry:verify` | proves applied changes with a marked event: it arrived, the stack trace is readable, and the payload passed a privacy scan |
| `/sentry:org` | reads the sentry org behind the repo with 17 read-only probes, and applies org changes you approved |
| `/sentry:policy` | answer, or change, the policy questions |
| `/sentry:doctor` | tools, login, scopes, region, git, coexistence |
| `/sentry:clean` | removes `.sentry-plugin/`, leftover trigger files and the `.gitignore` line it added |
| `triage` (model-invoked) | "why is this failing in prod?" walks the cli funnel: rank → view → corroborate. it runs seer only when you ask |
| `ground-rules` (model-invoked) | looks options up instead of guessing them, keeps tokens out of files, and claims only what was verified |

## how it works

1. **detect** (`sentry-ctx detect`, pure python 3.9+ stdlib): units, ecosystem, framework and resolved versions, sentry packages, init sites, dsn sources, release and ci wiring, secrets in tracked files. libraries never get told to init sentry.
2. **steer**: which of 25 products apply to each unit, and why: `applicable`, `n/a` (with the reason) or `unknown`. three states never get mashed together: clean, n/a and `UNVERIFIED`.
3. **audit / init**: read-only `auditor` agents, one per unit × product group, apply the module rubrics and the check catalog, and file findings with `ran`/`saw` evidence. the engine validates every finding. it rejects an unlisted check, a file outside the repo, a docs link off the allow-list and an org write without its exact call.
4. **approve**: you pick findings by severity (P0–P3) or by product. org writes show up as the exact calls.
5. **apply**: the `implementer` edits only the files a finding names, builds, and commits per group. nothing gets pushed.
6. **verify**: a separate `verifier` sends a marked event from the real code path, waits for it, then checks release, environment, stack-trace readability and privacy. a change counts as verified only up to the rung it actually reached (R0 build … R6 product), and the engine refuses a lower rung.

### several projects in one repo

got a site, a mobile app, an api and an mcp server in one repo? detect also maps how they connect (`links` in `detect.json`):

- which unit calls which, over http, cloudflare service bindings or durable object bindings
- cors allow-lists
- dsns shared between units
- `environment` spellings

one extra auditor judges those connections as the pseudo-unit `_links`:

- the trace chain from client to server: browser `tracePropagationTargets` plus cors headers. mobile and server clients don't get the cors question.
- worker-to-worker rpc trace propagation
- `prod` vs `production`
- one sentry project per app

every edge is a static candidate, and the auditor confirms it by reading both sides.

### cloudflare

workers has its own observability. workers logs is on by default for new workers, and traces and issues are opt-in. when a unit runs on cloudflare, one extra policy question (`cloudflare.owner`) decides who owns which signal:

- **split**: cloudflare logs, sentry errors and traces
- **sentry**: everything in sentry
- **both**: both, on purpose
- **otlp**: cloudflare exports to sentry over otlp

the `cf-observability` checks then hold your config to that answer, so nothing gets stored, billed or paged twice by accident. astro on cloudflare is handled as a worker (`@sentry/astro` plus `@sentry/cloudflare`, with wrangler `main` pointing at the wrapped entry), not as a node app.

the run state lives in `.sentry-plugin/` (gitignored if you say so): `policy.md`, `detect.json`, `plan.json`, `findings/`, `coverage.json`, `report.md`, `evidence/`.

## what it won't do

- it never reads or prints the cli's credential, and it never asks you for a token. it reuses your `sentry` login through `sentry api`.
- no seer by default: `sentry issue explain|plan` costs money, so it runs only when you ask.
- nothing gets written to sentry until you approve that exact call. a hook enforces it, and the engine checks again.
- marker events always use `--no-environ`. without it, the cli ships your whole shell environment to sentry.
- no mcp server. the only network calls go to the docs (`docs.sentry.io`, `cli.sentry.dev` and `developers.cloudflare.com`, cached for 24 h) and to your own `sentry` cli.
- no guessing: every option name in the rubrics is declared together with the official docs page that contains it, and ci re-checks that weekly.

### hooks (five of them, deterministic; set `hook_mode` to `quiet` or `off`)

| hook | does |
|---|---|
| sessionstart | restores the run digest after `/compact`, resume or clear |
| write guard | blocks writing a sentry token into any file git would track |
| stale-api | after an edit, tells the model when it used an option your sdk major removed |
| bash gate | blocks token paste, `auth token`, `event send` without `--no-environ`, and hand edits of the run state. it also blocks dumping or committing a credential file (details below). it asks before any sentry write not approved in this run and session, and before an approval gets recorded. |
| stop gate | won't let the run you own finish with unproven applied findings or leftover trigger files (it blocks at most twice) |

credential files are `.sentryclirc`, `.env.sentry-build-plugin` and `sentry.properties`. the bash gate blocks printing one by `cat`, a loop, a glob, a pipe or the read/grep tools, and it blocks writing one anywhere git would track it. every segment of a compound command gets checked. ci and eval harnesses opt in to writes with `SENTRY_PLUGIN_APPROVE_WRITES=1` in their own environment.

## headless runs (ci, evals, `claude -p`)

there's no question tool in headless mode, so two env vars stand in for you. the person running the session sets them; the model can't set them for the hooks.

| variable | meaning |
|---|---|
| `SENTRY_PLUGIN_POLICY_ANSWERS=/path/answers.json` | the policy answers (`{"privacy.preset": "strict", "org_access": "read-only", ...}`, keys as in `sentry-ctx policy questions`). without it, a headless run stops at the policy step |
| `SENTRY_PLUGIN_APPROVE_WRITES=1` | lets `sentry-ctx run approve-write` pass without a permission prompt. leave it unset and a headless run can read and report but never change sentry |

with neither set, a headless run is report-only: it audits, writes `.sentry-plugin/report.md`, and approves and cleans nothing.

## requirements

you need:

- `python3` 3.9+
- `git`
- the `sentry` cli v4, installed one of these ways:
  - `curl https://cli.sentry.dev/install -fsS | bash`
  - `npm install -g sentry`
  - `brew install getsentry/tools/sentry`
- then `sentry auth login` (`--read-only` is enough for audits)

no cli? the repo-side audit still runs, and every org-side row is reported as `UNVERIFIED`, never skipped and never called clean. node, go, swift and friends are only needed to build and run the code being verified.

## porting from `sentry-cli` 3.x

`sentry-cli` 3.x and `sentry` v4 are the same tool, new names. `sentry-ctx cli-map` has the full table, and the audit files a `rel.cli-version` finding with the exact v4 command for every v3 call it finds in your ci and scripts. the common ones:

| 3.x | v4 |
|---|---|
| `sentry-cli releases new V` | `sentry release create ORG/V --project P` |
| `sentry-cli releases set-commits V --auto` | `sentry release set-commits ORG/V --auto` |
| `sentry-cli releases deploys V new -e ENV` | `sentry release deploy ORG/V ENV` |
| `sentry-cli sourcemaps upload DIR -r V` | `sentry sourcemap upload DIR --release V` |
| `VERSION=$(sentry-cli releases propose-version)` | `VERSION=$(sentry release propose-version \| head -n 1)` (v4 prints a second `Detected from …` line on stdout) |
| `sentry-cli sourcemaps upload --debug-id-reference BUNDLE.hbc MAP` | keep it on sentry-cli 3: v4 can't upload a hermes bytecode bundle (react native / expo) |
| `sentry-cli upload-dif` / `upload-dsym` | `sentry debug-files upload` |
| `sentry-cli send-event -m MSG` | `sentry event send -m MSG --no-environ` |
| `sentry-cli monitors run SLUG -- CMD` | `sentry monitor run SLUG -- CMD` |
| `sentry-cli login` / `update` | `sentry auth login` / `sentry cli upgrade` |

## verified against

sentry docs and sdk releases as of **2026-10-21**: javascript sdk v11 (11.8.0), python sdk 2.x with the 3.0 alpha, cocoa 9, react native 8 and `sentry` cli 0.47. it was run live against a real eu org on next.js, go (gin), fastapi, a swiftui macos app, a cloudflare worker (hono), an mcp server, astro on cloudflare and expo. rubric claims trace to official pages, and `scripts/check.sh` re-fetches them.

## development

```sh
scripts/check.sh --offline     # compile (3.9 and current), fixtures, plugin validation, secret scan
scripts/check.sh               # + identifiers, stale-api rows and links against the live docs
scripts/run-hook-evals.sh      # hook a/b evals (needs a logged-in claude cli)
scripts/replay-events.py       # recorded real events through the privacy scan (also in check.sh)
scripts/check-sdk-types.py     # every removed/renamed js stale-api row against the real @sentry packages (in check.sh, weekly in ci)
```

see `AGENTS.md`. `PORT.md` maps every file of the older `use-sentry`, `build-sentry-macos-swift` and `plugin-sentry-cli` material to its new home.

## license

mit (see `LICENSE`). vendored reference text from [getsentry/sentry-for-ai](https://github.com/getsentry/sentry-for-ai) is mit too; see `NOTICE`. not affiliated with sentry.
