# Feature flag tracking (product id: flags)

## Fit
Propose when the repo evaluates feature flags with a supported SDK or decides code paths from its own toggles, AND a Sentry SDK is already initialised. The flag data is attached to Sentry events, so without a Sentry SDK there is nothing to attach it to (propose the SDK first). Evidence that raises priority:
- A flag SDK in a manifest: LaunchDarkly, OpenFeature, Statsig or Unleash (the four that have an evaluation integration on both the JavaScript and Python pages). Flagsmith appears only for change tracking.
- Hand-rolled toggles (config or env values that choose a code path) near code that captures errors. The generic API covers these.
- Flag-gated new code paths that have no error tracking yet.

Applicability is the `flags` row of `data/signals.tsv` (signal `sig:flags`). When no flag SDK is detected, the audit skips this product with the reason "no feature-flag SDK detected".

Not worth proposing:
- No flag SDK and no hand-rolled toggles.
- No Sentry SDK in the repo.
- Only multivariate (string or number) flags on JavaScript or Python. The generic API on both pages accepts boolean evaluations only.
- Any claim that this is GA. The product page is headed "Currently in Beta".

## Properly configured
| SDK family | Evaluation tracking (right) | Minimum version stated | Source |
|---|---|---|---|
| JavaScript, generic | `featureFlagsIntegration()` in the `integrations` array of `Sentry.init`; report each evaluation with `addFeatureFlag` on the object from `getIntegrationByName` ("FeatureFlags") | Sentry SDK 8.43.0 | JS featureflags page |
| JavaScript, providers | LaunchDarkly, OpenFeature, Statsig, Unleash integrations | not stated | JS feature-flags page |
| Python, LaunchDarkly | `LaunchDarklyIntegration()` in the `integrations` list | launchdarkly-server-sdk 9.8.0, sentry-sdk 2.19.2, Python 3.8 | Python LaunchDarkly page |
| Python, generic | `add_feature_flag(name, value)` at each evaluation | not stated | Python feature-flags page |
| Python, providers | LaunchDarkly, OpenFeature (several providers), Statsig, Unleash | not stated | Python feature-flags page |
| Apple, Android, PHP | Generic API section on each SDK page (Apple also has Custom Hub, Scope Callback, Clear Feature Flags) | not checked | SDK feature-flags pages |

The product page links eight SDK pages for evaluation tracking: Android, Apple, Dart, Java, JavaScript, PHP, Python, React Native. Use them as the list of supported SDKs.

Rules that apply to every family:
- Generic API: evaluations are held in memory and sent with error and transaction events. Boolean values only (JavaScript and Python pages say "At the moment, we only support boolean flag evaluations").
- Privacy: the Python LaunchDarkly page's sample no longer sets `send_default_pii`; the Python options page documents it (to be removed in 3.0) and `data_collection`. Keep the defaults unless the app already sends request headers and IP. Flag names and values travel with error and transaction events. No fetched page says whether values are sensitive, so judge them under the repo's data-collection settings.
- Change tracking requires evaluation tracking. Register a webhook with the provider (Flagsmith, LaunchDarkly, Statsig, Unleash, or Generic). For LaunchDarkly: in Sentry's feature-flags change-tracking settings, click Add New Provider (one webhook secret per provider type), copy the webhook URL into LaunchDarkly, tick "Sign this webhook", paste the revealed secret into Sentry, then save in both places.
- Sampling, environments and releases: no fetched page sets a rule for flag data. Do not invent one.

## Checks
| check id | read | passes when |
|---|---|---|
| flags.integration | Dependency manifests (`package.json`, `pyproject.toml`, `requirements*.txt`, `go.mod`, `build.gradle` or `build.gradle.kts`, `pom.xml`, `Podfile`, `Package.swift`, `composer.json`, `pubspec.yaml`) for a flag SDK named in Fit. Then the file that calls Sentry init, for the integration (JavaScript: `featureFlagsIntegration`; Python: `LaunchDarklyIntegration`). Then grep the source for `addFeatureFlag` and `add_feature_flag` to find evaluation sites. Org side (org settings feature-flags change-tracking page, UI only): ask the user; without an answer mark UNVERIFIED. | Each flag SDK found is reported: its provider integration appears in the init call, or each hand-rolled evaluation site calls the generic API. JavaScript init uses Sentry SDK 8.43.0 or later. Python LaunchDarkly uses launchdarkly-server-sdk 9.8.0 or later and sentry-sdk 2.19.2 or later. Where change tracking is wanted, the provider's signed webhook is registered (one secret per provider type). The webhook part cannot be proven from the repo, so it stays UNVERIFIED unless the user confirms it. |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| No Feature Flag section on the issue | The integration is missing from the init call, or the JavaScript SDK is below 8.43.0 | Add `featureFlagsIntegration()` (JavaScript) or the provider integration (Python); upgrade the SDK | JS featureflags page; Python LaunchDarkly page |
| Expected flag is missing from an error | The evaluation was not reported, or it happened after the error. The table lists the flags evaluated "leading up to the error" | Report each evaluation where the decision is made | Issue Details feature-flags page |
| Multivariate flag absent or wrong | Generic API is boolean only | Track a boolean flag, or use the provider integration where one exists | JS featureflags page; Python feature-flags page |
| Change lines never appear | Evaluation tracking is off (change tracking needs it), or the webhook is missing or unsigned | Enable evaluation tracking; register the webhook and tick "Sign this webhook" | Issue Details feature-flags page; LaunchDarkly org page |
| Webhook not accepted | Signing was not enabled, or the pasted secret differs from the one LaunchDarkly shows | Re-copy the secret; keep one secret per provider type | LaunchDarkly org page |
| Request headers and IP sent after copying a sample | The app, or an older sample, sets `send_default_pii=True` | Leave it off unless the app already sends that data | Python options page |

## Volume, cost and overhead
- Flag data rides on error and transaction events (JavaScript and Python generic pages). The fetched pages name no separate billing category. The research notes say "no separate billing"; that is not confirmed (see Unconfirmed).
- Bounded per event: the 100 most recently evaluated flags before the error (Issue Details page).
- Disagreement: the research notes say the last 100 evaluations are recorded "on each error". The docs say "each event", and the generic pages add transactions. Follow the docs.
- Change tracking writes one audit-log entry per definition change (Issue Details page). Its cost is not stated.
- Runtime: evaluations are held in memory until an event is sent. No overhead figure is stated on the pages.
- No pay-as-you-go budget is implied by the fetched pages. Confirm the billing category before saying so.

## Verify (R6)
1. Generic proof (JavaScript: `addFeatureFlag` on the integration; Python: `add_feature_flag`): on a non-production build, record a throwaway boolean flag, capture an exception, open the issue. The Feature Flag section shows the name and value. Remove the test call afterwards.
2. Real evaluation: trigger the error path behind a flag. The table lists the flags evaluated before the error; a suspect flag is highlighted yellow.
3. Issues Search: the `flags` keyword filters for errors where a flag evaluated true or false. The search syntax is on the searchable-properties page (not fetched).
4. Change tracking: change the flag in the provider. The audit-log change shows as a release-like line on the event chart, for flags evaluated before the error.

No CLI or API route for flag evaluations was verified on a fetched page, so the proof is on the event in the UI.

## Sources
- https://docs.sentry.io/product/issues/issue-details/feature-flags/
- https://docs.sentry.io/platforms/javascript/feature-flags/
- https://docs.sentry.io/platforms/javascript/configuration/integrations/featureflags/
- https://docs.sentry.io/platforms/python/feature-flags/
- https://docs.sentry.io/platforms/python/integrations/launchdarkly/
- https://docs.sentry.io/platforms/apple/feature-flags/
- https://docs.sentry.io/platforms/android/feature-flags/
- https://docs.sentry.io/platforms/php/feature-flags/
- https://docs.sentry.io/organization/integrations/feature-flag/
- https://docs.sentry.io/organization/integrations/feature-flag/launchdarkly/
- https://docs.sentry.io/platforms/python/configuration/options.md

## Identifiers
```identifiers
featureFlagsIntegration | https://docs.sentry.io/platforms/javascript/configuration/integrations/featureflags/
addFeatureFlag | https://docs.sentry.io/platforms/javascript/configuration/integrations/featureflags/
getIntegrationByName | https://docs.sentry.io/platforms/javascript/configuration/integrations/featureflags/
add_feature_flag | https://docs.sentry.io/platforms/python/feature-flags/
LaunchDarklyIntegration | https://docs.sentry.io/platforms/python/integrations/launchdarkly/
send_default_pii | https://docs.sentry.io/platforms/python/configuration/options.md
data_collection | https://docs.sentry.io/platforms/python/configuration/options.md
```

## Unconfirmed
- Apple minimum SDK version (9.22 in the research notes): could not find it in an official page on 2026-10-20; verify before use.
- Java, Dart (Flutter) and React Native provider lists, and the Flutter Firebase Remote Config route (from the research notes): not checked on the SDK pages on 2026-10-20.
- Minimum SDK versions for the Python generic API and for Apple, Android and PHP generic APIs: not stated on the fetched pages on 2026-10-20.
- Separate billing category for flag data ("no separate billing" in the research notes): could not confirm on a fetched page on 2026-10-20.
- Flag values being sensitive: no fetched page says so on 2026-10-20.
- Org-side flag audit-log endpoint (`/organizations/{o}/flags/logs/`, undocumented per the research notes): not on any official page on 2026-10-20.
