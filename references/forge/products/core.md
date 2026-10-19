# SDK core (product id: core)

## Fit
Always proposed when a Sentry SDK is present or the project is a runnable app (see `sentry-ctx detect`). This module audits what every
other product depends on: where `Sentry.init` runs, where the DSN comes from, `environment`, `release`, flushing, duplicate
handlers, `tunnel` and the SDK major. Not worth proposing as new work for libraries/packages that must not initialise Sentry
themselves (they should only depend on the API), and `core.dsn-region` needs org access.

## Properly configured
Majors below follow the brief dated 2026-10-20: JS `@sentry/*` 11, Python `sentry-sdk` 2.x stable and 3.0 alpha, Cocoa 9, Java/Android 8.

| Concern | Right | Source |
|---|---|---|
| Init placement, Node (JS v11) | `instrument.(js\|mjs)` holds `Sentry.init` and is loaded with `node --import ./instrument.js app.js` before app code. Bundler setups follow the "bundler" install page instead. | node guide |
| Init placement, Next.js (JS v11) | Client `instrumentation-client.ts`, server `sentry.server.config.ts`, edge `sentry.edge.config.ts`; `instrumentation.ts` imports the server/edge file by `NEXT_RUNTIME` in `register` | nextjs guide |
| Init placement, Python 2.x/3.0 | "As early as possible": in the app entry point, before the framework app object is built; Flask/Django integrations switch on from the installed package | python guide, flask page |
| Init placement, Cocoa 9 | Main thread, as early as possible, e.g. `application:didFinishLaunchingWithOptions` | ios guide |
| Init placement, Android 8 | `AndroidManifest.xml` meta-data (`io.sentry.dsn`) initialises the SDK | android guide |
| Init placement, Rails | `config/initializers/sentry.rb` | rails guide |
| DSN source | `dsn` option, or the `SENTRY_DSN` environment variable where the SDK reads one (server SDKs). Browsers have no env: the build must inline it (framework public prefix, e.g. `NEXT_PUBLIC_SENTRY_DSN`) | options pages, dsn explainer |
| DSN secrecy | A DSN only allows submitting events; it is safe to keep public, and rotated in the project's Client Keys settings. The old secret part is effectively deprecated | dsn explainer |
| `environment` | From the deploy (`SENTRY_ENVIRONMENT` or build var), never hard-coded. Default is `production` (Python, Cocoa); JS decides `development`/`production` by whether the app is packaged | options pages |
| `release` | Server JS reads `SENTRY_RELEASE`; Python reads `SENTRY_RELEASE` and otherwise tries to auto-detect; Cocoa uses `releaseName` and defaults to `CFBundleIdentifier@CFBundleShortVersionString+CFBundleVersion` | options pages, tagging |
| Flush | Short-lived process: JS `flush(timeout)` or `close(timeout)` (omitted timeout waits until everything is sent), Go `defer sentry.Flush(2 * time.Second)`; Python drains on exit unless `AtexitIntegration` is removed or `shutdown_timeout` is 0; Cocoa `SentrySDK.close()` waits `shutdownTimeInterval` (2.0) | apis, draining pages |
| Handlers | One capture path per error. Node ships `onUncaughtExceptionIntegration` by default; Python's logging integration turns ERROR records into events (`event_level`) | integration pages |
| `tunnel` | Browser: relative URL (recommended); server SDKs (`@sentry/node`, `@sentry/bun`) need an absolute URL. The handler must read the envelope header DSN and forward only known project ids on the matching host | troubleshooting page |

## Checks
| check id | read | passes when |
|---|---|---|
| core.sdk-version | `package.json` + lockfile, `pyproject.toml`/`requirements*.txt`/`uv.lock`, `Package.resolved`/`Podfile.lock`, Gradle/`go.mod`/`Gemfile.lock` | Installed major is the newest one that has a stale-API table (JS 11, Python 3.0 alpha, Cocoa 9) or the gap is written down. Any `Podfile`/`Podfile.lock` pod `Sentry` is P1 (nothing published after 9.19.1) |
| core.removed-api | Grep init files and call sites for names in `data/stale-apis/js.tsv`, `python.tsv`, `cocoa.tsv` matching the installed major | No hit. Do not re-derive: use the table's message and `source` column (JS v11 removals include `sendDefaultPii`, `enableLogs`; Python 3.0 alpha removes `send_default_pii`, `enable_tracing`) |
| core.init-placement | Node start script/Dockerfile `CMD` (`--import`), `instrumentation*.ts`, Python entry module, `AppDelegate`/`App` struct, `Application.onCreate`/manifest, `config/initializers/` | Init runs before the code it should observe; a framework or HTTP client imported before init is a miss (JS v11 cannot detect that case, see `disableInstrumentationWarnings` in the stale table) |
| core.dsn-source | Init files, `.env*`, CI/Docker env, framework public-env prefix | DSN comes from env/config per platform convention. A literal DSN is advisory only (DSNs are public). A browser DSN read from an unprefixed env var is a defect (undefined, SDK silently sends nothing) |
| core.dsn-region | `sentry-ctx doctor` (regions), DSN host in the repo, org region from the org probe | The DSN ingest host belongs to the same region as the org; the storage region of an org cannot be changed later |
| core.environment | Init option, deploy config, `SENTRY_ENVIRONMENT` | Derived from the deploy; staging/preview not reporting as `production`; value valid (no spaces, newlines or `/`, not `None`, at most 64 chars) |
| core.release | Init option, build/CI env, artifact upload step | Set; byte-identical to the string used for source maps/debug files and `release create`; Apple default kept unless the CI uses the same override |
| core.flush | Serverless handlers, CLIs, workers, `main`/`atexit`, signal handlers | Flush or close with a bounded timeout before exit on every exit path that can follow a capture |
| core.double-handlers | a hand-written Node process-level uncaught-exception or unhandled-rejection handler, `sys.excepthook`, `logger.exception` + re-raise, manual capture inside framework error hooks | At most one capture per error; a custom Node handler either does not capture or uses `exitEvenIfOtherHandlersAreRegistered` deliberately |
| core.tunnel | `tunnel` in init, the route that implements it | Unset, or relative URL in browsers and a handler that validates DSN host and project id, not an open relay |

## Common mistakes
| Symptom | Cause | Fix |
|---|---|---|
| No framework spans, partial errors on Node | `Sentry.init` imported at the top of the app file, after framework imports | Move to `instrument.(js\|mjs)` and `node --import` (JS v11 removed the loader registration and warnings, stale table) |
| No events from the browser, no console output | DSN env var has no public prefix so the bundle gets `undefined` | Inline via the framework prefix; set `debug` to see why (troubleshooting page) |
| Staging errors under `production` | `environment` unset (default `production`) or copied constant | Read from deploy env |
| Issues "unknown release" or regressions never detected | SDK `release` differs from the upload (`git rev-parse` vs package version) | One variable feeds both |
| Lambda/worker loses the last events | No flush before the runtime freezes | `flush(timeout)` before return |
| Every error appears twice | Own uncaught-exception handler or `logger.exception` plus `capture_exception` | Remove one path |
| New groups and errored sessions after bumping to JS v11 | `captureMessage` and non-Error `captureException` now attach a synthetic stack (`attachStacktrace` default) | Expected; set `attachStacktrace` to false only knowingly |
| Ad-blocked browser events after adding `tunnel` | Handler forwards any envelope to any host | Validate host and known project ids |

## Volume, cost and overhead
Core itself bills nothing; errors are billed by the errors category, so the cost lever here is duplication (double handlers
double event count) and wrong environment/release attribution (not recoverable after the fact). Init cost is paid at startup;
`flush`/`close` waits and `shutdown_timeout` block process exit and serverless duration, so keep timeouts to seconds (Python default
is 2 and the docs warn a high value blocks users with poor connectivity). A `tunnel` moves ingest traffic onto your own server.

## Verify (R6)
- Emit a marked event from the real entry path (not a standalone script), then `sentry event view <org>/<project>/<event-id> --json`:
  confirm `environment`, `release`, `sdk.version` and, for the framework path, request data or the framework integration tags.
- Flush: trigger the capture in the short-lived process and confirm the event arrived without a sleep.
- Duplicates: one trigger, count events with the marker tag via `sentry issue list <org>/<project> -q 'is:unresolved' --json`; expect 1.
- Region: `sentry-ctx doctor` regions line against the DSN host.
- Tunnel: send a marker through the route and a request with a foreign project id; the second must be rejected.

## Sources
- https://docs.sentry.io/platforms/javascript/configuration/options/
- https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
- https://docs.sentry.io/platforms/javascript/guides/node/
- https://docs.sentry.io/platforms/javascript/guides/nextjs/
- https://docs.sentry.io/platforms/javascript/troubleshooting/
- https://docs.sentry.io/platforms/javascript/migration/v10-to-v11/
- https://docs.sentry.io/platforms/python/configuration/options/
- https://docs.sentry.io/platforms/python/configuration/draining/
- https://docs.sentry.io/platforms/python/migration/2.x-to-3.x/
- https://docs.sentry.io/platforms/apple/guides/ios/configuration/options/
- https://docs.sentry.io/platforms/apple/guides/ios/install/cocoapods/
- https://docs.sentry.io/concepts/key-terms/dsn-explainer/
- https://docs.sentry.io/organization/data-storage-location/
- references/upstream/releases/tagging, references/upstream/first-error-setup

## Identifiers
```identifiers
dsn | https://docs.sentry.io/platforms/javascript/configuration/options.md
environment | https://docs.sentry.io/platforms/javascript/configuration/options.md
release | https://docs.sentry.io/platforms/javascript/configuration/options.md
tunnel | https://docs.sentry.io/platforms/javascript/configuration/options.md
capture_exception | https://docs.sentry.io/platforms/python/usage.md
captureMessage | https://docs.sentry.io/platforms/javascript/guides/node/configuration/apis.md
attachStacktrace | https://docs.sentry.io/platforms/javascript/migration/v10-to-v11.md
SENTRY_RELEASE | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options.md
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/javascript/guides/node/configuration/options.md
shutdown_timeout | https://docs.sentry.io/platforms/python/configuration/options.md
AtexitIntegration | https://docs.sentry.io/platforms/python/configuration/draining.md
event_level | https://docs.sentry.io/platforms/python/integrations/logging.md
releaseName | https://docs.sentry.io/platforms/apple/guides/ios/configuration/options.md
shutdownTimeInterval | https://docs.sentry.io/platforms/apple/guides/ios/configuration/options.md
onUncaughtExceptionIntegration | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/onuncaughtexception.md
exitEvenIfOtherHandlersAreRegistered | https://docs.sentry.io/platforms/javascript/guides/node/configuration/integrations/onuncaughtexception.md
```

## Unconfirmed
- Go "init at the top of `main`" and Ruby/PHP/.NET init placement beyond Rails were not fetched; verify on the platform page before asserting.
- That a custom Node uncaught-exception handler which also calls `captureException` duplicates events is an inference from the integration page, not a stated behaviour.
