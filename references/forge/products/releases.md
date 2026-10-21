# Releases (product id: releases)

Covers the release string, release object (commits, finalize, deploys), release health, CI release step and CLI version. Source
maps and debug files: `products/debug-artifacts`. SDK-side `release`/`environment` are also read by `core.release`, `core.environment`.

## Fit

| Evidence in the repo | Worth proposing |
|---|---|
| Any deployed service or app with an `init` call and a CI/CD file (`.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile`, `bitbucket-pipelines.yml`, `.circleci`, Netlify/Vercel build) | Tag + release object + deploy. The tag alone gives release filtering and regression detection; commits, finalize and deploys need the CI half (`references/upstream/releases/ci-pipeline`). |
| Mobile/desktop app (Xcode project, Gradle app module, Flutter, React Native, Electron, .NET client) | Release health (sessions) plus a CI release step; adoption stages only show for mobile projects filtered to one environment. |
| A Sentry bundler plugin or framework SDK build wrapper already in the build config | Configure the plugin; do not add a parallel CLI pipeline (two releases with different names). |
| Library, local-only script, repo without CI | Not worth a CI release step. No SCM integration is still fine: commits can be sent from CI (local mode or the API with `patch_set`). |

## Properly configured

Two halves that must carry one identical string (JS v11, Python 2.x/3.0 alpha, Cocoa 9, Java/Android 8, Go, .NET 6, Ruby 7, PHP 4):

| Half | What "right" looks like | Where |
|---|---|---|
| Tag (SDK) | `release` set once from the build/deploy value, `environment` set from the deploy environment. | `init` file; env `SENTRY_RELEASE` |
| Release object (CI) | Created after build and before deploy, commits associated, finalized, deploy recorded into an environment. | CI file or bundler plugin options |

Release name rules (naming page): unique per organization, so prefix with something project-specific; no newline, tab, `/` or `\`;
not only `.`, `..` or a space; at most 200 characters. Semver form `package@version` or `package@version+build`; the parentheses form
`1.0 (2)` is display only and errors if used as a name. Commit SHA is the other recommended form. Do not switch scheme mid-project:
regression detection and `release:latest` sorting differ between semver and SHA/time-based projects.

Default release per SDK when nothing is set (docs pages, fetched this session):

| SDK | Default | Explicit setting |
|---|---|---|
| Python 2.x | `SENTRY_RELEASE`, else git HEAD SHA, else hosting-provider env vars | `release` in `sentry_sdk.init` |
| JS browser/Node | Node: not documented on the page; bundled apps get the injected plugin value | `release` in `init`; plugin `release.name` |
| Apple (Cocoa 9) | `CFBundleIdentifier@CFBundleShortVersionString+CFBundleVersion` | `releaseName` |
| Android | `packageName@versionName+versionCode` | manifest meta-data `io.sentry.release` |
| .NET | `SENTRY_RELEASE`, then assembly informational/version attributes | `options.Release` |
| Go, PHP, Java | none stated | `Release` (Go), `'release'` (PHP), `setRelease` (Java) |

CI release step, by route (check which one the project already uses before proposing another):

| Route | Notes from the sources |
|---|---|
| Bundler plugin / framework build options | Options under `release`: `name`, `inject`, `create`, `finalize` (default `true`), `dist`, `vcsRemote`, `setCommits` (default `{ auto: true }`; `false` disables), `deploy` (`false` disables automatic deployment detection; `env` sets the environment). `setCommits` children: `auto`, `repo`, `commit`, `previousCommit`, `ignoreMissing`, `ignoreEmpty`. |
| `getsentry/action-release@v3` | Needs `actions/checkout` with `fetch-depth: 0`. Inputs `release` (default the commit SHA), `environment` (omit it and no deploy is created), `set_commits` (`auto`, `skip` or `manual`), `ignore_missing`, `ignore_empty`, `finalize`, `dist`, `sourcemaps`. Env: `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`. |
| `sentry` v4 CLI (successor of `sentry-cli` 3.x) | `sentry release create <org>/<version> --project <p> [--finalize]`, `release set-commits <org>/<version> --auto` (needs a local git checkout) or `--local` or `--commit REPO@SHA`, `release finalize`, `release deploy <org>/<version> <environment> [name]`, `release propose-version` (capture it as `$(sentry release propose-version | head -n 1)`: on 0.47.0 stdout also carries a `Detected from ...` line, observed 2026-10-21, not on a docs page). |
| Raw API | Create-release endpoint with `commits[]`; `patch_set` is required for suspect commits and suggested assignees, `author_email` for assignees. |

Release health (sessions): SDK sends sessions when enabled, a `release` and an `environment` are set, and a user identity exists for
crash-free users. Documented per SDK:

| SDK | Sessions | Opt-out / caveat |
|---|---|---|
| JS browser (v11) | On by default via the `BrowserSession` integration; a session spans client-side navigations (before v11 each navigation started one) | Remove the integration; unhandled errors mark the session `unhandled` (before v11: `crashed`) |
| JS Node | Request-mode sessions via `httpIntegration` | `sessions: false`; the removed `autoSessionTracking` is in `data/stale-apis/js.tsv` |
| Python 2.x | On by default on supported web frameworks | `auto_session_tracking=False` |
| Apple (Cocoa 9) | On by default; ends after 30 s in background (`sessionTrackingIntervalMillis`) | `enableAutoSessionTracking = false` |
| Android | On by default; manifest `io.sentry.auto-session-tracking.enable` | AndroidX transitive deps removed breaks it |
| Ruby | On by default | `auto_session_tracking = false` |
| .NET 6 | Off by default | `AutoSessionTracking` true; client apps only |
| Java | Manual `Sentry.startSession()` / `Sentry.endSession()` | `distinctId` needed for crash-free users |

Release health per the setup page: Android, Flutter, iOS, JS browser and Node, Electron, Native, PHP, Python, React Native, Rust, .NET, Unity.

## Checks

| check id | read | passes when |
|---|---|---|
| rel.commits-deploys | CI files; bundler/framework config for `setCommits` and `deploy`; `sentry release view <org>/<version> --json`, `sentry release deploys <org>/<version>`, `sentry repo list <org>/` | CI checks out full history (`fetch-depth: 0` or equivalent unshallow), runs commit association once per release (plugin default or one CLI/action step, `set_commits` not `skip`), and records a deploy into a real environment; the newest release in the org has commits and at least one deploy. If no repo integration exists, commits are still sent (local mode or API with `patch_set`). |
| rel.cli-version | CI files, Dockerfiles, `package.json`, install scripts (`sentry-cli`, `@sentry/cli`, `npm install -g sentry`, `curl https://cli.sentry.dev/install`) | The CLI is pinned (`SENTRY_VERSION` for the install script, or an exact npm version), not floating `latest`; if `sentry-cli` 3.x is used, the port to `sentry` v4 is noted (see the table below; `sentry-ctx cli-port` prints the exact v4 command for every 3.x call found in CI files and scripts). |
| rel.health | `init` files for the sessions opt-outs above; user set on scope (JS: `initialScope`); `sentry release list <org>/ --json` for session counts | Session tracking is not disabled where the platform supports it (and enabled where off by default), `release` and `environment` are set, a user identifier is set so crash-free users computes, and the org shows sessions for the latest release. Browser dashboards or crash-rate alerts written before v11 are checked for the `crashed` to `unhandled` change. |
| ci.release-step | Every CI job that builds a deployable artifact; bundler plugin config; Xcode/Gradle/Flutter plugin config | Each deploy build runs the release step (create/commits/finalize/deploy plus its artifact upload, see `products/debug-artifacts`) with the same release string as the SDK `init` of that build, after build and before deploy; the token comes from the CI secret store (token rules: `products/privacy`). |

Porting `sentry-cli` 3.x to `sentry` v4 (migration page; `sentry-ctx cli-map` has the full table):

| 3.x | v4 | Audit note |
|---|---|---|
| `sentry-cli releases new V` | `sentry release create <org>/V --project P` | singular group names; plural alone only lists |
| `releases set-commits V --auto --ignore-missing` | `release set-commits <org>/V --auto` | no `--ignore-missing` in v4 `--help` (observed on the installed 0.47.0 binary); use `--local` or an explicit `--commit` range when history is rewritten |
| `deploys new -r V -e ENV` | `release deploy <org>/V ENV` | environment and name are positionals |
| `--auth-token T` flag | `SENTRY_AUTH_TOKEN` from the secret store | a token on a command line is a `priv.token-ci-logs` finding |
| `npm i @sentry/cli` / `curl .../sentry-cli` | `npm install -g sentry` / `curl https://cli.sentry.dev/install` | the binary installed in this environment reports 0.47.0, so "v4" is the doc name, not the printed version |

## Common mistakes

| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Release exists with commits and a deploy but shows 0 events | SDK and CI strings differ (`v` prefix, short vs full SHA, build suffix) | Derive both from one variable; compare a real event's `release` tag with the release list | naming page; `references/upstream/releases/troubleshooting` |
| Release has no commits | Shallow clone, step runs outside the repo, or no commit step at all | Full-depth checkout; run the step where `.git` exists | action-release README |
| `set-commits` fails after a squash/rebase/force-push | Previous release commit no longer in the repo | 3.x or action/plugin: `--ignore-missing`, `ignore_missing`, `ignoreMissing`; v4: local mode or explicit range | cli/releases page; bundler plugin docs source |
| "Resolve in next release" resolves nothing | Release never finalized | `finalize` at deploy time (plugin default is `true`) | cli/releases page |
| Two releases per build | Bundler plugin and a hand-written CLI step both run with different names | Keep one route | `references/upstream/releases/ci-pipeline` |
| Hard-coded `release` in `init` drifts from the CI string while a plugin injects its own | Two sources of truth | Set it once, in the plugin's `release.name` or one env var | `references/upstream/releases/tagging` |
| Release created after the deploy | Events arrive first and Sentry auto-creates a bare release | Run the step between build and deploy | JS releases page |
| Crash-free rate empty or wrong | Sessions off, `environment` missing, platform without release health, staging in the same environment | Fix per the sessions table; set `environment` | setup and health pages |
| Deploy never recorded | Release creation does not create a deploy; the action skips it without `environment` | Add the deploy step | setup page; action-release README |

## Volume, cost and overhead

- Sessions are not a billable event type (stats page). They are also not subject to inbound filters or sampling (health page), so
  volume levers on `products/quota` do not shrink release health.
- Releases, commits and deploys are not a quota category on the pricing pages fetched; no billing claim is made for artifacts.
- Overhead: a full-depth checkout in CI (my inference: slower on large repos); the action sends its own telemetry unless
  `disable_telemetry` is set.

## Verify (R6)

Ship one build through CI, then compare the two halves (events and object are separate lookups):

- `sentry release view <org>/<version> --json` for the exact version the SDK reports: commit and deploy counts non-zero.
- `sentry release deploys <org>/<version>`: an entry in the expected environment.
- `sentry issue list <org>/<project> -q 'release:<version>' --json --fields shortId,title`: events carry the identical string; zero hits
   with a release that has commits is the name-mismatch signature.
- `sentry release list <org>/ --json` (sort by sessions): the latest release shows sessions; for mobile, filter to one environment
   before reading the adoption stage.

Without org access the finding stays source-only; the proof is the CI log of the release step.

## Sources

- references/upstream/concepts/releases; references/upstream/releases/{index,ci-pipeline,tagging,troubleshooting}
- https://docs.sentry.io/product/releases/setup.md
- https://docs.sentry.io/product/releases/naming-releases.md
- https://docs.sentry.io/product/releases/associate-commits.md
- https://docs.sentry.io/product/releases/health.md
- https://docs.sentry.io/product/stats.md
- https://docs.sentry.io/cli/releases.md
- https://cli.sentry.dev/migrating-from-v3.md
- https://cli.sentry.dev/commands/release.md
- https://cli.sentry.dev/getting-started.md
- https://github.com/getsentry/action-release/blob/master/README.md
- https://github.com/getsentry/sentry-javascript-bundler-plugins/blob/main/packages/dev-utils/src/generate-documentation-table.ts
- https://docs.sentry.io/platforms/javascript/configuration/releases.md
- https://docs.sentry.io/platforms/javascript/guides/node/configuration/releases.md
- https://docs.sentry.io/platforms/python/configuration/releases.md
- https://docs.sentry.io/platforms/python/configuration/sessions.md
- https://docs.sentry.io/platforms/apple/configuration/releases.md
- https://docs.sentry.io/platforms/android/configuration/releases.md
- https://docs.sentry.io/platforms/ruby/configuration/releases.md
- https://docs.sentry.io/platforms/dotnet/configuration/releases.md
- https://docs.sentry.io/platforms/java/configuration/releases.md

## Identifiers

```identifiers
setCommits | https://github.com/getsentry/sentry-javascript-bundler-plugins/blob/main/packages/dev-utils/src/generate-documentation-table.ts
ignoreMissing | https://github.com/getsentry/sentry-javascript-bundler-plugins/blob/main/packages/dev-utils/src/generate-documentation-table.ts
ignoreEmpty | https://github.com/getsentry/sentry-javascript-bundler-plugins/blob/main/packages/dev-utils/src/generate-documentation-table.ts
previousCommit | https://github.com/getsentry/sentry-javascript-bundler-plugins/blob/main/packages/dev-utils/src/generate-documentation-table.ts
vcsRemote | https://github.com/getsentry/sentry-javascript-bundler-plugins/blob/main/packages/dev-utils/src/generate-documentation-table.ts
set_commits | https://github.com/getsentry/action-release/blob/master/README.md
ignore_missing | https://github.com/getsentry/action-release/blob/master/README.md
ignore_empty | https://github.com/getsentry/action-release/blob/master/README.md
disable_telemetry | https://github.com/getsentry/action-release/blob/master/README.md
patch_set | https://docs.sentry.io/product/releases/associate-commits.md
author_email | https://docs.sentry.io/product/releases/associate-commits.md
BrowserSession | https://docs.sentry.io/platforms/javascript/configuration/releases.md
initialScope | https://docs.sentry.io/platforms/javascript/configuration/releases.md
httpIntegration | https://docs.sentry.io/platforms/javascript/guides/node/configuration/releases.md
auto_session_tracking | https://docs.sentry.io/platforms/python/configuration/sessions.md
releaseName | https://docs.sentry.io/platforms/apple/configuration/releases.md
enableAutoSessionTracking | https://docs.sentry.io/platforms/apple/configuration/releases.md
sessionTrackingIntervalMillis | https://docs.sentry.io/platforms/apple/configuration/releases.md
AutoSessionTracking | https://docs.sentry.io/platforms/dotnet/configuration/releases.md
distinctId | https://docs.sentry.io/platforms/java/configuration/releases.md
setRelease | https://docs.sentry.io/platforms/java/configuration/releases.md
```

## Unconfirmed
- `auto_session_tracking`: documented for Python 2.x only; the 2.x-to-3.x migration page does not mention it, so its 3.0 alpha status is unknown.
- `setCommits`: the Next.js build options page lists only `release.name`, `release.create`, `release.finalize`, `release.dist`; the commit and deploy options above come from the bundler plugin documentation source on GitHub and are assumed to pass through framework wrappers; verify per wrapper.
- Default release for JS Node servers: not stated on the Node releases page fetched.
