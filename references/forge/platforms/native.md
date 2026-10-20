# Native (C/C++) SDK (module: platforms/native)

Applies to the Sentry Native SDK (C API in `sentry.h`, built with CMake). Framework id `native`. The docs show no major split (SDK 0.x; the `native` backend is since 0.13.2), so v(N-1) is n/a throughout.

## Detect

| Signal | Where | Means |
|---|---|---|
| `CMakeLists.txt`, `vcpkg.json`, `conanfile.txt`, `conanfile.py`, `meson.build` | repo root and build dirs | build system; the SDK is consumed as a CMake project |
| `#include <sentry.h>` and `sentry_init(` | `.c`, `.cc`, `.cpp`, `.cxx`, `.h`, `.hpp` | SDK in use; the init site to read, usually in `main` |
| `SENTRY_BACKEND` | CMake invocations in scripts, CI, Dockerfile, README | backend chosen at build time; absent means the desktop default (crashpad) |
| `.sentryclirc` | repo root | sentry-cli config; must be gitignored if it holds a token |

`sentry_init(` present with no `sentry.h` include, or `sentry.h` included with no init call, is a finding.

Not this module: Android apps using the NDK. The Install section says the Native SDK is an NDK support library inside the Android SDK and does not directly support Android; audit those under the Android module.

## Install route

Manual only. The platform page documents no wizard integration. Build from the SDK release sources with CMake, then install. Docs path: `sentry-ctx docs page platforms/native --section Install`.

| Host | Build | Installed artifacts |
|---|---|---|
| macOS | `cmake -B build -D SENTRY_BACKEND=crashpad -D CMAKE_BUILD_TYPE=RelWithDebInfo` (CMake 4: export `SDKROOT` first), `cmake --build build --parallel`, `cmake --install build --prefix install` | `bin/crashpad_handler`, `include/sentry.h`, shared library plus `.dSYM` |
| Windows | `cmake -B build`, `cmake --build build --config RelWithDebInfo`, `cmake --install build --prefix install --config RelWithDebInfo` | `bin/crashpad_handler` (with `.exe`), `bin/sentry.dll` plus `.pdb`, `lib/sentry.lib` |

## Init placement

| Where | Rule | Evidence |
|---|---|---|
| Entry point (`main`), as early as possible | `sentry_options_new()`, set options, then `sentry_init(options)`; `crash_reporting_mode` and `minidump_mode` must be set before it | Configure section; backends/native page |
| Every exit path | `sentry_close()` before the process ends | Configure warning: event data may be lost |

## Options by SDK major

| option | v(N-1) | v(N) | note |
|---|---|---|---|
| `dsn` | n/a | no default; env `SENTRY_DSN` | neither set: no events are sent |
| `database_path` | n/a | default `.sentry-native`, relative to CWD | local event and crash database; docs urge an explicit path |
| `release` | n/a | env `SENTRY_RELEASE` | no other default documented; see Release and artifacts |
| `environment` | n/a | default `production`; env `SENTRY_ENVIRONMENT` | staging and dev builds must set it |
| `debug` | n/a | `true` when `NDEBUG` is not defined, else `false`; env `SENTRY_DEBUG` | release builds default to false |
| `crash_reporting_mode` | n/a | default `SENTRY_CRASH_REPORTING_MODE_NATIVE_WITH_MINIDUMP` | event with client-side stacks plus `event.minidump`; `SENTRY_CRASH_REPORTING_MODE_MINIDUMP` sends a minidump only (server-side) |
| `minidump_mode` | n/a | default `SENTRY_MINIDUMP_MODE_SMART` | affects only the `native` backend and modes that send a minidump; no effect on crashpad |
| `before_send` | n/a | hook | scrub or drop any event; see Privacy |
| `on_crash` | n/a | hook, backend-specific event | crash events only; drop by calling `sentry_value_decref` on the event |
| `before_send_feedback` | n/a | hook | feedback payload |
| `traces_sample_rate`, `traces_sampler` | n/a | Tracing Options; sampler returns 0 to 1 | default not stated on the page: set it deliberately |
| `before_send_log`, `logs_with_attributes`, `before_send_metric` | n/a | Logs and Metrics options | |
| `propagate_traceparent`, `send_client_reports`, `max_breadcrumbs`, `sample_rate` | n/a | Core options | defaults not read on this pass |

## Product support matrix

Rows come from the plugin's platform matrix snapshot (research/06, section 3), not product pages; version floors are from that snapshot. "no" means the matrix shows no page or no integration.

| product | supported | notes |
|---|---|---|
| Errors | yes (GA) | `before_send`, `on_crash`; symbols need debug files |
| Tracing | yes (GA) | `traces_sample_rate`, `traces_sampler`, `propagate_traceparent` |
| Profiling | no (matrix: no page) | no profiling option on the options page |
| Replay | no (matrix: no page) | no replay option on the options page |
| Logs | yes (GA, 0.11.1+) | `before_send_log`, `logs_with_attributes` |
| Metrics | yes (GA, 0.12.6+) | `before_send_metric` |
| Crons | no (matrix: no page) | |
| Feedback | yes (GA, 0.16+) | `before_send_feedback`; user-feedback page not fetched |
| AI | no (matrix: no page) | |
| Flags | no (matrix: no integration) | |
| Debug files | yes | `sentry-cli debug-files upload`; see Release and artifacts |
| App hangs | unconfirmed | App Hang section of the options page; no matrix row |

## Release and artifacts

- `release`: set with `sentry_options_set_release` or env `SENTRY_RELEASE`. Docs example shape: `my-project-name@2.3.12`. No other default is documented, so an unset release must be found in code, CI or the Dockerfile; treat it as a finding.
- Debug files (symbols for crash frames): upload before shipping with `sentry-cli debug-files upload -o <org> -p <project> <path>`. For a manual test, use `--wait` before the first native crash. Upload the debug companions the build emits (`.dSYM` on macOS, `.pdb` on Windows). Source: debug-files/upload page.
- Propagation delay: a file Sentry once reported missing can take up to one hour to apply to new crashes. Existing events and issues are not reprocessed.
- Minidump endpoint (only for dumps made by something other than the SDK): POST `upload_file_minidump` to the Minidump Endpoint URL in Project Settings > Client Keys. Source: minidumps guide.

## Privacy

| Data | Default | Control |
|---|---|---|
| Minidump (process memory around the crash) | attached as `event.minidump` in the default mode | `crash_reporting_mode`; `minidump_mode` (`SENTRY_MINIDUMP_MODE_STACK_ONLY` captures less memory) |
| Event contents | sent | `before_send` for all events; `on_crash` for crash events |
| Feedback payload | sent when the app submits feedback | `before_send_feedback` |
| Logs and metrics | sent when emitted | `before_send_log`, `before_send_metric` |
| Local event and crash database | `.sentry-native` in CWD | `database_path` |

## Verify recipe

1. Put one temporary call inside the real code path the feature runs (the handler or loop body, not a stub in `main`), gated by a temporary check so it fires once. Use the docs' message shape with a unique marker:

```c
/* TEMP sentry-verify: remove after check */
sentry_capture_event(sentry_value_new_message_event(SENTRY_LEVEL_INFO, "custom", "sentry-verify-<UTC timestamp>"));
```

2. Build with the production CMake settings (same `SENTRY_BACKEND` and build type), run the real path once, and find the marker in the project's Issues within a minute.
3. Remove: delete the TEMP block and its gate, rebuild, and confirm `grep -rn "sentry-verify" <src>` prints nothing.

## Gotchas

| Symptom | Cause | Fix and source |
|---|---|---|
| Last events missing at exit | no `sentry_close()` | call it before every exit; Configure warning |
| macOS sessions show as `abnormal` | crashpad on macOS cannot reliably tell crashed sessions apart | known limitation, crashpad page |
| No crash reports from a sandboxed macOS app | crashpad client cannot start `crashpad_handler` under the sandbox | use the `native` backend, or `breakpad` or `inproc` if no extra executable can ship; crashpad page |
| No crash reports on desktop | `crashpad_handler` not beside the app binary | ship it alongside; Install section |
| `minidump_mode` has no effect | it only applies to the `native` backend and minidump modes | set `SENTRY_BACKEND=native` if the setting matters; backends/native page |
| Android crashes not captured by this module's setup | Android is not directly supported; NDK use goes through the Android SDK | Install section; Android module |
| Old crashes still unsymbolicated after upload | existing events are not reprocessed | upload page. The plugin research note says native events reprocess after a dSYM upload; the page says otherwise, so follow the page |
| Backend claimed as "inproc on Android" | the research note says so; the docs give no Android default | follow the docs: crashpad is the desktop default only |

## Sources

- https://docs.sentry.io/platforms/native/
- https://docs.sentry.io/platforms/native/configuration/options/
- https://docs.sentry.io/platforms/native/configuration/backends/crashpad/
- https://docs.sentry.io/platforms/native/configuration/backends/native/
- https://docs.sentry.io/platforms/native/data-management/debug-files/upload/
- https://docs.sentry.io/platforms/native/guides/minidumps/
- https://docs.sentry.io/platforms/native/guides/breakpad/

## Identifiers

```identifiers
dsn | https://docs.sentry.io/platforms/native/configuration/options/
database_path | https://docs.sentry.io/platforms/native/configuration/options/
release | https://docs.sentry.io/platforms/native/configuration/options/
environment | https://docs.sentry.io/platforms/native/configuration/options/
debug | https://docs.sentry.io/platforms/native/configuration/options/
crash_reporting_mode | https://docs.sentry.io/platforms/native/configuration/options/
minidump_mode | https://docs.sentry.io/platforms/native/configuration/options/
before_send | https://docs.sentry.io/platforms/native/configuration/options/
on_crash | https://docs.sentry.io/platforms/native/configuration/options/
before_send_feedback | https://docs.sentry.io/platforms/native/configuration/options/
traces_sample_rate | https://docs.sentry.io/platforms/native/configuration/options/
traces_sampler | https://docs.sentry.io/platforms/native/configuration/options/
before_send_log | https://docs.sentry.io/platforms/native/configuration/options/
logs_with_attributes | https://docs.sentry.io/platforms/native/configuration/options/
before_send_metric | https://docs.sentry.io/platforms/native/configuration/options/
propagate_traceparent | https://docs.sentry.io/platforms/native/configuration/options/
send_client_reports | https://docs.sentry.io/platforms/native/configuration/options/
max_breadcrumbs | https://docs.sentry.io/platforms/native/configuration/options/
sample_rate | https://docs.sentry.io/platforms/native/configuration/options/
SENTRY_DSN | https://docs.sentry.io/platforms/native/configuration/options/
SENTRY_RELEASE | https://docs.sentry.io/platforms/native/configuration/options/
SENTRY_ENVIRONMENT | https://docs.sentry.io/platforms/native/configuration/options/
SENTRY_DEBUG | https://docs.sentry.io/platforms/native/configuration/options/
NDEBUG | https://docs.sentry.io/platforms/native/configuration/options/
sentry_value_decref | https://docs.sentry.io/platforms/native/configuration/options/
sentry_options_new | https://docs.sentry.io/platforms/native/
sentry_options_set_dsn | https://docs.sentry.io/platforms/native/
sentry_options_set_release | https://docs.sentry.io/platforms/native/
sentry_init | https://docs.sentry.io/platforms/native/
sentry_close | https://docs.sentry.io/platforms/native/
sentry_capture_event | https://docs.sentry.io/platforms/native/
sentry_value_new_message_event | https://docs.sentry.io/platforms/native/
SENTRY_LEVEL_INFO | https://docs.sentry.io/platforms/native/
SENTRY_BACKEND | https://docs.sentry.io/platforms/native/
CMAKE_BUILD_TYPE | https://docs.sentry.io/platforms/native/
RelWithDebInfo | https://docs.sentry.io/platforms/native/
crashpad_handler | https://docs.sentry.io/platforms/native/
SDKROOT | https://docs.sentry.io/platforms/native/
crashpad | https://docs.sentry.io/platforms/native/configuration/backends/crashpad/
inproc | https://docs.sentry.io/platforms/native/configuration/backends/crashpad/
breakpad | https://docs.sentry.io/platforms/native/configuration/backends/crashpad/
SENTRY_CRASH_REPORTING_MODE_NATIVE_WITH_MINIDUMP | https://docs.sentry.io/platforms/native/configuration/backends/native/
SENTRY_CRASH_REPORTING_MODE_MINIDUMP | https://docs.sentry.io/platforms/native/configuration/backends/native/
SENTRY_MINIDUMP_MODE_SMART | https://docs.sentry.io/platforms/native/configuration/backends/native/
SENTRY_MINIDUMP_MODE_STACK_ONLY | https://docs.sentry.io/platforms/native/configuration/backends/native/
event.minidump | https://docs.sentry.io/platforms/native/configuration/backends/native/
upload_file_minidump | https://docs.sentry.io/platforms/native/guides/minidumps/
```

## Unconfirmed
- `sentry_capture_user_feedback`: research note says deprecated for `sentry_capture_feedback` from 0.16; the user-feedback page was not fetched.
- `sentry` CLI v4 and `--include-sources`: research notes only. The native upload page still names sentry-cli and does not show `--include-sources`. Check the live page before changing either.
- `configuration/backends/breakpad` and `configuration/backends/inproc`: Page Not Found on the docs site. The backend names above come only from the crashpad and native pages.
