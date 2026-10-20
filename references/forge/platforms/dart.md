# Dart (module: platforms/dart)

Applies to the pure Dart `sentry` package, 10.x (current 10.1.0, checked 2026-10-20), for server and CLI code. Flutter apps (`sentry_flutter`, a `flutter` SDK dependency) belong to `platforms/flutter`; this module covers Flutter only where the artifact path is shared.

## Detect

| Signal | Where | Means |
|---|---|---|
| `sentry` dependency | `pubspec.yaml`, `pubspec.lock` | pure Dart SDK installed; the lockfile gives the real major |
| `flutter` SDK dependency | `pubspec.yaml` | Flutter app: engine resolves framework `flutter` (fixture: `pubspec.yaml:deps:flutter`); not this module |
| `Sentry.init(` | `bin/*.dart`, `lib/**/*.dart` | the init site; `SentryFlutter.init(` is the Flutter one |
| `sentry_dart_plugin`, `sentry:` block | `pubspec.yaml`, `sentry.properties` | Flutter-only symbol upload; see Gotchas |

Engine entry: `data/detect/frameworks.json`, id `dart` (ecosystem `dart`, role `unknown`, docs_platform `dart`, module `platforms/dart`). Read every init file the engine reports as an init site.

## Install route

Manual. The Dart platform page documents no wizard for pure Dart. The wizard's Flutter integration (`npx @sentry/wizard@latest -i flutter`, Flutter guide) is audited by the Flutter module. For pure Dart, add `sentry: ^10.1.0` under `dependencies` in `pubspec.yaml`, then follow the page: `sentry-ctx docs page platforms/dart --section "Install"`, and `--section "Initialize the Sentry SDK"`.

## Init placement

- The docs say configure "as early as possible" in the entry point: `await Sentry.init((options) { ... })` as the first statement of `Future<void> main() async`.
- A CLI with several entry points (`bin/*.dart`) needs one init per process, not per command or per library.
- Init in a helper library, in a request handler, or after startup code that can throw is a finding.
- Process exit: the platform page documents no flush or close call (see Unconfirmed). Check that a short-lived process still delivers its event.

## Options by SDK major

The fetched pages describe the current major. The v9 column is filled only where a fetched page states it.

| option | v9.x | v10.x (current) | note |
|---|---|---|---|
| `dsn` | not stated | env `SENTRY_DSN`; none set means no events are sent | silent no-op without a DSN |
| `sendDefaultPii` | not stated | default `false` | the Initialize sample sets it to `true` |
| `sampleRate` | not stated | default `1.0` | error sampling; runs after `beforeSend` |
| `tracesSampleRate` | not stated | no default; this or `tracesSampler` must be set to enable tracing | the Initialize sample sets `1.0` |
| `tracesSampler` | not stated | function; in stream mode reads `samplingContext.spanContext` | |
| `traceLifecycle` | available since 9.23.0 | default `stream` (since 10.0.0); `SentryTraceLifecycle.static` = transaction mode | |
| `environment` | not stated | env `SENTRY_ENVIRONMENT`; not set by default | freeform string |
| `release` | not stated | env `SENTRY_RELEASE` | see Release and artifacts |
| `dist` | not stated | max 64 characters; env `SENTRY_DIST` (Initialize comment) | |
| `debug` | not stated | default `false` | |

## Product support matrix

| product | supported | notes |
|---|---|---|
| Errors | yes | `Sentry.captureException` (Verify section); `sampleRate` default `1.0` |
| Tracing | yes | `traceLifecycle` default `stream`; needs `tracesSampleRate` or `tracesSampler` |
| Profiling | unconfirmed | no `platforms/dart/profiling` page; the Flutter guide has none either |
| Replay | Flutter only | `platforms/dart/guides/flutter/session-replay`, needs `sentry_flutter` 9.0.0 or later; no replay page under `platforms/dart` for pure Dart (unconfirmed) |
| Logs | yes | enabled by default; `Sentry.logger.info`, `warn`, `error` |
| Metrics | yes | enabled by default; `Sentry.metrics.count`, `gauge`, `distribution` |
| Crons | unconfirmed | no `platforms/dart/crons` page |
| User feedback | yes | `platforms/dart/user-feedback` (User Feedback API); Flutter adds the `SentryFeedbackForm` widget |
| AI monitoring | unconfirmed | no AI page under `platforms/dart` |
| Feature flags | yes | `platforms/dart/feature-flags`, section "Enable Evaluation Tracking" |

## Release and artifacts

- SDK `release`: read only from env `SENTRY_RELEASE` (options page). The page documents no git SHA or pubspec fallback for the SDK, so an unset variable means events carry no release. Set it per deploy, to the same string the artifact upload uses.
- `dist`: option or env `SENTRY_DIST`.
- Flutter plugin defaults (Configuration Reference): `release` is `name@version` from `pubspec.yaml`; `dist` is the build number after `+`. The SDK does not derive these, so both sides must be set to match.
- Pure Dart has no debug files. The platform page says Sentry does not support symbolication or debug symbol uploads for pure Dart apps (GitHub issue sentry-dart#1508). Do not propose a symbol step for server or CLI code.
- Flutter mobile and desktop: `flutter build <target> --obfuscate --split-debug-info=<dir> --extra-gen-snapshot-options=--save-obfuscation-map=build/app/obfuscation.map.json`, then `flutter pub run sentry_dart_plugin`. Build and upload in the same CI job, in that order. `dart_symbol_map_path` in the `sentry:` block makes obfuscated iOS and Android issue titles readable.
- Flutter web: `flutter build web --release --source-maps`, then the plugin with `upload_source_maps: true`.
- Source context: `upload_sources` defaults to `false`; iOS and Android source context needs `--split-debug-info`.
- Auth: `SENTRY_AUTH_TOKEN` from the environment, never committed. `auth_token` exists as a key but the env var is preferred.
- Plugin keys and defaults: `upload_debug_symbols` true, `symbols_path` `.`, `build_path` `build`, `commits` `auto`. Config lives in the `sentry:` block of `pubspec.yaml` or in `sentry.properties`.

## Privacy

| Data | Default | Control |
|---|---|---|
| User identity, IP, request headers added by integrations | off (`sendDefaultPii` is `false`) | `sendDefaultPii`; if turned on, remove unwanted fields with Sensitive Data (`platforms/dart/data-management/sensitive-data`, linked from the option entry, not fetched) |
| Source context and source code | `upload_sources` `false` (Flutter plugin) | plugin keys |
| Log and metric attributes | sent as the app calls `Sentry.logger` or `Sentry.metrics` | review call sites: no secrets in messages or attributes |
| Event content | `beforeSend` runs before sampling | filter or scrub in `beforeSend` |

## Verify recipe

1. In the real server or CLI entry path, add a temporary route or subcommand that throws a marked error and captures it with the same `Sentry.init` settings:
   `try { throw StateError('sentry-verify-<token>'); } catch (e, s) { await Sentry.captureException(e, stackTrace: s); }`
2. Run the process with `SENTRY_DSN` set to the project DSN, `SENTRY_ENVIRONMENT=verify`, and `SENTRY_RELEASE` set to the release under audit.
3. Trigger the route or subcommand once. Expect an issue whose title contains `sentry-verify-<token>` with environment `verify` and the release string. Product proof: `Sentry.logger.info('sentry-verify-<token>')` on the Logs page and `Sentry.metrics.count('sentry.verify', 1)` on the Application Metrics page (Verify section).
4. Remove: delete the route or subcommand and its imports; `grep -rn "sentry-verify" bin lib` must print nothing; unset the three env vars. Do not leave the marker in the repo.

For Flutter, use the verify recipe in `platforms/flutter`.

## Gotchas

1. The Initialize sample sets `sendDefaultPii = true` and `tracesSampleRate = 1.0`, and says to adjust the rate in production. Copy-paste ships PII and full tracing. Right: explicit values per environment (platforms/dart Initialize).
2. Config from the environment vs `--dart-define`: the Initialize comment says `SENTRY_DSN`, `SENTRY_RELEASE`, `SENTRY_DIST`, `SENTRY_ENVIRONMENT` are set "via Dart environment variable (--dart-define)", while the options tables name them as process environment variables. The pages do not say which a pure Dart process reads. Decide by the verify event (see Unconfirmed).
3. Pure Dart cannot be symbolicated (debug-symbols page). A missing symbol step in a server repo is not a finding.
4. Release mismatch: the SDK reads only `SENTRY_RELEASE`; the plugin defaults to `name@version` from `pubspec.yaml`. Events and artifacts land in different releases unless both are set to the same string.
5. `traceLifecycle` defaults to `stream` since 10.0.0. In stream mode `tracesSampler` reads `samplingContext.spanContext`, not transaction fields. Code written for `SentryTraceLifecycle.static` reads the wrong context.
6. Logs and metrics are enabled by default (Verify section). There is no opt-in gate, so volume is decided by call sites: audit `Sentry.logger` calls inside loops and request paths.
7. Replay, the feedback widget and the Flutter plugin are Flutter pages. A pure Dart app gets none of them from this module.
8. A missing page is unknown, not absent: `platforms/dart` has no profiling, crons or AI page. The matrix marks these unconfirmed, not no.

## Sources

- https://docs.sentry.io/platforms/dart/
- https://docs.sentry.io/platforms/dart/configuration/options/
- https://docs.sentry.io/platforms/dart/debug-symbols/
- https://docs.sentry.io/platforms/dart/guides/flutter/
- https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/
- https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
- https://docs.sentry.io/platforms/dart/guides/flutter/session-replay/
- https://docs.sentry.io/platforms/dart/guides/flutter/user-feedback/
- https://docs.sentry.io/platforms/dart/user-feedback/
- https://docs.sentry.io/platforms/dart/feature-flags/

## Identifiers

```identifiers
Sentry.init | https://docs.sentry.io/platforms/dart/
Sentry.captureException | https://docs.sentry.io/platforms/dart/
StateError | https://docs.sentry.io/platforms/dart/
stackTrace | https://docs.sentry.io/platforms/dart/
Sentry.logger.info | https://docs.sentry.io/platforms/dart/
Sentry.metrics.count | https://docs.sentry.io/platforms/dart/
SENTRY_DIST | https://docs.sentry.io/platforms/dart/
SENTRY_DSN | https://docs.sentry.io/platforms/dart/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/dart/configuration/options/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/dart/configuration/options/
sendDefaultPii | https://docs.sentry.io/platforms/dart/configuration/options/
sampleRate | https://docs.sentry.io/platforms/dart/configuration/options/
tracesSampleRate | https://docs.sentry.io/platforms/dart/configuration/options/
tracesSampler | https://docs.sentry.io/platforms/dart/configuration/options/
samplingContext.spanContext | https://docs.sentry.io/platforms/dart/configuration/options/
traceLifecycle | https://docs.sentry.io/platforms/dart/configuration/options/
SentryTraceLifecycle.static | https://docs.sentry.io/platforms/dart/configuration/options/
beforeSend | https://docs.sentry.io/platforms/dart/configuration/options/
SentryFlutter.init | https://docs.sentry.io/platforms/dart/guides/flutter/
sentry_flutter | https://docs.sentry.io/platforms/dart/guides/flutter/
SentryFeedbackForm | https://docs.sentry.io/platforms/dart/guides/flutter/user-feedback/
sentry_dart_plugin | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
auth_token | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
upload_debug_symbols | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
upload_sources | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
upload_source_maps | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
dart_symbol_map_path | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
symbols_path | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
build_path | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
commits | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
--split-debug-info | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
--obfuscate | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
--save-obfuscation-map | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
```

## Unconfirmed
- `Sentry.close`: no flush or close call on platforms/dart (grep of the page for close, flush, shutdown found none) on 2026-10-20; verify before recommending exit handling.
- Mapping of `SENTRY_DSN`, `SENTRY_RELEASE`, `SENTRY_DIST`, `SENTRY_ENVIRONMENT` through `--dart-define` vs process environment for a pure Dart process: the pages disagree in wording and do not settle it on 2026-10-20.
- Replay, profiling, crons and AI monitoring for pure Dart: no page under platforms/dart on 2026-10-20.
