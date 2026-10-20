# Session Replay (product id: replay)

## Fit
Applicability (`data/signals.tsv`, rule `replay`): a client role in the JS ecosystem (frontend or fullstack), a mobile role, or `fw:electron`. Not applicable: server, CLI, or a native macOS app.

Evidence that makes it worth proposing:
- A browser SDK init (client entry or client config) and no `replayIntegration` call anywhere in the repo.
- A mobile SDK init (Android, iOS, React Native, Flutter) with no replay setup at all.
- Production web or mobile traffic through flows where a user's path explains an error (checkout, forms, uploads, onboarding).
- A replay already on with a production session rate of 1.0 (cost problem; see Checks).

Not worth proposing:
- Backend-only or CLI repos: nothing on screen to record.
- Native macOS apps: the mobile product page lists Android, iOS, React Native and Flutter; macOS is not listed.
- Apps with sensitive screens and no one to review masking. The usual "fix" for a missing replay is turning masking off; review masking first or do not propose.
- Electron (`fw:electron`) until the SDK route is confirmed; no Electron replay page was found (see Unconfirmed).

## Properly configured
Sampling logic is the same on every platform: the session rate is checked first; if it is not sampled, the on-error rate is checked. Names are as each platform page spells them.

| SDK family | Sampling | Privacy default | Other |
|---|---|---|---|
| Browser JS (current docs) | `replaysSessionSampleRate` 0.1 at 10k–100k sessions/day (0.01 above 100k, 0.25 below 10k); `replaysOnErrorSampleRate` 1.0. Both default to 0 | `maskAllText`, `maskAllInputs`, `blockAllMedia` default to true | `replayIntegration()` in init; `workerUrl` only when CSP blocks inline workers; `networkDetailAllowUrls` lists only URLs safe to capture |
| React Native | `replaysSessionSampleRate` / `replaysOnErrorSampleRate` (web names) | Masks text, images, webviews by default; opt out only via `mobileReplayIntegration` with `maskAllText`, `maskAllImages`, `maskAllVectors` | `beforeErrorSampling` (on-error capture can be limited to unhandled errors); `networkDetailAllowUrls` (RN SDK 8.15.0+) |
| iOS (Cocoa) | `options.sessionReplay.sessionSampleRate`, `options.sessionReplay.onErrorSampleRate` | Masks text, images, PDF viewers and webviews by default; `maskAllText` and `maskAllImages` false only to disable | On-error buffer 30 s |
| Android | `options.sessionReplay.sessionSampleRate`, `options.sessionReplay.onErrorSampleRate`; `beforeErrorSampling` | Masks text, images, webviews by default; same two flags to disable | `screenshotStrategy`: PixelCopy (default) or Canvas for strict PII; On-error buffer 30 s |
| Flutter | See Unconfirmed (sampling names not fetched) | Masks text, inputs and non-asset images; asset images need `maskAssetImages` | Mobile floor per the mobile page (see Unconfirmed) |

Notes:
- Browser on-error buffer is up to one minute; iOS and Android are 30 seconds; React Native's sampling section says a minute.
- Web sessions are recorded in real time only when session-sampled; an on-error session sends the buffer plus the rest of the session.
- Mobile floors (product page): iOS 8.43.0, Android 7.20.0, React Native 6.5.0, Flutter 8.12.0 (see Unconfirmed for the conflicting iOS page).

## Checks
| check id | read | passes when |
|---|---|---|
| replay.rates | Applies when a replay integration or replay sample option exists. Grep `replayIntegration`, `replaysSessionSampleRate`, `replaysOnErrorSampleRate`, `sessionSampleRate`, `onErrorSampleRate` across the client init files (`sentry.client.config.*`, `instrumentation-client.*`, the browser entry calling `Sentry.init`, the iOS SDK start code, the Android `Application` class, RN and Flutter init). Read the production branch of the init, not the dev branch. For CSP, grep `Content-Security-Policy` in `next.config.*`, `middleware.*`, nginx/Caddy/vercel.json/netlify.toml and `<meta http-equiv="Content-Security-Policy">` | In the production branch: the session rate is below 1.0 (`replaysSessionSampleRate` on web and RN; `options.sessionReplay.sessionSampleRate` on iOS and Android); the on-error rate is above 0 (`replaysOnErrorSampleRate` / `options.sessionReplay.onErrorSampleRate`; docs recommend 1.0); when the CSP allows no `blob:` worker (`worker-src 'self' blob:`, or `child-src` for Safari 15.4 and older), `workerUrl` points to a self-hosted worker |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Replay quota drains fast | `replaysSessionSampleRate` at 1.0 in production (every session recorded) | Session rate by traffic band; keep on-error at 1.0 | JS session-replay page: Recommended Production Sample Rates; Verify |
| No replay for error sessions | `replaysOnErrorSampleRate` left at its default of 0 | Set it to 1.0 | JS configuration page: General Integration Configuration |
| Replay shows typed or visible text | Masking turned off (`maskAllText: false`); the page reserves this for static sites with no sensitive data | Restore defaults; add `sentry-mask` / `sentry-block` classes or the `mask` / `block` selectors (added to the defaults) | JS privacy page: Privacy Configuration, Masking |
| Network details missing | Headers and bodies are opt-in; only URLs matching `networkDetailAllowUrls` are enriched | Allowlist safe URLs only; use `networkDetailDenyUrls` to exclude | JS configuration page: Network Details |
| Replay missing or blank under strict CSP | Inline compression worker blocked by CSP | Add `worker-src 'self' blob:` (and `child-src 'self' blob:` for Safari 15.4 and older), or self-host the worker and set `workerUrl` | JS session-replay page: Configure CSP; configuration page: Custom Compression Worker |
| Same-origin `srcdoc` iframe is blank | Internal default blocks it, because masking cannot run inside it | Expected; unblock only if the content is safe | JS privacy page: Privacy Configuration |
| Masking selectors stopped matching after an upgrade | Since v8, `unmask` and `unblock` no longer add default selectors | Re-list `.sentry-unmask` and `[data-sentry-unmask]` explicitly | JS privacy page: Privacy Configuration |
| Android masking options ignored | `screenshotStrategy` set to Canvas (experimental) masks everything and disregards `maskAll*` options | PixelCopy unless strict PII requires Canvas | Android session-replay page: Screenshot Strategy |
| Wrong option names copied across platforms | Web names (`replaysSessionSampleRate`) used on iOS or Android, or `options.sessionReplay.*` used on web | Use the names of the platform's page; RN uses web names | iOS, Android, RN session-replay pages: Sampling |
| Error counts differ between replay and issue | Errors lost when the replay was rate limited, deleted, or failed to save | Expected; check the outcome counts before blaming the SDK | JS session-replay page: Error Linking |

## Volume, cost and overhead
- Billed in the Replays category, one unit per replay; each category has its own quota (https://docs.sentry.io/pricing/quotas.md).
- Spike protection does not cover replays: its page covers errors, spans and attachments and does not mention replays. Control replay volume with the sample rates, not spike protection.
- Unsampled web sessions are buffered in memory for the last 60 seconds and discarded; only error-sampled sessions leave the browser (JS: How Sampling Works).
- Web compression runs in a web worker. The inline worker adds to the main bundle; a self-hosted `workerUrl` can be cached separately (configuration page).
- `mutationLimit` (default 10000) stops web recording on heavy DOM churn; the page says recording stops for performance.
- Captured request and response bodies are truncated at 150k characters (configuration page: Network Details).
- Lazy loading (`integrations: []` in init, then `addIntegration(replayIntegration())` later) shrinks startup bundle; the page does not say what is lost before the load.

## Verify (R6)
1. Web test build only: set `replaysSessionSampleRate` to 1.0 (the JS Verify section recommends this during testing), trigger a handled error, open the issue; a replay link must appear (Error Linking). Revert the rate afterwards.
2. Masking proof: type a known string into a text input and into a `sentry-mask` element; in the replay the text must show as `*` characters (JS Masking).
3. Outcome proof: run before and after the test and compare the Replays category outcomes:
```
sentry api -X GET "/organizations/<org>/stats_v2/?field=sum(quantity)&groupBy=category&groupBy=outcome&statsPeriod=1h"
```
The replay category string is not in the fetched docs; record the observed value as C evidence.
4. Mobile: UI-only confirmation (replay under the issue) until the platform page's Verify section is read; mark UNVERIFIED otherwise.

## Sources
- https://docs.sentry.io/platforms/javascript/session-replay.md
- https://docs.sentry.io/platforms/javascript/session-replay/configuration.md
- https://docs.sentry.io/platforms/javascript/session-replay/privacy.md
- https://docs.sentry.io/platforms/react-native/session-replay.md
- https://docs.sentry.io/platforms/apple/guides/ios/session-replay.md
- https://docs.sentry.io/platforms/android/session-replay.md
- https://docs.sentry.io/platforms/dart/guides/flutter/session-replay.md
- https://docs.sentry.io/product/session-replay/mobile.md
- https://docs.sentry.io/pricing/quotas.md
- https://docs.sentry.io/pricing/quotas/spike-protection.md

## Identifiers
```identifiers
replaysSessionSampleRate | https://docs.sentry.io/platforms/javascript/session-replay.md
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/session-replay.md
replayIntegration | https://docs.sentry.io/platforms/javascript/session-replay.md
replayCanvasIntegration | https://docs.sentry.io/platforms/javascript/session-replay.md
addIntegration | https://docs.sentry.io/platforms/javascript/session-replay.md
maskAllText | https://docs.sentry.io/platforms/javascript/session-replay/privacy.md
maskAllInputs | https://docs.sentry.io/platforms/javascript/session-replay/privacy.md
blockAllMedia | https://docs.sentry.io/platforms/javascript/session-replay/privacy.md
workerUrl | https://docs.sentry.io/platforms/javascript/session-replay/configuration.md
networkDetailAllowUrls | https://docs.sentry.io/platforms/javascript/session-replay/configuration.md
networkDetailDenyUrls | https://docs.sentry.io/platforms/javascript/session-replay/configuration.md
mutationLimit | https://docs.sentry.io/platforms/javascript/session-replay/configuration.md
beforeErrorSampling | https://docs.sentry.io/platforms/javascript/session-replay/configuration.md
sessionReplay | https://docs.sentry.io/platforms/apple/guides/ios/session-replay.md
sessionSampleRate | https://docs.sentry.io/platforms/apple/guides/ios/session-replay.md
onErrorSampleRate | https://docs.sentry.io/platforms/apple/guides/ios/session-replay.md
maskAllImages | https://docs.sentry.io/platforms/apple/guides/ios/session-replay.md
screenshotStrategy | https://docs.sentry.io/platforms/android/session-replay.md
mobileReplayIntegration | https://docs.sentry.io/platforms/react-native/session-replay.md
browserReplayIntegration | https://docs.sentry.io/platforms/react-native/session-replay.md
maskAllVectors | https://docs.sentry.io/platforms/react-native/session-replay.md
maskAssetImages | https://docs.sentry.io/platforms/dart/guides/flutter/session-replay.md
```

## Unconfirmed
- `tracePropagationTargets`: research note says unset targets drop backend trace links; no fetched page names it; verify before use.
- `_experiments.autoFlushOnFeedback`: research note says removed in v10; migration page not fetched on 2026-10-20.
- Replay class and `@sentry/replay` package removed in v8, and replay sample rates moved from the integration to init: research note only; migration pages not fetched on 2026-10-20.
- Canvas content is not scrubbed: research note only; the fetched canvas section says nothing on masking on 2026-10-20.
- Replay inbound filters (IP, release, request URL, user-agent): research note only; filtering page not fetched on 2026-10-20.
- Electron replay route: `platforms/electron/session-replay` returned Page Not Found on 2026-10-20; confirm the SDK route before proposing.
- Flutter sampling option names and the Flutter floor: not fetched on 2026-10-20.
- Disagreement, page wins: Cocoa floor is 8.31.1 on the iOS page (Pre-requisites) but 8.43.0 on the mobile product page; Flutter floor is 8.12.0 on the mobile product page but at least 9.0 in the research note; research note says mobile buffers about 30 s, while React Native's page says a minute.
