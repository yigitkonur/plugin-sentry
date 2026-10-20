# Java and Kotlin (JVM) (module: platforms/jvm)

Sentry Java SDK 8.x (`io.sentry:sentry`; 8.61.0 in the docs install snippets). Serves plain JVM apps and the framework ids `jvm`, `ktor`, `micronaut`, `quarkus`, which fall back here. Spring and Spring Boot have their own module (`platforms/spring-boot`). Kotlin uses the same SDK; the docs show a Kotlin variant of each snippet.

## Detect

| Signal | Where | Means |
|---|---|---|
| `io.sentry:sentry*` coordinates | `pom.xml`, `build.gradle(.kts)`, `settings.gradle(.kts)`, `gradle/libs.versions.toml`, `gradle.lockfile` | SDK present; the pinned version gives the major (8.x is current) |
| `io.sentry.jvm.gradle` plugin | `build.gradle(.kts)` | Gradle plugin: integrations and source bundle upload |
| `sentry-maven-plugin` | `pom.xml` | Maven plugin: SDK auto-install, source bundle upload, SDK version check |
| `Sentry.init(` | `*.java`, `*.kt` | the init site (see Init placement) |
| `dsn=` | `sentry.properties` | file-based config; plain JVM keys are kebab-case |
| `SentryAppender` | `logback.xml`, `log4j2.xml` | logging integration |
| `com.getsentry.raven` | manifests | legacy raven client, not this SDK: report |

The `spring-boot` fixture (`evals/fixtures/spring-boot`: `build.gradle.kts` with `org.springframework.boot`) detects as framework `spring-boot` with module `platforms/spring-boot`, so it is not audited with this file. Framework ids `ktor`, `micronaut`, `quarkus` have no docs page of their own (see Gotchas).

## Install route

- No wizard for `jvm`: the `jvm` entry in `data/detect/frameworks.json` has docs_platform java, module `platforms/jvm`, and no wizard id. Install manually from the live page: docs path `platforms/java`, section Install.
- Docs-preferred route: the Gradle plugin `io.sentry.jvm.gradle` (6.24.0 in the snippet) or the Maven plugin `sentry-maven-plugin` 0.11.0 with `<extensions>true</extensions>`. Both add integrations and source context.
- Without a build plugin: `io.sentry:sentry` 8.61.0 plus a BOM (docs path `platforms/java/configuration/bill-of-materials`) so all `io.sentry` artifacts share one version.
- Logging integrations: `platforms/java/guides/logback`, `platforms/java/guides/log4j2`, `platforms/java/guides/jul`.
- Options: `platforms/java/configuration/options`.

## Init placement

| Where | Rule | Evidence |
|---|---|---|
| Application entry (`main` or the startup class) | `Sentry.init(options -> { ... })`, "as early as possible in your application's lifecycle" | `platforms/java`, section Configure |
| `sentry.properties` on the classpath or path the SDK reads | same options as kebab-case keys: `dsn`, `data-collection.user-info`, `traces-sample-rate`, `profile-session-sample-rate`, `profile-lifecycle`, `logs.enabled` | `platforms/java` Configure; search-path rules not fetched (Unconfirmed) |
| `logback.xml` / `log4j2.xml` | `SentryAppender` on the root logger, with its own thresholds | logback and log4j2 guides |

## Options by SDK major

| option | 7.x (N-1) | 8.x (N, 8.61.0) | note |
|---|---|---|---|
| `dataCollection` | not available | since 8.58.0 | once any field is set, `sendDefaultPii` is ignored (Privacy) |
| `sendDefaultPii` | not checked | default `false`; deprecated | "will be removed in the next major version (v9)" |
| `release` | not checked | string; env `SENTRY_RELEASE` | docs: set it explicitly |
| `environment` | not checked | listed; default not fetched | set per deploy |
| `tracesSampleRate` | not checked | number 0 to 1 | uniform sampling |
| `tracesSampler` | not checked | function | wins if both are set (tracing page) |
| `profileSessionSampleRate` | not checked | continuous profiling | needs tracing for `trace` lifecycle |
| `profileLifecycle` | not checked | `manual` or `trace` | `manual` works without tracing |
| `logs.enabled` | not in 7.x (logs need SDK 8.12.0+) | required for logging integrations | direct `Sentry.logger` calls need no flag since 8.59.0 |

## Product support matrix

| product | supported | notes |
|---|---|---|
| errors | yes | `Sentry.captureException` (Verify snippet) |
| tracing | yes, SDK 4.0+ | `tracesSampleRate` or `tracesSampler`; Spring integrations link errors to spans |
| profiling | yes, continuous, SDK 8.23+ (matrix) | macOS and Linux only; needs `sentry-async-profiler`; `manual` mode via `Sentry.startProfiler` and `Sentry.stopProfiler` |
| replay | no | matrix shows no Java replay; no `platforms/java/session-replay` page exists |
| logs | yes, SDK 8.12.0+ | `logs.enabled`, `beforeSendLog`; Logback and Log4j2 `minimumLevel` default INFO |
| metrics | yes, SDK 8.34.0+ | `platforms/java/metrics` |
| crons | yes | `CheckInUtils.withCheckIn` with `MonitorConfig` upserts the monitor; manual check-ins also documented |
| feedback | yes | `platforms/java/user-feedback` (User Feedback API) |
| ai | unconfirmed | matrix says manual instrumentation; no Java AI page found |
| flags | yes, SDK 8.42.0+ | `platforms/java/feature-flags`; beta at product level per matrix |
| debug files | yes, as JVM source bundles | not native symbols; see Release and artifacts |

## Release and artifacts

- Release string: the SDK reads env `SENTRY_RELEASE` by default. The docs say set `release` explicitly so it matches deploy integrations and source uploads. No git-derived default is stated for Java (Unconfirmed).
- JVM has no source maps. Source context comes from a source bundle (`--type jvm`) matched to the event by a debug ID (UUID).
- Gradle: `io.sentry.jvm.gradle` with `includeSourceContext = true` (disabled by default); the build must run `assemble`; token from env `SENTRY_AUTH_TOKEN`. Maven: `sentry-maven-plugin` goals `uploadSourceBundle` and `validateSdkDependencyVersions`; token from env, not committed.
- Manual route (the docs' own commands):

```bash
sentry-cli debug-files bundle-jvm --output <bundle-dir> --debug-id <UUID> <project-root>
sentry-cli debug-files upload --type jvm <bundle-dir>
```

- The SDK must know the same UUID: `io.sentry.bundle-ids=<UUID>` in `sentry-debug-meta.properties` (resources), `bundle-ids=<UUID>` in `sentry.properties`, or `options.addBundleId("<UUID>")`.
- Right looks like: the CI step runs the plugin goal or both CLI commands after the build; the UUID is generated per build and written where the SDK reads it; `SENTRY_AUTH_TOKEN` comes from CI secrets.

## Privacy

| Data | Default | Control |
|---|---|---|
| user id, IP | not sent (`sendDefaultPii` default `false`) | `dataCollection.userInfo`; default `true` once Data Collection is on |
| cookies, request/response headers, query params | `DENY_LIST`: built-in sensitive terms (token, secret, password, key, session, ...) filtered | `cookies`, `httpHeaders.request`, `httpHeaders.response`, `urlQueryParams`; `OFF` disables |
| HTTP bodies | all body types once Data Collection is on | `httpBodies`; empty set disables |
| file names, absolute paths (File I/O) | `filePaths` `true` once Data Collection is on | `setFilePaths(false)` |
| unencoded Logback messages | not part of Data Collection | Logback `includeUnencodedMessage` |

## Verify recipe

1. Add a temporary route or branch on the app's real request or job path, not the docs' standalone try/catch snippet. It should call `logger.error("sentry-verify <marker>")` through the app's own logger (Logback or Log4j2 with `SentryAppender`), or `Sentry.captureException(new Exception("sentry-verify <marker>"))` from the same code.
2. Trigger it through the real path (for example `curl` the temporary route), then search Issues for `sentry-verify <marker>`.
3. For source context, check that the top in-app frame shows source lines after the bundle upload (Project Settings > Debug Files, search by the debug ID).
4. Remove: delete the route or branch and the log line, rebuild, and confirm `grep -r "sentry-verify" src` returns nothing.

## Gotchas

- Data Collection trap: setting any `dataCollection` field, or calling `forceDataCollection()`, makes `sendDefaultPii` stop controlling those categories. The defaults then include `userInfo` `true`, `filePaths` `true` and all HTTP bodies. Source: options page, dataCollection.
- `sendDefaultPii` migration: the legacy header filter missed `X-Forwarded-For`, `X-Real-IP` and `Remote-Addr`. Add the terms `forwarded`, `-ip`, `remote-`, `via`, `-user` to the deny lists to keep filtering them. Source: options page, sendDefaultPii.
- `tracesSampler` takes precedence over `tracesSampleRate` if both are set. Source: tracing page.
- Logback and Log4j2 thresholds: event default ERROR, breadcrumb default INFO, log default INFO. `SentryAppender` must receive the lower-level entries, so its own level must sit below the breadcrumb and event levels. Thresholds only apply to logger calls; `Sentry.captureMessage` ignores them. Source: logback and log4j2 guides.
- Source context UUID: the bundle and upload must share one UUID, and the SDK must be told the same one. Known limitations: `MainActivity.java` and `MainActivity.kt` both map to `.jvm` (undefined behaviour); the package declaration must match the directory tree. Source: source-context page.
- Mixed SDK versions: the Maven plugin's `validateSdkDependencyVersions` fails the build; use a BOM instead of pinning each `io.sentry` artifact. Source: java page, Install.
- Profiling: macOS and Linux only; `trace` lifecycle requires tracing enabled. Source: profiling page.
- OpenTelemetry: the Install section says to add `sentry-opentelemetry-agent` to the `java` command at run time. The page does not say how this combines with `Sentry.init` (Unconfirmed).
- Framework ids without a docs page: `platforms/java/guides/ktor`, `.../micronaut` and `.../quarkus` return "Page Not Found". The Java frameworks list names only java.util.logging, Log4j 2.x, Logback, Servlet, Spring and Spring Boot. For those three ids, audit the framework's own entry point plus this file.

## Sources
- https://docs.sentry.io/platforms/java/
- https://docs.sentry.io/platforms/java/configuration/options/
- https://docs.sentry.io/platforms/java/configuration/bill-of-materials/
- https://docs.sentry.io/platforms/java/source-context/
- https://docs.sentry.io/platforms/java/guides/logback/
- https://docs.sentry.io/platforms/java/guides/log4j2/
- https://docs.sentry.io/platforms/java/tracing/
- https://docs.sentry.io/platforms/java/profiling/
- https://docs.sentry.io/platforms/java/logs/
- https://docs.sentry.io/platforms/java/metrics/
- https://docs.sentry.io/platforms/java/crons/
- https://docs.sentry.io/platforms/java/feature-flags/
- https://docs.sentry.io/platforms/java/user-feedback/

## Identifiers
```identifiers
Sentry.init | https://docs.sentry.io/platforms/java/
io.sentry:sentry | https://docs.sentry.io/platforms/java/
io.sentry.jvm.gradle | https://docs.sentry.io/platforms/java/
sentry-maven-plugin | https://docs.sentry.io/platforms/java/
uploadSourceBundle | https://docs.sentry.io/platforms/java/
validateSdkDependencyVersions | https://docs.sentry.io/platforms/java/
sentry-opentelemetry-agent | https://docs.sentry.io/platforms/java/
sentry-async-profiler | https://docs.sentry.io/platforms/java/
sentry.properties | https://docs.sentry.io/platforms/java/
data-collection.user-info | https://docs.sentry.io/platforms/java/
traces-sample-rate | https://docs.sentry.io/platforms/java/
profile-session-sample-rate | https://docs.sentry.io/platforms/java/
profile-lifecycle | https://docs.sentry.io/platforms/java/
dataCollection | https://docs.sentry.io/platforms/java/configuration/options/
forceDataCollection | https://docs.sentry.io/platforms/java/configuration/options/
sendDefaultPii | https://docs.sentry.io/platforms/java/configuration/options/
userInfo | https://docs.sentry.io/platforms/java/configuration/options/
setUserInfo | https://docs.sentry.io/platforms/java/configuration/options/
filePaths | https://docs.sentry.io/platforms/java/configuration/options/
setFilePaths | https://docs.sentry.io/platforms/java/configuration/options/
httpHeaders.request | https://docs.sentry.io/platforms/java/configuration/options/
httpBodies | https://docs.sentry.io/platforms/java/configuration/options/
urlQueryParams | https://docs.sentry.io/platforms/java/configuration/options/
cookies | https://docs.sentry.io/platforms/java/configuration/options/
DENY_LIST | https://docs.sentry.io/platforms/java/configuration/options/
includeUnencodedMessage | https://docs.sentry.io/platforms/java/configuration/options/
X-Forwarded-For | https://docs.sentry.io/platforms/java/configuration/options/
Remote-Addr | https://docs.sentry.io/platforms/java/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/java/configuration/options/
tracesSampleRate | https://docs.sentry.io/platforms/java/configuration/options/
tracesSampler | https://docs.sentry.io/platforms/java/configuration/options/
profileSessionSampleRate | https://docs.sentry.io/platforms/java/configuration/options/
profileLifecycle | https://docs.sentry.io/platforms/java/configuration/options/
beforeSend | https://docs.sentry.io/platforms/java/configuration/options/
beforeSendTransaction | https://docs.sentry.io/platforms/java/configuration/options/
beforeBreadcrumb | https://docs.sentry.io/platforms/java/configuration/options/
onDiscard | https://docs.sentry.io/platforms/java/configuration/options/
environment | https://docs.sentry.io/platforms/java/configuration/options/
dsn | https://docs.sentry.io/platforms/java/configuration/options/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/java/source-context/
SENTRY_PROPERTIES | https://docs.sentry.io/platforms/java/source-context/
sentry-cli | https://docs.sentry.io/platforms/java/source-context/
sentry-debug-meta.properties | https://docs.sentry.io/platforms/java/source-context/
io.sentry.bundle-ids | https://docs.sentry.io/platforms/java/source-context/
bundle-ids | https://docs.sentry.io/platforms/java/source-context/
addBundleId | https://docs.sentry.io/platforms/java/source-context/
includeSourceContext | https://docs.sentry.io/platforms/java/source-context/
SentryAppender | https://docs.sentry.io/platforms/java/guides/logback/
minimumEventLevel | https://docs.sentry.io/platforms/java/guides/logback/
minimumBreadcrumbLevel | https://docs.sentry.io/platforms/java/guides/logback/
minimumLevel | https://docs.sentry.io/platforms/java/guides/logback/
Sentry.captureMessage | https://docs.sentry.io/platforms/java/guides/logback/
Sentry.captureException | https://docs.sentry.io/platforms/java/
Sentry.startProfiler | https://docs.sentry.io/platforms/java/profiling/
Sentry.stopProfiler | https://docs.sentry.io/platforms/java/profiling/
CheckInUtils.withCheckIn | https://docs.sentry.io/platforms/java/crons/
MonitorConfig | https://docs.sentry.io/platforms/java/crons/
logs.enabled | https://docs.sentry.io/platforms/java/logs/
Sentry.logger | https://docs.sentry.io/platforms/java/logs/
beforeSendLog | https://docs.sentry.io/platforms/java/logs/
```

## Unconfirmed
- `SENTRY_AUTO_INIT`: appears in a research note for the OpenTelemetry agent; not on any Java page fetched on 2026-10-20. Verify before use.
- Git-derived release default for Java: the options page only names env `SENTRY_RELEASE`; no fallback stated.
- Search-path rules for `sentry.properties`: the Configure section shows the keys, not where the SDK looks.
- Log4j2 `SentryAppender` with async loggers: research note only; the Log4j2 guide was checked for thresholds, not for this limitation.
- Coroutine context propagation for Kotlin: no coroutine-specific page found in the Java pages fetched.
- AI monitoring for Java: no Java AI page found (matrix says manual).
- ProGuard or R8 mapping upload for JVM builds: not checked.
- Whether the OpenTelemetry agent path still needs `Sentry.init`: the Install section does not say.
