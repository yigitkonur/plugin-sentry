# User Feedback (product id: feedback)

## Fit
Propose when the repo has a user-facing client unit: a browser front end, a React Native, Flutter, iOS or Android app, or a desktop or game client. The applicability rule in data/signals.tsv (row `feedback`: mode `cond`, applies when `client`, na_reason "not user-facing") gates it. A backend-only repo gets n/a, not a finding.

Evidence that raises priority:
- A "report a problem", "contact support" or feedback form that posts to a custom sink (mail handler, webhook, Slack, a table). Route it to Sentry instead of adding a second form beside it.
- A server-rendered error page (500 template) on a site that already loads the browser SDK. This is the crash-report modal's use case.
- Session Replay already on in the browser init (`replaysOnErrorSampleRate` above 0). Feedback then links a replay.
- A mobile app with a help or settings screen where a form can live.

Not worth proposing:
- Backend-only repos (API, worker, CLI, library with no UI).
- A client that already has another vendor's feedback widget and no decision to switch. Do not stack two widgets.
- A Python-only backend with no browser JavaScript on its error pages. The fetched Python page documents only the crash-report modal, and Python is not on the supported-SDK list for the feedback API (see Common mistakes).
- No org access: the SDK side can still be audited, but where feedback lands and which alerts exist stay UNVERIFIED.

## Properly configured
Right = what the auditor should find in code. Browser entries use `feedbackIntegration`; other families are listed per SDK.

| SDK family | Right | Source |
|---|---|---|
| Browser, NPM | `feedbackIntegration({...})` in the `integrations` array of the init call; `@sentry/browser` or the framework SDK at 7.85.0 or later. NPM default is `feedbackSyncIntegration`, which ships the form in the bundle. `autoInject` stays true unless the app supplies its own button | JS user-feedback page "Set Up"; configuration "Loading Strategies" |
| Browser, CDN | A bundle with feedback in it (`bundle.feedback.min.js`, or the tracing, replay and feedback bundle). `feedbackIntegration` aliases `feedbackAsyncIntegration` here: the form loads from the Sentry CDN on click, so an ad blocker can stop it | configuration "When Installed Via CDN" |
| Browser, custom UI | `autoInject: false`, then `getFeedback()?.createWidget()` and `appendToDom()` to place the button; `removeFromDom()` on teardown. Or `captureFeedback({message, ...})` from your own form, with `associatedEventId` set | configuration "Auto-Inject vs. Manual Injection"; JS page "User Feedback API" |
| Browser, fields | `showName` and `showEmail` default true; `isNameRequired` and `isEmailRequired` default false. Set them on purpose. `useSentryUser` maps the `setUser` name and email into the form | configuration "User and Form" |
| Browser with Replay | `replaysOnErrorSampleRate` above 0 in the init call, so a widget submission carries a replay. The SDK buffers up to 30 seconds until the widget opens | JS page "Session Replay" |
| Crash-report modal | `showReportDialog({eventId})` in the framework error component, or in `beforeSend` as the docs example does. The event id comes from the backend; the modal authenticates with the public DSN | JS page "Crash-Report Modal" |
| Python | Put `sentry_sdk.last_event_id()` into the 500 template and load the browser bundle on that page. This is the documented Python route | Python page "Crash-Report Modal" |
| React Native | `<FeedbackForm />` component; `feedbackIntegration({enableShakeToReport: true})` or `enableFeedbackOnShake()`; `captureFeedback` with `associatedEventId` for your own UI. Offline feedback is stored and sent when back online | RN page "Feedback Form Component", "Shake to Report", "User Feedback API" |
| Apple (Cocoa) | `configureUserFeedback` in the start call. It is required for `SentrySDK.feedback.show()` and for global shake and screenshot triggers. Swift presentation APIs need Cocoa 9.17.0 or newer, are experimental, and are not available in app extensions | Apple page "Managed Feedback Form" |
| Android | `options.feedbackOptions.isUseShakeGesture = true` in `SentryAndroid.init` for global shake, which is off by default. Per screen: `SentryUserFeedbackForm.Builder(activity)` with the same flag, only while global shake is off | Android page "Shake to Report", "User Feedback Form" |
| Other SDKs with an API | Dart and Flutter, .NET, Java, Kotlin, Node.js, Unity and Unreal are on the supported list for the feedback API; use that platform's "User Feedback API" section | setup page "Supported SDKs for User Feedback API" |

Privacy (PII), from the product page "User Feedback Widget" and the configuration page:
- A widget submission can carry the message, a screenshot, the user's email, the associated replay, the page URL and tags. The crash-report modal collects name, email and description.
- `useSentryUser` prefills name and email from `setUser`. A hidden field (`showName` or `showEmail` false) still sends its prefilled value with the message. Right: map only the fields you mean to send.
- Screenshots default to on in browser SDK v8 and later (`enableScreenshot`). Turn them off on screens that show account, payment or health data. The button is hidden on mobile. Self-hosted Sentry needs release 24.4.2 or later for screenshots. How screenshot content is masked is not on any fetched page (see Unconfirmed).
- Spam: with Generative AI Features enabled on the org, likely spam goes to the Spam folder and does not alert. Opt-out is "Enable Spam Detection" in the project's User Feedback settings.

Where feedback lands: it is an issue category named Feedback. Right: the default "Alert me on every new issue" covers it; otherwise one alert with Issue Category equal to Feedback. Crash-report feedback needs "Enable Crash Report Notifications" in the project's User Feedback settings. Per-feedback GitHub or Jira issues come from an alert action. `onSubmitSuccess` can deep-link to the saved item (URL pattern on the configuration page).

## Checks
| check id | read | passes when |
|---|---|---|
| fb.widget | Run `grep -rn` for each of: `feedbackIntegration`, `captureFeedback`, `showReportDialog`, `configureUserFeedback`, `isUseShakeGesture`, `FeedbackForm`, `last_event_id`, `SentrySDK.feedback` (skip node_modules, Pods, build, .git). Open the file that holds the init call (browser or RN entry, the Swift start call, `SentryAndroid.init`) and the 500 template if one exists. Read the SDK version from package.json (browser and RN, 7.85.0 or later) and Podfile.lock or Package.resolved (Cocoa 9.17.0 or later if `SentrySDK.feedback.show()` is called). If grep finds nothing, grep README.md, CLAUDE.md and docs/ for "feedback" to look for a recorded exclusion | Each user-facing client unit has one entry point that reaches a visible control: a `feedbackIntegration` entry in the integrations array with `autoInject` not false, or a `captureFeedback`, `FeedbackForm`, `SentrySDK.feedback.show()` or `SentryUserFeedbackForm` call behind a button or screen, or `showReportDialog` on a rendered error page; the SDK version meets the minimum above; or the repo holds a dated decision to exclude that unit. An imported but never-added integration, or hits only in tests, is a fail. No hits and no recorded decision is a fail |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| No widget on a page that has the browser SDK | `feedbackIntegration` never added to the integrations array, or the browser lacks Shadow DOM or the dialog element | Add the integration; check the browser prerequisites | JS page "Pre-requisites" |
| Feedback arrives with no replay | `replaysOnErrorSampleRate` is 0 or Session Replay is not configured | Set the rate above 0 | JS page "Session Replay" |
| Feedback not paired with the error | `associatedEventId` omitted, or the id read before capture finished | Use the id returned by the capture call, or `lastEventId()` inside `beforeSend` | JS page "User Feedback API" |
| Hidden email field still sent | `useSentryUser` prefill with `showEmail` false | Remove the mapping for fields you do not send | configuration "User Context" |
| Attachments quota drains | Screenshots on by default in browser SDK v8 and later | `enableScreenshot: false` on sensitive screens | JS page "User Feedback Widget" |
| Feedback without alerts | No alert with Issue Category equal to Feedback, or the item is spam (spam does not alert) | Add the alert; check the Spam folder | product page "Getting User Feedback Alerts", "Spam Detection" |
| Handler breaks after upgrade | `onSubmitSuccess` took only data in v9 and below; the current signature adds an event ID argument | Update the callback signature | configuration "Event Callbacks" |
| Apple build calls `showWidget()` or `customButton` | Deprecated; the page says both are removed in v10 | Use a button that calls `SentrySDK.feedback.show()` | Apple page "Deprecated Widget and Custom Button Setup" |
| Shake works on some screens only | Global shake is off by default; per-form shake works only then | Choose one: global flag, or per-form Builder | Android page "Per-Form Shake" |
| Custom code POSTs to the user-feedback Web API | Endpoint is deprecated for new users; it accepts feedback only within 30 minutes of the event save, and returns 409 after the mutability threshold | Use the SDK feedback API; use the endpoint only with no JS frontend and no SDK feedback API | API page "Submit User Feedback" |

Source disagreements (the page wins; this file follows the page):
- Replay buffer: the product page says up to 60 seconds of replay before submit; the browser platform page says the SDK buffers up to 30 seconds until the widget opens.
- Python: the research notes name a "Python API". The supported-SDK list on the setup page has no Python entry, and the Python page documents only the crash-report modal.

## Volume, cost and overhead
| Item | Right | Source |
|---|---|---|
| Screenshots | Bill to the Attachments quota (GB). 1 GB is included on all plans, about 2500 screenshots per the docs. Turn off where not needed | JS page "User Feedback Widget"; quota module |
| Linked replay | Comes from Session Replay; the Replays row of the quota module applies. It exists only when `replaysOnErrorSampleRate` is above 0 | JS page "Session Replay" |
| Bundle weight | NPM default `feedbackSyncIntegration` ships the form up front; CDN default `feedbackAsyncIntegration` fetches it on click. Choose deliberately on size-sensitive pages | configuration "Loading Strategies" |
| Network at submit | Browser submission needs connectivity; React Native stores offline feedback and sends it later | configuration "Feedback Form"; RN page |
| Feedback item itself | Billing category not stated on fetched pages (see Unconfirmed); check Usage Stats before quoting a number | none |
| Pay-as-you-go | No fetched page says feedback needs a PAYG budget. Attachments and replays beyond included volume follow the quota module | quota module |

## Verify (R6)
1. Send one marked submission from the real code path in a dev or staging build: the widget button, or the `captureFeedback` call from your own form, passing `associatedEventId` from a real captured error. Find it in the project's User Feedback view (issue category Feedback). Expect the message, the linked event, a replay when `replaysOnErrorSampleRate` is above 0, and a screenshot only in a browser with `enableScreenshot` on.
2. Check the name and email on the entry equal what the form showed or prefilled. A hidden field with a prefilled value is the leak to look for.
3. Crash-report modal: throw on a test route, confirm the modal appears with the event id, submit, and confirm the entry pairs with that event.
4. Remove the marked call and resolve or delete the test entry.
5. Routing: confirm one alert with Issue Category equal to Feedback, or the default new-issue alert. The fetched pages show this only in the UI, so ask the user or mark it UNVERIFIED.

## Sources
- https://docs.sentry.io/product/user-feedback/
- https://docs.sentry.io/product/user-feedback/setup/
- https://docs.sentry.io/platforms/javascript/user-feedback/
- https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
- https://docs.sentry.io/platforms/react-native/user-feedback/
- https://docs.sentry.io/platforms/apple/user-feedback/
- https://docs.sentry.io/platforms/android/user-feedback/
- https://docs.sentry.io/platforms/python/user-feedback/
- https://docs.sentry.io/api/projects/submit-user-feedback/

## Identifiers
```identifiers
feedbackIntegration | https://docs.sentry.io/platforms/javascript/user-feedback/
feedbackSyncIntegration | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
feedbackAsyncIntegration | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
captureFeedback | https://docs.sentry.io/platforms/javascript/user-feedback/
associatedEventId | https://docs.sentry.io/platforms/javascript/user-feedback/
showReportDialog | https://docs.sentry.io/platforms/javascript/user-feedback/
replaysOnErrorSampleRate | https://docs.sentry.io/platforms/javascript/user-feedback/
lastEventId | https://docs.sentry.io/platforms/javascript/user-feedback/
beforeSend | https://docs.sentry.io/platforms/javascript/user-feedback/
eventId | https://docs.sentry.io/platforms/javascript/user-feedback/
enableScreenshot | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
autoInject | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
showName | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
showEmail | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
isNameRequired | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
isEmailRequired | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
useSentryUser | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
setUser | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
onSubmitSuccess | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
getFeedback | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
createWidget | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
appendToDom | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
removeFromDom | https://docs.sentry.io/platforms/javascript/user-feedback/configuration/
FeedbackForm | https://docs.sentry.io/platforms/react-native/user-feedback/
enableShakeToReport | https://docs.sentry.io/platforms/react-native/user-feedback/
enableFeedbackOnShake | https://docs.sentry.io/platforms/react-native/user-feedback/
configureUserFeedback | https://docs.sentry.io/platforms/apple/user-feedback/
SentrySDK | https://docs.sentry.io/platforms/apple/user-feedback/
showWidget | https://docs.sentry.io/platforms/apple/user-feedback/
customButton | https://docs.sentry.io/platforms/apple/user-feedback/
isUseShakeGesture | https://docs.sentry.io/platforms/android/user-feedback/
feedbackOptions | https://docs.sentry.io/platforms/android/user-feedback/
SentryAndroid | https://docs.sentry.io/platforms/android/user-feedback/
SentryUserFeedbackForm | https://docs.sentry.io/platforms/android/user-feedback/
last_event_id | https://docs.sentry.io/platforms/python/user-feedback/
sentry_sdk | https://docs.sentry.io/platforms/python/user-feedback/
```

## Unconfirmed
- `captureUserFeedback`: JS call said to be removed in v9 (research notes only); not found on a fetched official page (2026-10-20).
- `sendFeedback`: said to always reject in v11 (research notes only); not found on a fetched official page (2026-10-20).
- `showFeedbackForm`: React Native, said to need `Sentry.wrap` (research notes only); the fetched RN page documents `FeedbackForm` and `enableFeedbackOnShake()` instead.
- `sentry_capture_feedback` and `sentry_capture_user_feedback`: native C API; research notes only, native page not fetched.
- `SentryFeedbackForm`: Flutter widget name; research notes only, Flutter page not fetched.
- Screenshot masking: no fetched page says how screenshot content is masked. Verify on the docs before recommending any masking setting.
- Billing category of a feedback item (which quota row it counts toward): not stated on any fetched page.
- Python feedback API: none documented on the fetched pages; treat the Web API as deprecated.
