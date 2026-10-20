# Using the `sentry` CLI (v4) from this plugin

The plugin is CLI-first and ships no MCP server. `sentry` v4 is the successor of `sentry-cli` 3.x (same project, new name, one
tool): https://cli.sentry.dev/migrating-from-v3.md . `sentry-ctx doctor` reports which one is installed; the command names for
v3 are in `sentry-ctx cli-map`.

## Install and login (the user runs these; the plugin never installs software or handles tokens)

- Install: `curl https://cli.sentry.dev/install -fsS | bash` (or `npm install -g sentry`, or `brew install getsentry/tools/sentry`).
- Audit login: `sentry auth login --read-only` (OAuth device flow, opens a browser). Needs project:read, org:read, event:read,
  member:read, team:read.
- Login that can create projects/monitors/alerts: `sentry auth login` (default scopes; verified on a live org: alerts:read/write,
  event:read/write, member:read, org:read, project:read/write/admin, team:read/write/admin). Not included by default:
  `org:write`, `org:ci`, `project:releases`, `member:write`. Releases and source-map uploads still worked with the default login.
- `sentry auth status --json` shows the user, masked token, expiry and orgs; **not** the scopes. Scopes: `sentry api /api/0/`
  returns `auth.scopes`.
- Never run `sentry auth token` or `sentry auth status --show-token`, never read `~/.config/sentry/cli.db`, never put a token on
  a command line. Organization tokens (`sntrys_`, fixed `org:ci` scope) are for CI uploads only and cannot audit.
- Precedence: stored login > `SENTRY_AUTH_TOKEN` > `SENTRY_TOKEN`; `SENTRY_FORCE_ENV_TOKEN=1` makes the env token win.
- The CLI sends its own usage telemetry unless `SENTRY_CLI_NO_TELEMETRY=1` (or `DO_NOT_TRACK`). The engine sets it for its calls.

## Targets, output, exit codes

- Target syntax: `<org>/<project>`; `<org>/` (trailing slash) = every project in the org; a bare name is a project-name search.
  With no target the CLI auto-detects from `.sentryclirc`, DSNs in the repo and the directory name: run commands directly instead
  of listing orgs and projects first.
- `--json` for machines, `--fields a,b.c` to keep only named fields (list commands return `{data, hasMore, hasPrev}`).
  `SENTRY_NO_CACHE=1` disables the on-disk response cache (set it for audits). `--fresh` bypasses it per command.
- Exit codes (https://cli.sentry.dev/exit-codes.md): 0 ok, 1 general, 10 not authenticated, 11 token expired, 12 token invalid,
  13 host scope (credentials do not match the target host), 20 config/DSN, 21 validation, 22 missing context (org/project),
  23 not found, 30 API error, 31 timeout, 40 Seer not enabled, 41 Seer needs a paid plan, 42 AI disabled, 51 device flow,
  60 command-specific (`sentry api` uses it for any non-2xx, observed), 61-64 setup-wizard errors.

## `sentry api`: the REST escape hatch

`sentry api [-X METHOD] [-F key=value]... [--input file|-] [--dry-run] <endpoint>` reuses the stored login, so no token is ever in
the plugin, a script, a transcript or a file. Rules the plugin follows:

- Relative paths (`/organizations/<org>/...`) work for org- and project-level endpoints on a region org (verified on an EU org);
  an absolute region URL also works. Hosts outside the login's host exit 13.
- Reads only during audits: `-X GET`. Every write is first shown with `--dry-run`, approved, then run. The plugin's engine builds
  org probes as GET-only by construction.
- No auto-pagination: loop `-F cursor=<value>` using the `Link` header cursor, bounded to 10 pages.
- `sentry schema --search <word>` lists endpoints; it does not show request bodies. For a body, read the docs page or the
  `getsentry/sentry` source (uptime example: `references/forge/products/uptime.md`).

## Commands the plugin uses

| Intent | v4 command |
|---|---|
| Create a project / read its DSN | `sentry project create <org>/<name>:<platform> [--team T]` / `sentry dsn list <org>/<project>` |
| Release | `sentry release create <org>/<version> --project <p>`, `release set-commits <org>/<version> --auto`, `release finalize`, `release deploy <org>/<version> <environment>` |
| Source maps | `sentry sourcemap inject <dir>` then `sentry sourcemap upload <dir> --release <v> --org <o> --project <p>` (injects Debug IDs automatically; `--org`/`--project` are long flags only) |
| Native / mobile symbols | `sentry debug-files upload <path>... [--include-sources] --org <o> --project <p>`; `debug-files check <path>` |
| Cron wrapper | `sentry monitor run <slug> -- <command>` (DSN-authenticated; no login needed) |
| Marker event | `sentry event send <org>/<project> -m <msg> -l error --tag plugin_marker:<id> --env <e> --no-environ` |
| Read issues / events | `sentry issue list <org>/<project> -q 'is:unresolved' --json --fields shortId,title,level,count`, `sentry issue view <id> --json`, `sentry event view <org>/<project>/<event-id> --json` |
| Aggregates | `sentry explore <org>/ -d errors -F environment -F "count()" -t 7d --json` |
| Docs | `sentry docs query "<question>"`; the plugin prefers `sentry-ctx docs page <path>` (fetches the markdown page) |

`sentry event send` (and `send-event`) attach the **whole process environment** unless `--no-environ`. Always pass it.

`--org` and `--project` are accepted by every command, before or after the subcommand, although a command's own `--help` usage and the CLI docs' "Global Options" omit them. Do not conclude from `--help` that they do not exist. Tested on 0.47.0: `sentry dsn list --org <o> --project <p>` returns that project's DSN, a wrong org answers 404, with no flags and no DSN in the directory it fails with "Organization and project are required", and an invented flag is rejected. The documented routes are `SENTRY_ORG`, `SENTRY_PROJECT` (which may be `org/project`), the DSN, and an `ORG/` prefix; prefer them in CI files.

## Accelerators (all followed by the same audit)

- **`sentry init`** (experimental): hosted setup wizard. `sentry init <org>/<project> . --dry-run --yes --features errors,tracing,logs --no-tui`
  previews the changed files without touching the tree (observed). It **uploads project file excerpts to a Sentry service for
  analysis**, so ask the user first. A real run edits files and installs the SDK. Observed on a fresh Next.js app (SDK 11.8.0): it
  wrote `enableLogs: true` into three init files, which does not type-check (TS2353) because v11 removed the option; it also
  left no `environment`, `release` or `dataCollection`, no auth-token plumbing, and no `.gitignore` entry. Treat its output as
  untrusted first-party code.
- **`@sentry/wizard`** (`npx @sentry/wizard@latest -i <integration> --disable-telemetry`, flags `--non-interactive`, `--quiet`, `--org`,
  `--project`, `--ignore-git-changes`, `--uninstall`): needs the user's browser login, so hand it over as a `! npx ...` line.
  Integrations: reactNative, flutter, ios, appleSnapshots, android, cordova, angular, cloudflare, electron, nextjs, nuxt, remix,
  reactRouter, sveltekit, sourcemaps.
- **Manual** from the live docs page for the detected platform (`sentry-ctx docs page platforms/<path>`).

## Porting `sentry-cli` 3.x to `sentry` v4 (rel.cli-version)

`sentry-ctx cli-map` has the full table; `--intent <name>` gives a ready pair (create_release, upload_sourcemaps, upload_dsyms,
deploy, wrap_cron, marker_event, install). Rules for a port:

1. Install step: `npm install -g sentry` (or the install script), binary name `sentry`.
2. Plural groups become singular: `releases new` -> `release create`, `monitors run` -> `monitor run`, `organizations` -> `org`.
3. `deploys new -r V -e ENV` -> `release deploy <org>/V ENV`; `deploys list` -> `release deploys <org>/V`.
4. `upload-dsym` / `upload-dif` -> `debug-files upload`; `upload-proguard` -> `proguard upload`; `sourcemaps` also works as written.
5. `-o`/`-p` short flags are gone: use `--org`/`--project`, a `<org>/` prefix on the version, or `SENTRY_ORG`/`SENTRY_PROJECT`.
6. `--auth-token T` on a command line becomes the `SENTRY_AUTH_TOKEN` environment variable (from the CI secret store), plus
   `SENTRY_FORCE_ENV_TOKEN=1` when a stored login must not win. A token on a command line is a P0 finding in its own right.
7. `--url` (host) becomes `SENTRY_URL`/`SENTRY_HOST`; `--header` becomes `SENTRY_CUSTOM_HEADERS`; `--allow-failure` is gone: use `|| true`.
8. Drop flags with no v4 equivalent (`sourcemaps upload --validate/--wait/--note/--url-suffix/...`, `releases set-commits --ignore-missing`).
9. Re-run the pipeline once and read the output: the port is verified when the upload step shows the files and the release.
