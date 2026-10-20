# Spring Boot (module: platforms/spring-boot)

Sentry Java SDK 8.x with the Spring Boot starters (8.61.0 in the guide). Framework id `spring-boot`, role `backend`, ecosystem
`jvm`, docs platform `java/guides/spring-boot`. Plain (non-Boot) Java is a different module.

## Detect

| Signal | Where | Means |
|---|---|---|
| `org.springframework.boot` or `spring-boot*` dependency | build.gradle(.kts), pom.xml | framework `spring-boot`; the Boot version there selects the starter |
| class annotated `SpringBootApplication` or `SpringBootConfiguration` | `src/main/java/**` | app entry; its package becomes `sentry.in-app-packages` |
| `io.sentry.jvm.gradle` plugin, `sentry-maven-plugin` | build.gradle(.kts), pom.xml | build wiring for source context |
| `sentry-spring-boot-starter`, `-jakarta`, `sentry-spring-boot-4` | build files | SDK present; check it matches the Boot major |
| `sentry.dsn` | `application.properties` or `application.yml` | config present (YAML nests the same keys) |
| `sentry-opentelemetry-agent` on the `java` command | Dockerfile, scripts, Procfile | agent route (see Init placement) |

Reference fixture `evals/fixtures/spring-boot`: the engine reads Boot 3.3.5, the Gradle plugin at `build.gradle.kts:5`, and the
DSN at `application.properties:3`. Boot 3 means the `-jakarta` starter.

## Install route

- No wizard: the engine entry for `spring-boot` has the docs platform and no wizard field. Use the manual route from the live
  guide: `sentry-ctx docs page platforms/java/guides/spring-boot --section Install`, then `--section Configure`.
- Starter by Boot major: Boot 2 `sentry-spring-boot-starter`; Boot 3 `sentry-spring-boot-starter-jakarta`; Boot 4
  `sentry-spring-boot-4`. Profiling adds `sentry-async-profiler` at the same version; Logback users add `sentry-logback`.
- Recommended: Gradle plugin `io.sentry.jvm.gradle` (6.24.0 in the guide) or Maven plugin `sentry-maven-plugin` (0.11.0). Both
  add integrations and source context.
- Several artifacts: use the BOM (bill-of-materials page linked from the guide, not fetched).
- Right: one starter matching the Boot major; all Sentry artifacts on one version.

## Init placement

- No code-level init. The starter auto-configures at Spring Boot startup. Config comes from `sentry.dsn` in
  `application.properties` or `application.yml`, Java system properties, or environment variables.
- The starter must be on the runtime classpath (not `test` scope) of the process that serves requests.
- `sentry.in-app-packages` is auto-set from the package of the `SpringBootApplication` class. App code outside it shows as
  not in-app: a finding.
- Agent route: add `sentry-opentelemetry-agent` to the `java` command (`-javaagent`). Its version must match the SDK. The setup
  page says SDK 8.6.0 and later throw on `init` when they differ.
- Starter plus agent both initialising Sentry is a finding unless the disable flag is confirmed (see Unconfirmed).

## Options by SDK major

Only 8.61.0 is on the pages fetched; the v(N-1) column is not checked.

| option | 8.x (8.61.0) | v(N-1) | note |
|---|---|---|---|
| `sentry.dsn` | required | not checked | the only option the guide calls required |
| `sentry.traces-sample-rate` | example `1.0`, "adjust in production" | not checked | default not stated; flat 1.0 in prod is a finding |
| `sentry.data-collection.user-info` | example `false` | not checked | "Use Data Collection defaults but don't collect automatic user information" |
| `sentry.logs.enabled` | example `true` | not checked | Sentry Logs; off unless set |
| `sentry.profile-session-sample-rate` | example `1.0` | not checked | needs `sentry-async-profiler` on the classpath |
| `sentry.profile-lifecycle` | example `TRACE` | not checked | paired with the session rate |
| `sentry.exception-resolver-order` | example `-2147483647` | not checked | default: only unhandled exceptions are sent |
| `sentry.in-app-packages` | auto-set from the `SpringBootApplication` package | not checked | override only when app code lives elsewhere |
| `sentry.logging.minimum-event-level` | example `info` | not checked | Logback appender: level that creates events |
| `sentry.logging.minimum-breadcrumb-level` | example `debug` | not checked | Logback appender: level that creates breadcrumbs |
| `sentry.logging.minimum-level` | example `debug` | not checked | level at or above which logs become Sentry Logs (with `sentry.logs.enabled`) |
| `release` | example `my-project-name@2.3.12` | not checked | property, environment variable, or system property |

Precedence: the runtime docs check Java system properties before environment variables. The env-var rule (dot becomes
underscore, uppercase, `SENTRY_` prefix) is documented, but the page shows only `SENTRY_ENVIRONMENT`; check the page before
flagging the env form of a dashed property.

## Product support matrix

| product | supported | notes |
|---|---|---|
| errors | yes | unhandled exceptions only by default; `sentry.exception-resolver-order` widens it |
| tracing | yes | `sentry.traces-sample-rate`; with the OTel agent, OpenTelemetry creates spans for instrumented libraries |
| profiling | yes (continuous) | matrix: GA continuous from 8.23; needs `sentry-async-profiler` |
| replay | no | matrix: no Java replay page (the "—" cell) |
| logs | yes | `sentry.logs.enabled`; Logback and Log4j 2 integrations; matrix: GA from 8.12 |
| metrics | yes | matrix: GA from 8.34 (research matrix, not fetched) |
| crons | yes | crons page exists (`platforms/java/guides/spring-boot/crons`, listing only); matrix: GA |
| feedback | yes | matrix: GA (research matrix, not fetched) |
| ai | manual | matrix: manual instrumentation; no Spring AI integration page fetched |
| flags | beta | matrix: platform integration in beta |

## Release and artifacts

- `release`: set explicitly (property, environment variable, or system property). The pages fetched do not state the default
  derivation, so an unset release is a finding until confirmed (see Unconfirmed).
- Java has no source maps. Source context is a source bundle uploaded to Sentry.
- Gradle: `io.sentry.jvm.gradle` 6.24.0 with `includeSourceContext = true` (the page marks the default disabled). Optional
  `additionalSourceDirsForSourceContext`. Auth token from the `SENTRY_AUTH_TOKEN` environment variable. The upload runs on the
  `assemble` task, so the release build must execute it.
- Maven: `sentry-maven-plugin` 0.11.0 with `<extensions>true</extensions>`, goal `uploadSourceBundle`, plus goal
  `validateSdkDependencyVersions` (fails the build on mixed SDK versions). Token via environment, not the POM.
- Debug output: `debugSentryCli` (Maven example) or `debug = true` (Gradle). Turn it off afterwards.
- Manual bundle route: `sentry-ctx docs page platforms/java/source-context --section "Manually Uploading Source Context"`.
- Check that the upload's version matches the release the app reports (not spelled out on the fetched pages).

## Privacy

| data | default | control |
|---|---|---|
| automatic user information | not stated on the fetched pages; the guide's example turns it off | `sentry.data-collection.user-info` |
| Logback message text | a custom encoder sends the encoded message only; template and parameters omitted | `includeUnencodedMessage` on the appender |
| full data categories | data-collected page (`platforms/java/guides/spring-boot/data-management/data-collected`, not fetched) | read it before flagging a category |

## Verify recipe

The guide's Verify snippet calls `captureException` in an isolated try/catch. It proves wiring, not the request path. Use the
real path:

1. Add a temporary controller on a unique path in the app's own package that throws an exception with a unique marker (for
   example `sentry-verify-<date>`). Do not catch it on that path: only unhandled exceptions are sent by default.
   `sentry.exception-resolver-order` is the documented alternative.
2. Start the app the usual way (bootRun or `java -jar`) and call the path with curl against the running server.
3. In Sentry, find the issue with the marker. The stack should show in-app frames from the app package.
4. Remove the controller and temporary properties; `git diff` must show no residue. Resolve the marker issue in Sentry.

## Gotchas

- Wrong starter for the Boot major (Boot 3 on the unsuffixed starter, or Boot 4 on `-jakarta`): match the starter to the Boot
  version in the build file.
- Mixed SDK versions fail the Maven build via `validateSdkDependencyVersions`; use the BOM.
- Handled exceptions are not sent by default, including ones resolved by an exception handler. `sentry.exception-resolver-order=-2147483647`
  includes them (guide, Configure section).
- Logback captures logs as breadcrumbs and error events by default. Sentry Logs need `sentry.logs.enabled=true` and the
  `sentry.logging.minimum-level` threshold.
- With the OTel agent, spans for libraries OpenTelemetry instruments come from OpenTelemetry; their absence from Sentry's own
  spans is expected (opentelemetry page). Do not add manual spans for the same calls.
- Without `includeSourceContext`, source context is not enabled and stack frames lack source lines (source-context page).
- The guide's sample rate `1.0` says "adjust in production": a flat 1.0 in prod is a finding (trace.rate).

## Sources

- https://docs.sentry.io/platforms/java/guides/spring-boot/ (Install, Configure, Verify, Next Steps)
- https://docs.sentry.io/platforms/java/guides/spring-boot/configuration/ (runtime environment, Release, Traces Sample Rate)
- https://docs.sentry.io/platforms/java/guides/spring-boot/source-context/ (Gradle plugin section)
- https://docs.sentry.io/platforms/java/source-context/ (headings only)
- https://docs.sentry.io/platforms/java/guides/spring-boot/opentelemetry/ and .../opentelemetry/setup/ (agent interplay, version alignment)
- https://docs.sentry.io/platforms/java/guides/spring-boot/logging-frameworks/logback/ (threshold properties)
- https://docs.sentry.io/platforms/java/guides/spring-boot/crons/ (headings only)

## Identifiers

```identifiers
sentry-spring-boot-starter | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry-spring-boot-starter-jakarta | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry-spring-boot-4 | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry-async-profiler | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry-opentelemetry-agent | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry-maven-plugin | https://docs.sentry.io/platforms/java/guides/spring-boot/
io.sentry.jvm.gradle | https://docs.sentry.io/platforms/java/guides/spring-boot/
uploadSourceBundle | https://docs.sentry.io/platforms/java/guides/spring-boot/
validateSdkDependencyVersions | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry.dsn | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry.traces-sample-rate | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry.data-collection.user-info | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry.logs.enabled | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry.profile-session-sample-rate | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry.profile-lifecycle | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry.exception-resolver-order | https://docs.sentry.io/platforms/java/guides/spring-boot/
sentry.in-app-packages | https://docs.sentry.io/platforms/java/guides/spring-boot/
SpringBootApplication | https://docs.sentry.io/platforms/java/guides/spring-boot/
SpringBootConfiguration | https://docs.sentry.io/platforms/java/guides/spring-boot/
debugSentryCli | https://docs.sentry.io/platforms/java/guides/spring-boot/
captureException | https://docs.sentry.io/platforms/java/guides/spring-boot/
includeSourceContext | https://docs.sentry.io/platforms/java/guides/spring-boot/source-context/
additionalSourceDirsForSourceContext | https://docs.sentry.io/platforms/java/guides/spring-boot/source-context/
sentry-logback | https://docs.sentry.io/platforms/java/guides/spring-boot/logging-frameworks/logback/
sentry.logging.minimum-event-level | https://docs.sentry.io/platforms/java/guides/spring-boot/logging-frameworks/logback/
sentry.logging.minimum-breadcrumb-level | https://docs.sentry.io/platforms/java/guides/spring-boot/logging-frameworks/logback/
sentry.logging.minimum-level | https://docs.sentry.io/platforms/java/guides/spring-boot/logging-frameworks/logback/
includeUnencodedMessage | https://docs.sentry.io/platforms/java/guides/spring-boot/logging-frameworks/logback/
```

## Unconfirmed

- `SENTRY_AUTO_INIT`: the research note says to set it to false with the OTel agent. Not on the OpenTelemetry setup page or the
  Spring pages fetched on 2026-10-20. Check `opentelemetry/setup/agent` before using it.
- `send-default-pii`: the fixture's detect snapshot reads this key. The Spring pages fetched document `sentry.data-collection.user-info` instead.
- `release`: the default derivation when unset is not stated on the fetched pages.
- `sentry.traces-sample-rate`: no default is stated on the fetched pages.
