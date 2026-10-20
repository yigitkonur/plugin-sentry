# Rust (module: platforms/rust)

Applies to the `sentry` crate 0.49.3 (current docs, checked 2026-10-20). Framework ids `actix`, `axum` and `rocket` resolve to this module. Only the 0.49.3 docs were fetched: "n/d" in the options table means not documented on any fetched page.

## Detect

| Signal | Where | Means |
|---|---|---|
| `sentry = "<req>"` in the manifest; resolved version in the lockfile | `Cargo.toml`, `Cargo.lock` | SDK present. Use the lockfile version (fixture: declared `0.34`, resolved `0.34.0`) |
| `sentry::init(` | entry file or a module it calls (fixture: `src/main.rs:6`) | the init site; a second site is a finding |
| `actix-web`, `axum`, `rocket` dependency | `Cargo.toml` | framework id (fixture: `axum` 0.7.9 from the lockfile) |
| `#[tokio::main]`, `#[actix_web::main]` | entry file (fixture: `src/main.rs:3`) | the runtime starts before init: see Gotchas 1 |
| `.sentryclirc` | repo root | sentry-cli config that holds the token (ecosystem row for rust) |
| `[lib]` only, no `main` | `Cargo.toml` | library crate: does not init Sentry; report and move on |

## Install route

No wizard integration for Rust. Manual route from the live page: `sentry-ctx docs page platforms/rust` (section Install: `sentry = "0.49.3"` under `[dependencies]`). Framework pages: `platforms/rust/guides/actix-web` (the `sentry` dependency enables the `actix` feature) and `platforms/rust/guides/axum` (the example enables `tower-axum-matched-path`). Logs and metrics: `platforms/rust/logs`, `platforms/rust/metrics`. Never paste install steps from memory.

## Init placement

| Entry point | Where `sentry::init` goes | Evidence / note |
|---|---|---|
| Plain binary, sync `fn main` | first statement; keep the guard in a named variable | docs: client must exist before any runtime or thread starts |
| tokio (axum or any async app) | sync `fn main`: init, build the router and layers, then `tokio::runtime::Builder::new_multi_thread()` ... `.block_on(...)` | axum guide Configure; `#[tokio::main]` is not supported |
| actix-web | sync `fn main`: init first, then `actix_web::rt::System::new().block_on(...)` around `HttpServer` | actix guide Configure; `#[actix_web::main]` is not supported |
| rocket | no docs page; see Unconfirmed | apply the same ordering rule and record the result as unverified |

Two init sites in one process, or an init only inside a handler or task module, are findings.

## Options by SDK major

Only the current major is documented. "n/d" = pre-0.48 pins, not on any fetched page.

| option | v(N-1) | v(N) 0.49.3 | note |
|---|---|---|---|
| `dsn` | n/d | string; env `SENTRY_DSN`; unset means no events | fixture hard-codes the DSN at `src/main.rs:5` (public key, not a secret) |
| `release` | n/d | not set by default; env `SENTRY_RELEASE` | use `maybe_release(sentry::release_name!())`; see Release and artifacts |
| `environment` | n/d | env `SENTRY_ENVIRONMENT`; else `development` with debug assertions, `production` without | release-profile builds report `production` unless set |
| `debug` | n/d | default `false` | SDK diagnostics; not for production |
| `send_default_pii` | n/d | default `false` | the guides set `true`; keep only if deliberate |
| `attach_stacktrace` | n/d | default `false` | changes grouping for messages |
| `sample_rate` | n/d | default `1.0` | error sampling, fixed rate only |
| `traces_sample_rate` | n/d | `f32` 0.0 to 1.0 | mutually exclusive with `traces_sampler`; `0.0` still selects fixed rate |
| `traces_sampler` | n/d | callback | replaces any `traces_sample_rate` setting |
| `strict_trace_continuation` | n/d | default `false` | needs `org_id` for self-hosted or local Relay |
| `max_request_body_size` | n/d | default `MaxRequestBodySize::Medium` (10 kB) | `MaxRequestBodySize::None` stops body capture |
| `shutdown_timeout` | n/d | default 2 s | bounds the flush when the guard drops |
| `default_integrations` | n/d | default `true` | defaults depend on the crate's feature flags |
| `auto_session_tracking` | n/d | default `false` | needs the `release-health` feature (on by default) |
| `before_send` | n/d | callback | runs after scope data is applied; scrub PII here |
| `before_send_log` | n/d | callback | drop or edit one log record |

## Product support matrix

| product | supported | notes |
|---|---|---|
| Errors | yes | `sample_rate`, `before_send`; panic reporting is a default integration |
| Tracing | yes | `traces_sample_rate` or `traces_sampler`; axum `SentryHttpLayer::new().enable_transaction()`; actix `start_transaction(true)` |
| Profiling | no | no docs page (probe: Page Not Found); research matrix `—` |
| Replay | no | no docs page; research matrix `—` |
| Logs | yes | enabled by default; if `sentry` is built without default features the `logs` feature must be on |
| Metrics | yes | docs: from 0.48.0; `metrics` feature on by default; the matrix's "Upcoming" is superseded by the docs |
| Crons | no | no docs page; research matrix `—` |
| Feedback | no | no docs page; research matrix `—` |
| AI monitoring | no | no docs page; research matrix `—` |
| Feature flags | no | no docs page; research matrix `—` |
| Debug files | yes | release profile debug info plus `sentry-cli debug-files upload`; see Release and artifacts |
| Release health | yes, opt-in | `auto_session_tracking`, `session_mode` (default `SessionMode::Application`) |

## Release and artifacts

- Release string: `release` is not set by default, and `SENTRY_RELEASE` is read automatically. The documented setter is `maybe_release(sentry::release_name!())`, which "automatically generates the expected release based on the cargo metadata" (options page). Right = the same string at build, upload and runtime. The exact string shape is not on a fetched page.
- Debug files, Linux (source-context page): set the release profile to `debug = true`; then `objcopy --only-keep-debug` on the binary, `objcopy --strip-debug --strip-unneeded`, and `objcopy --add-gnu-debuglink` to link the split file.
- Debug files, macOS (source-context page): release profile with `debug = true`, `split-debuginfo = "packed"` and `strip = true`; plain `cargo build --release` leaves the debug files beside the binary.
- Upload (source-context page), run in CI from the artifacts that ship:
  ```
  sentry-cli debug-files upload --include-sources .
  ```
  Prerequisite: sentry-cli installed and configured with auth token, org and project (`platforms/rust/source-context`, Prerequisites).
- Do not add the `debug_images` integration or the `debug-images` feature when debug info stays in the binary: docs say it collides with built-in debug file processing (platforms/rust, Integrations).
- No source maps for Rust. Releases can be auto-created by uploads or events, so set the name at build time and keep it identical to the deployed one (releases page).

## Privacy

| Data | Default | Control |
|---|---|---|
| Client IP (actix) | not sent | `send_default_pii` `true` enables it (data-collected, Users' IP Address) |
| HTTP headers (`sentry-actix`, `sentry-tower` with the http feature) | potentially sensitive headers filtered | `before_send` and Sensitive Data settings (data-collected, HTTP Headers) |
| Request body | attached only with a valid Content-Length within `max_request_body_size` (default `MaxRequestBodySize::Medium`, 10 kB) | `MaxRequestBodySize::None` stops capture; `MaxRequestBodySize::Always` captures any size (actix guide comment) |
| User and other PII | `send_default_pii` default `false` | docs: remove what you do not want with Sensitive Data settings or `before_send` |

## Verify recipe

1. Add a temporary route to the real router. axum: a handler that panics with a unique marker, the same pattern as the guide's `failing` handler, on a path such as `/sentry-audit-probe`. actix-web: a `#[get]` handler that returns `Err` like the guide's `failing` handler; `capture_server_errors(true)` reports the 500.
2. Run the binary the service ships (`cargo run` for debug, `cargo run --release` for release-profile behaviour), then request the probe path on the service's own listen address with `curl -i`.
3. In Sentry, find the issue with the marker text. Right = one event, with the expected release and environment, and an in-app frame for the probe handler; with a debug-file upload, function names and source context resolve.
4. Remove: delete the route and handler, then `grep -rn "sentry-audit-probe" src` must print nothing. Rebuild.

## Gotchas

1. Runtime macros before init: `#[tokio::main]` and `#[actix_web::main]` start the runtime before `sentry::init`. Docs require init first so spawned threads inherit the hub (platforms/rust, Async Main Function). Fixture `src/main.rs:3` uses `#[tokio::main]` with init at line 6: finding.
2. Guard lifetime: `let _guard = sentry::init(...)` must live until exit. Dropping it flushes with a two-second deadline. `let _ = sentry::init(...)` drops at once (Rust semantics), so nothing is sent.
3. Layer order. actix: the Sentry middleware is the last `wrap` (it must see the request first). axum: layers bound directly on `Router` go in the opposite order, or the guide warns of a memory leak. Use the guide's `ServiceBuilder` form.
4. Feature flags decide integrations: the guides enable `actix` or `tower-axum-matched-path` on `sentry`. A manifest without them gets no framework integration. `default_integrations` depends on the active features.
5. Research notes disagree with the docs. The notes name separate crates (`sentry-actix`, `sentry-tower`, `sentry-tracing`) and a `.bind_hub(...)` call for futures. The docs wire everything through `sentry` features and `sentry::integrations::*` paths, and `bind_hub` is on no fetched page. Follow the docs.
6. Stale pin: fixture `sentry` 0.34.0 predates logs and metrics as documented here (metrics from 0.48.0). Finding: upgrade or justify the pin.
7. Environment default: without `SENTRY_ENVIRONMENT` or `environment`, release-profile builds report `production`. Staging binaries built in release mode therefore look like production. Right = set it explicitly.
8. Trace continuation: `strict_trace_continuation` needs an organization ID, parsed from SaaS DSNs. The docs say the Rust SDK does not yet attach one to outgoing traces, so keep it off if upstream callers use such an SDK.

## Sources
- https://docs.sentry.io/platforms/rust/
- https://docs.sentry.io/platforms/rust/configuration/options/
- https://docs.sentry.io/platforms/rust/configuration/releases/
- https://docs.sentry.io/platforms/rust/guides/actix-web/
- https://docs.sentry.io/platforms/rust/guides/axum/
- https://docs.sentry.io/platforms/rust/source-context/
- https://docs.sentry.io/platforms/rust/logs/
- https://docs.sentry.io/platforms/rust/metrics/
- https://docs.sentry.io/platforms/rust/data-management/data-collected/

## Identifiers
```identifiers
sentry::init | https://docs.sentry.io/platforms/rust/
sentry::ClientOptions | https://docs.sentry.io/platforms/rust/
maybe_release | https://docs.sentry.io/platforms/rust/
release_name | https://docs.sentry.io/platforms/rust/configuration/options/
tokio::main | https://docs.sentry.io/platforms/rust/
actix_web::main | https://docs.sentry.io/platforms/rust/
debug-images | https://docs.sentry.io/platforms/rust/
debug_images | https://docs.sentry.io/platforms/rust/
dsn | https://docs.sentry.io/platforms/rust/configuration/options/
release | https://docs.sentry.io/platforms/rust/configuration/options/
environment | https://docs.sentry.io/platforms/rust/configuration/options/
debug | https://docs.sentry.io/platforms/rust/configuration/options/
send_default_pii | https://docs.sentry.io/platforms/rust/configuration/options/
attach_stacktrace | https://docs.sentry.io/platforms/rust/configuration/options/
sample_rate | https://docs.sentry.io/platforms/rust/configuration/options/
traces_sample_rate | https://docs.sentry.io/platforms/rust/configuration/options/
traces_sampler | https://docs.sentry.io/platforms/rust/configuration/options/
strict_trace_continuation | https://docs.sentry.io/platforms/rust/configuration/options/
org_id | https://docs.sentry.io/platforms/rust/configuration/options/
max_request_body_size | https://docs.sentry.io/platforms/rust/configuration/options/
MaxRequestBodySize::Medium | https://docs.sentry.io/platforms/rust/configuration/options/
MaxRequestBodySize::None | https://docs.sentry.io/platforms/rust/data-management/data-collected/
MaxRequestBodySize::Always | https://docs.sentry.io/platforms/rust/guides/actix-web/
shutdown_timeout | https://docs.sentry.io/platforms/rust/configuration/options/
default_integrations | https://docs.sentry.io/platforms/rust/configuration/options/
auto_session_tracking | https://docs.sentry.io/platforms/rust/configuration/options/
session_mode | https://docs.sentry.io/platforms/rust/configuration/options/
release-health | https://docs.sentry.io/platforms/rust/configuration/options/
before_send | https://docs.sentry.io/platforms/rust/configuration/options/
before_send_log | https://docs.sentry.io/platforms/rust/configuration/options/
SENTRY_DSN | https://docs.sentry.io/platforms/rust/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/rust/configuration/options/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/rust/configuration/options/
SentryHttpLayer | https://docs.sentry.io/platforms/rust/guides/axum/
enable_transaction | https://docs.sentry.io/platforms/rust/guides/axum/
tower-axum-matched-path | https://docs.sentry.io/platforms/rust/guides/axum/
new_multi_thread | https://docs.sentry.io/platforms/rust/guides/axum/
capture_server_errors | https://docs.sentry.io/platforms/rust/guides/actix-web/
start_transaction | https://docs.sentry.io/platforms/rust/guides/actix-web/
sentry::integrations::actix | https://docs.sentry.io/platforms/rust/guides/actix-web/
HttpServer | https://docs.sentry.io/platforms/rust/guides/actix-web/
ServiceBuilder | https://docs.sentry.io/platforms/rust/guides/axum/
sentry::integrations::tracing::layer | https://docs.sentry.io/platforms/rust/logs/
logs | https://docs.sentry.io/platforms/rust/logs/
split-debuginfo | https://docs.sentry.io/platforms/rust/source-context/
debug-files | https://docs.sentry.io/platforms/rust/source-context/
include-sources | https://docs.sentry.io/platforms/rust/source-context/
sentry-cli | https://docs.sentry.io/platforms/rust/source-context/
sentry-actix | https://docs.sentry.io/platforms/rust/data-management/data-collected/
sentry-tower | https://docs.sentry.io/platforms/rust/data-management/data-collected/
```

## Unconfirmed
- `bind_hub`, `Hub::current`, `sentry-tracing`: research notes only; no fetched page names them (the logs page uses `sentry::integrations::tracing`). Do not use.
- Release string shape from `release_name`; option names and defaults before 0.48; Rocket wiring and its entry macro: not on any fetched page (no Rocket docs page exists).
- Profiling, replay, crons, feedback, AI monitoring, feature flags: no docs page (404 probes) and matrix `—`; no official "unsupported" sentence was fetched, so the matrix "no" is provisional.
