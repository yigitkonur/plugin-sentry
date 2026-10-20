# Profiling (product id: profiling)

## Fit
Propose profiling only when the repo shows a long-running process that Sentry already reports from, and the org can buy a pay-as-you-go (PAYG) budget. Profile hours cannot be bought any other way (https://docs.sentry.io/pricing/). The applicability rule is the `profiling` row in data/signals.tsv: backend or worker roles on python, js, jvm, dotnet, ruby or php that are not a short-lived serverless runtime; fullstack js on docker, fly, render, railway, heroku, cloud-run, kubernetes or gcp-app-engine; mobile; or macos, ios, tvos or visionos.

| Repo evidence | Why it qualifies |
|---|---|
| Long-running backend or worker (Python, Node, or another listed eco) with `sentry-sdk`, `@sentry/node` or equivalent in the manifest and an init call | Continuous profiling attaches to a process that lives for many requests |
| Fullstack JS deployed to a container or PaaS host from the list above | Same as backend; the signal rule pairs these hosts with fullstack js |
| Mobile or Apple app (`sentry-cocoa`, `io.sentry` Android) | UI profiling is documented for Apple and Android |
| Tracing already on (`tracesSampleRate`, `traces_sample_rate`, Android sample-rate meta-data) and a known slow path | The `trace` lifecycle needs tracing; the flame graph localizes the slow span (https://docs.sentry.io/product/profiling/) |

Not worth proposing:
- A short-lived serverless runtime (Lambda, Cloud Functions or similar). The signal rule excludes it. See the serverless notes under Properly configured.
- A platform without profiling support: Node on Deno or Bun (the Node profiler is a native add-on; platforms/javascript/guides/node/profiling), or browser profiling outside Chromium (platforms/javascript/profiling).
- A repo with no Sentry SDK, or no org access (the billing rows stay UNVERIFIED, never n/a).
- An org that will not fund a PAYG budget: continuous and UI profile hours are PAYG-only.
- A repo whose only profiling code uses the removed per-transaction option. Migrate that code to session options first; see Common mistakes.

## Properly configured
Profiling is session sampling plus a lifecycle. Choose the lifecycle first, then the session rate.

| SDK family (docs path) | Right | Source |
|---|---|---|
| Browser JS (`@sentry/browser` 10.27.0+, Chromium only) | `profileSessionSampleRate` above 0 (default `0` disables it); `profileLifecycle` `manual` (default) or `trace` with `browserProfilingIntegration` and `tracesSampleRate` set; the document response carries `Document-Policy: js-profiling` | platforms/javascript/profiling; platforms/javascript/configuration/options |
| Node (JS) with `@sentry/profiling-node` at the same exact version as the main SDK | `nodeProfilingIntegration` in `integrations`; `profileSessionSampleRate` above 0; `profileLifecycle` set explicitly. `profileSessionSampleRate: 0.0` is the documented service-level off switch | platforms/javascript/guides/node/profiling |
| Python (`sentry-sdk` 2.24.1+ for continuous profiling; 3.x is current) | `profile_session_sample_rate` above 0 (default `None` disables it); `profile_lifecycle` `"trace"` (needs `traces_sample_rate`) or `"manual"` (default) with `start_profiler` and `stop_profiler` around the code to profile | platforms/python/profiling; platforms/python/configuration/options |
| Apple (Cocoa 8.49.0+ for UI profiling; 9.x is current) | `options.configureProfiling` closure sets `sessionSampleRate` (default 0); lifecycle `.trace` needs `tracesSampleRate` above 0; `profileAppStarts` only when a launch profile is wanted | platforms/apple/profiling |
| Android (UI profiling) | Manifest meta-data `io.sentry.traces.profiling.session-sample-rate` and `io.sentry.traces.profiling.lifecycle`; `trace` requires tracing enabled, `manual` does not | platforms/android/profiling |

Rules that hold across families:
- The session decision is made once per session (browser, Android, Apple) or once at SDK init (Python). Changing a rate takes effect on the next session or process.
- Apple: the profile rate is relative to the trace rate. Both at 0.5 gives about 25% of attempts (platforms/apple/profiling).
- JS `trace` lifecycle stops after at most 5 minutes per root span (platforms/javascript/configuration/options).
- Apple's prior profiling APIs were removed in 9.0.0; UI profiling arrived in 8.49.0 (platforms/apple/profiling).
- Production: a session rate of 1.0 is a deliberate cost decision (see Volume). Use a fraction, or a service-level rate per deployment.

### Short-lived serverless runtime
- Once-per-init decision: if Sentry initializes on every cold start, the profiled share is cold starts, not requests. This is derived from the once-per-init statements on platforms/python/configuration/options and platforms/javascript/configuration/options.
- `manual` collects only between the start and stop calls, so start and stop must bracket the work inside the same invocation (platforms/python/profiling; platforms/javascript/guides/node/profiling).
- Node: the default eager logging mode keeps a constant CPU cost even when no profile is active; lazy mode (`SENTRY_PROFILER_LOGGING_MODE`) makes `startProfiler` take a few hundred ms per call (platforms/javascript/guides/node/profiling). Both costs repeat on every cold start.
- Node: prebuilt binaries exist only for the listed architecture and Node version pairs; any other pair compiles from source at install (same page, "Precompiled Binaries").
- Whether profiles flush before the runtime freezes is not in the fetched sections. See Unconfirmed.

## Checks
| check id | read | passes when |
|---|---|---|
| prof.lifecycle | Init and config files: `grep -rn -E "profileLifecycle\|profileSessionSampleRate\|profile_lifecycle\|profile_session_sample_rate\|configureProfiling\|io.sentry.traces.profiling" <repo>`. Call sites: `grep -rn -E "startProfiler\|start_profiler\|stopProfiler\|stop_profiler" <repo>`. Tracing: `grep -rn -E "tracesSampleRate\|traces_sample_rate\|traces-sample-rate" <repo>`. Browser: `grep -rn "Document-Policy" <repo>` in vercel.json, netlify.toml, _headers, nginx or apache config, or server middleware. Removed per-transaction options: `grep -rn -i -E "profiles.?sampl|launch.?profil" <repo>` (any hit in the SDK's init or config code) | Each profiling-enabled SDK: (a) `manual` (explicit or default) has a start call and a matching stop call around the code the profile should cover; a `manual` setup with no start call is a finding (no profile is ever collected); (b) `trace` has tracing on in the same init (non-zero trace rate) and a non-zero session rate; (c) browser profiling has `Document-Policy: js-profiling` on the document response; (d) no removed per-transaction name appears in JS v11+, Python 3+ or Cocoa 9+ code; (e) a production session rate of 1.0 is a recorded decision, not a default |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Session rate set, no profiles arrive | `profileLifecycle` / `profile_lifecycle` left at the default `manual`, and no start call runs | Use `trace` with tracing on, or wrap the work in start and stop calls | platforms/javascript/configuration/options; platforms/python/profiling |
| Browser profiles never arrive | No `Document-Policy: js-profiling` header, or a non-Chromium browser | Add the header at the host or server (examples for Vercel, Netlify, Express, nginx, Apache on the page) | platforms/javascript/profiling |
| `trace` lifecycle collects nothing | Tracing off, or the root span was not sampled | Set the trace rate above 0; Android docs say `trace` requires tracing | platforms/android/profiling; platforms/javascript/configuration/options |
| Apple profiles at about a quarter of the expected share | Session rate is relative to the trace rate | Read the rates as a product; set the trace rate deliberately | platforms/apple/profiling |
| Old per-transaction profiling option set, nothing collected in the new SDK | The per-transaction option is removed in current majors (see Unconfirmed for the versions) | Replace with the session options: `profileSessionSampleRate`, Python `profile_session_sample_rate`, Apple `configureProfiling` `sessionSampleRate` | platforms/javascript/configuration/options; platforms/apple/profiling |
| Node profiles missing after a SDK upgrade | `@sentry/profiling-node` version differs from the main SDK | Install the same exact version | platforms/javascript/guides/node/profiling |
| Node profiler on Deno or Bun | Native add-on, not supported there | Not a fit | platforms/javascript/guides/node/profiling |
| Node `startProfiler` slow on every call | Lazy logging mode (`SENTRY_PROFILER_LOGGING_MODE`) | Keep the default eager mode unless constant CPU cost matters more than call latency | platforms/javascript/guides/node/profiling |
| Apple launch profile keeps running for the whole session | Manual lifecycle with `profileAppStarts` and no `stopProfiler` call, or the SDK was not started on that launch | Add the stop call, or use the trace lifecycle | platforms/apple/profiling |

## Volume, cost and overhead
| Product | Billed as | Included on paid plans | Source |
|---|---|---|---|
| Continuous profiling (backend) | Continuous Profile Hours: profile length in milliseconds, billed in hours | None; PAYG only | https://docs.sentry.io/pricing/ |
| UI profiling (browser, mobile) | UI Profile Hours | None; PAYG only | https://docs.sentry.io/pricing/ |
| Transaction-based (legacy) | Billed under UI or Continuous Profile Hours | Same as above | https://docs.sentry.io/pricing/ |

- Profile hours can only be bought with the PAYG budget (pricing page). The budget is a prerequisite, not a quota line.
- Overhead: the sampling profiler takes about 100 stack samples per second (every 10 ms). The docs target about 1-5% CPU time overhead on a typical configuration, and say overhead is imperceptible for most applications (https://docs.sentry.io/product/profiling/performance-overhead/).
- Node eager logging has a constant CPU cost even when no profile is active (see Properly configured).
- Default off: JS `profileSessionSampleRate` defaults to `0`, and Python `profile_session_sample_rate` defaults to `None`, so profiling is off until a rate is set.

## Verify (R6)
1. In a non-production environment, set the session rate to 1.0 and the lifecycle the code ships with. For `trace`, also set the trace rate to 1.0. For `manual`, run the code path between the start and stop calls.
2. Trigger one traced request or flow. Open the Profiling page in Sentry (Transactions tab, Aggregate Flamegraph tab; https://docs.sentry.io/product/profiling/). The transaction should link to a profile, and the profile should cover only the window you set in `manual` mode.
3. Confirm a PAYG budget exists with the org owner (Settings > Subscription is UI-only; ask the user, else UNVERIFIED).
4. Remove the trigger: restore the production session rate and the shipped lifecycle, then redeploy.

## Sources
- https://docs.sentry.io/product/profiling/
- https://docs.sentry.io/product/profiling/performance-overhead/
- https://docs.sentry.io/pricing/
- https://docs.sentry.io/platforms/javascript/profiling/
- https://docs.sentry.io/platforms/javascript/guides/node/profiling/
- https://docs.sentry.io/platforms/javascript/configuration/options/
- https://docs.sentry.io/platforms/python/profiling/
- https://docs.sentry.io/platforms/python/configuration/options/
- https://docs.sentry.io/platforms/apple/profiling/
- https://docs.sentry.io/platforms/android/profiling/

## Identifiers
```identifiers
profileSessionSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
profileLifecycle | https://docs.sentry.io/platforms/javascript/configuration/options/
uiProfiler | https://docs.sentry.io/platforms/javascript/profiling/
startProfiler | https://docs.sentry.io/platforms/javascript/profiling/
stopProfiler | https://docs.sentry.io/platforms/javascript/profiling/
browserProfilingIntegration | https://docs.sentry.io/platforms/javascript/profiling/
tracesSampleRate | https://docs.sentry.io/platforms/javascript/profiling/
Document-Policy | https://docs.sentry.io/platforms/javascript/profiling/
nodeProfilingIntegration | https://docs.sentry.io/platforms/javascript/guides/node/profiling/
SENTRY_PROFILER_LOGGING_MODE | https://docs.sentry.io/platforms/javascript/guides/node/profiling/
profile_session_sample_rate | https://docs.sentry.io/platforms/python/profiling/
profile_lifecycle | https://docs.sentry.io/platforms/python/profiling/
start_profiler | https://docs.sentry.io/platforms/python/profiling/
stop_profiler | https://docs.sentry.io/platforms/python/profiling/
traces_sample_rate | https://docs.sentry.io/platforms/python/profiling/
configureProfiling | https://docs.sentry.io/platforms/apple/profiling/
sessionSampleRate | https://docs.sentry.io/platforms/apple/profiling/
profileAppStarts | https://docs.sentry.io/platforms/apple/profiling/
io.sentry.traces.profiling.session-sample-rate | https://docs.sentry.io/platforms/android/profiling/
io.sentry.traces.profiling.lifecycle | https://docs.sentry.io/platforms/android/profiling/
```

## Unconfirmed
- `profilesSampleRate` (JS v11, Cocoa 9.0), `profiles_sample_rate` and `profilesSampler` (Python 3.0): removal versions come from data/stale-apis/*.tsv. The fetched migration pages do not name them, and the Python options page still documents `profiles_sample_rate` with no removal note. Verify before quoting a version.
- Browser UI profiling status: research note 06-product-map says beta; the fetched browser page shows only a "Chromium Only" banner and no beta label. Treat the docs page as the source.
- Android minimum SDK version for UI profiling (research note says 8.5): not in the fetched Android sections; verify.
- Transaction-based-only SDKs (React Native, PHP, Ruby, .NET): research note only; read their platform profiling pages before proposing.
- Serverless: whether profiles flush before a function freezes, and the AWS Lambda profiling guidance. Read platforms/javascript/guides/aws-lambda/profiling and platforms/python/guides/aws-lambda before proposing; not read here.
- The stats API category name for profile hours: not confirmed on an official page; read the returned groups rather than assuming a name.
