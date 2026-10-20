# Spotlight (local development) (product id: dev-spotlight)

## Fit
Propose only when the repo has a local run path for a web app, API or worker, and a Sentry SDK is already initialized in the code that run path starts. Applicability rule (`data/signals.tsv`): conditional, foundation tier, roles frontend, backend, fullstack, worker; skip when there is no local web/server workflow to attach to.

Worth proposing when all of these hold:

| Evidence | Where to look | Why it matters |
|---|---|---|
| A local dev command for a web app, API or worker | a `dev` or `start` script in `package.json`; `manage.py runserver`; `uvicorn --reload`; `flask run`; a dev service in `docker-compose*.yml`; a `Makefile` or `Procfile` target | Spotlight is a local sidecar; it needs a running process to receive events from |
| Sentry SDK initialized in that code | `sentry_sdk.init(` in Python; `Sentry.init(` or an `@sentry/*` import in JS | Spotlight only shows what the SDK sends; with no SDK there is nothing to show |
| Role is frontend, backend, fullstack or worker | role tags from the detection engine | Matches the applicability rule |

NOT worth proposing when:
- No local web/server workflow: a library, a package with no runnable app, an infra-only repo, or a one-shot script with no long-running process.
- No Sentry SDK in the repo. Propose SDK setup first; Spotlight comes after it.
- The only goal is production error tracking. Spotlight is a development tool; production routing belongs to other modules.
- Spotlight is already enabled in a production or CI deploy config. That is a `dev.spotlight` finding to fix, not a reason to add more.

## Properly configured
Development only. Turn Spotlight on from a dev-only path (a dev script, a dev env file, or a branch that runs only locally) and keep it off in every deploy config. The README says Spotlight works "alongside your existing Sentry setup without interference", so the guard belongs on Spotlight; the DSN alone decides whether events also reach Sentry.

Python (`sentry-sdk`), per the Python options page:

| Setting | Dev | Production | Note |
|---|---|---|---|
| `spotlight` init argument, or `SENTRY_SPOTLIGHT` | `True` (default URL http://localhost:8969/stream), or a URL string for the sidecar | unset (default `None`) | `True` uses the default URL; a string names the URL Spotlight runs on |
| `environment`, or `SENTRY_ENVIRONMENT` | set explicitly to a non-production value | the deployed environment name | Default is `production` when unset |
| `dsn`, or `SENTRY_DSN` | unset for Spotlight-only runs; set only when dev events should reach a Sentry project | the project DSN | "If this option is not set, the SDK will just not send any data" |

JS family (Browser, Node, Next.js): none of the fetched official options pages names a Spotlight option. The option name and its placement are Unconfirmed (see the list at the end). Gate it by the dev path the repo already has; do not assume an option name.

Other platforms: no Spotlight page was fetched. Do not propose Spotlight settings for them without a docs page.

Coverage gap: docs.sentry.io has no Spotlight page at the paths tried for JS, Node, Next.js and Python (`platforms/javascript/guides/node/spotlight`, `platforms/javascript/guides/nextjs/spotlight`, `platforms/python/spotlight`). `product/sentry-basics/integrate-backend/spotlight` serves the Getting Started Tutorial instead. Spotlight's own docs are on spotlightjs.com, which is outside the fetch allowlist.

Sampling, release and PII: no Spotlight-specific setting is stated on the fetched pages; the normal SDK settings for the dev environment apply.

## Checks
| check id | read | passes when |
|---|---|---|
| dev.spotlight | `grep -rn "spotlight\|SENTRY_SPOTLIGHT"` over source, `.env*`, `Dockerfile*`, `docker-compose*.yml`, CI workflows and deploy manifests; then the condition around each Python `spotlight` argument (environment check, dev-only branch, dev-only env file) | Spotlight is enabled only on a development path, and no production or CI deploy config sets `SENTRY_SPOTLIGHT` or a `spotlight` argument. Unconditional enablement, or a value set in a production config, is a finding. |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Spotlight on in a production build or container | `spotlight` or `SENTRY_SPOTLIGHT` set unconditionally, or set in a shared env file | Move it behind a dev-only path and remove it from deploy config (`dev.spotlight`) | Python options page, `spotlight` |
| Dev events show as `production` in Sentry | `environment` not set; the Python default is `production` | Set `environment` / `SENTRY_ENVIRONMENT` to a non-production value in dev | Python options page, `environment` |
| Dev errors land in a production Sentry project | DSN set in the env file used for dev | Use a dev DSN, or unset the DSN for Spotlight-only runs | Python options page, `dsn` |
| Spotlight UI or `spotlight tail` shows nothing | Sidecar not running, or the app started without the Spotlight setting | Start `npx @spotlightjs/spotlight` first, or launch the app with `spotlight run <command>`, which configures it | GitHub README |
| `spotlight` in JS code treated as documented | No fetched JS page names it | Mark it Unconfirmed; check the SDK's own options page before relying on it | Unconfirmed list |

## Volume, cost and overhead
- Quota: no quota category or price for Spotlight is stated on the fetched pages. Events the SDK also sends to Sentry (DSN set) count under that project's normal quota; see the quota module.
- Runtime: Spotlight runs a local proxy (the sidecar) on the developer machine. The README gives no overhead figures.
- Budget: nothing fetched says Spotlight needs a pay-as-you-go budget. Budget only the DSN path, if it is used.

## Verify (R6)
1. Start the sidecar: `npx @spotlightjs/spotlight` (default mode serves the web UI). In a second terminal, run `npx @spotlightjs/spotlight tail errors`.
2. Run the app on the dev path with Spotlight enabled. Trigger one marked exception from a dev-only route, for example `RuntimeError("spotlight-verify")`.
3. Expect the marked message in the `tail errors` output or the Spotlight UI.
4. Remove the trigger. Then check deploy config for a Spotlight setting: `grep -rn "SENTRY_SPOTLIGHT\|spotlight=" <deploy dirs>` should return no production hit.

## Sources
- https://docs.sentry.io/platforms/python/configuration/options/ (`spotlight`, `SENTRY_SPOTLIGHT`, `dsn`, `SENTRY_DSN`, `environment`, `SENTRY_ENVIRONMENT`)
- https://github.com/getsentry/spotlight/blob/main/README.md (CLI modes `spotlight tail`, `spotlight run`, `spotlight mcp`; sidecar; "alongside your existing Sentry setup")

## Identifiers
```identifiers
spotlight | https://docs.sentry.io/platforms/python/configuration/options/
SENTRY_SPOTLIGHT | https://docs.sentry.io/platforms/python/configuration/options/
dsn | https://docs.sentry.io/platforms/python/configuration/options/
SENTRY_DSN | https://docs.sentry.io/platforms/python/configuration/options/
environment | https://docs.sentry.io/platforms/python/configuration/options/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/python/configuration/options/
spotlight run | https://github.com/getsentry/spotlight/blob/main/README.md
spotlight tail | https://github.com/getsentry/spotlight/blob/main/README.md
spotlight mcp | https://github.com/getsentry/spotlight/blob/main/README.md
@spotlightjs/spotlight | https://github.com/getsentry/spotlight/blob/main/README.md
```

## Unconfirmed
- `spotlight` as a JS, Node or Next.js SDK init option: not in the Browser, Node or Next.js options pages fetched 2026-10-20; verify before use.
- `@spotlightjs/spotlight` 4.12: the version comes from research notes only; no fetched page states it (2026-10-20).
- spotlightjs.com sidecar and configuration docs: outside the fetch allowlist; sidecar port override and UI URL are unverified beyond the README and the Python option text (2026-10-20).
- Spotlight on any non-Python platform: no official page fetched (2026-10-20).
