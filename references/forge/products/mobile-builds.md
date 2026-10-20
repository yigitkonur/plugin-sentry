# Mobile build tooling (product id: mobile-builds)

## Fit
Three products share this module: Size Analysis (GA), Snapshots (Beta, page banner) and Build Distribution (no Beta notice on the docs page read on 2026-10-20; see Gotchas). Signal: data/signals.tsv row `mobile-builds` is conditional on role:mobile ("not a mobile app" excludes it). Propose only when the repo builds an app binary.

Worth proposing when the repo shows:

| Evidence in repo | Points to |
|---|---|
| `build.gradle*` applying the Android application plugin; `android/app/` (React Native, Flutter) | Size Analysis (Gradle or CLI), Build Distribution (Android) |
| Xcode project or workspace with an app target; `ios/` (React Native, Flutter) | Size Analysis (XCArchive or IPA), Build Distribution (iOS) |
| `Fastfile` lanes that build an AAB, IPA or archive | Size Analysis or Build Distribution via Fastlane |
| CI job running `bundleRelease`, `xcodebuild archive` or a release build of the app | A CI upload step is possible; Size Analysis fits |
| Screenshot tests (Paparazzi, Playwright or other image tools) and GitHub pull requests | Snapshots (Beta) |
| Testers who install outside the store (internal channels, Android auto-update SDK) | Build Distribution |

Not worth proposing:
- No app target: SDK, library, backend or web-only repo (the signal excludes these).
- App built only on developer machines; no CI job produces a release artifact, so nothing to upload.
- Snapshots: no screenshot generation, or no GitHub (status checks and PR comments are GitHub-only).
- Build Distribution: testers already served by the store tracks and no out-of-store channel.
- No org access: upload needs an org/project token; every org-side result is UNVERIFIED, never n/a.

## Properly configured
Size Analysis (GA):

| Route | Artifact to upload | Tooling | Right |
|---|---|---|---|
| Android, Gradle | AAB from the release variant | Sentry Gradle plugin >= 6.24.0; `sizeAnalysis` enabled only on CI; `SENTRY_AUTH_TOKEN` from env | Task `./gradlew bundleRelease`; release variant not in `ignoredVariants`, `ignoredBuildTypes` or `ignoredFlavors`; `vcsInfo` set where CI is not GitHub Actions |
| Android, CLI | AAB (preferred) or APK | sentry-cli 3.8.0 recommended, minimum 2.58.2 | `sentry-cli build upload app.aab --org <org> --project <project> --build-configuration Release` |
| iOS, CLI | XCArchive (preferred) or IPA | sentry-cli 3.8.0 recommended, minimum 2.58.2 | `sentry-cli build upload app.xcarchive ... --build-configuration Release` |
| iOS, Fastlane | XCArchive or IPA | Fastlane route on the iOS guide | Take the exact action from platforms/apple/guides/ios/size-analysis (only headings read here) |
| React Native, Flutter | Per platform guide | Linked from product/size-analysis | Not read in this pass; use the linked guide |

Metadata on every route: `build-configuration` (required); `base-sha` = the branch merge-base for comparisons; `head-sha` = current commit; `vcs-provider` (auto-detected from the git remote; only github and github_enterprise get status checks); `pr-number` on PR builds. Triggers: the docs example uploads on push to main and release/*; PR uploads are what produce PR status checks. Each upload counts against the build allowance.

Build Distribution:
- Android Gradle: `distribution { enabled }` gated like Size Analysis (CI only, same variant filters). Distributed Android build: an APK signed with one stable key (see Common mistakes).
- iOS: platforms/apple/guides/ios/build-distribution (Fastlane and CLI sections; headings only read here).

Snapshots (Beta): sentry-cli 3.5.0 or later; `sentry-cli snapshots upload` on the snapshot directory from CI; token with `project:write` (personal) or `org:ci` (org); Sentry GitHub App installed for PR status checks. Recommended workflows exist for iOS, Android and Flutter (linked from product/snapshots).

Monitors (Mobile Builds monitor settings, UI only): Absolute Size, Absolute Diff or Relative Diff on Install/Uncompressed or Download size. Diff baseline is the most recent build with the same platform, package_name, build_configuration and filters.

## Checks
| check id | read | passes when |
|---|---|---|
| x.size-analysis-trigger | CI files (`.github/workflows/*.yml`, `.gitlab-ci.yml`, `bitrise.yml`, `codemagic.yaml`, `Fastfile`): the step that runs the Gradle AAB task or `sentry-cli build upload`, and its branch/PR trigger | Uploads come from PRs (status checks) and from main or release branches (baselines); the token comes from a secret or env var, never a literal in the file |
| x.size-analysis-artifact | The upload step's file argument (`app.aab`, `app.xcarchive`, `app.ipa`) and the release build task | Android uploads the AAB; no APK upload when R8 or ProGuard is on (APK uploads cannot correlate the mapping); iOS uploads the XCArchive (IPA only where no archive exists) |
| x.size-analysis-gradle | `build.gradle*`, `settings.gradle*`, `libs.versions.toml`: the Sentry Gradle plugin version and the `sentry {}` block (`sizeAnalysis`, `vcsInfo`, `ignoredVariants`, `ignoredBuildTypes`, `ignoredFlavors`) | Plugin >= 6.24.0; `sizeAnalysis` enabled only on CI (docs gate on `GITHUB_ACTIONS`); the release variant is not excluded by an ignored* filter; `vcsInfo` set on non-GitHub CI |
| x.size-analysis-metadata | Upload command flags (`--build-configuration`) and the `base-sha` / `head-sha` values CI passes | `build-configuration` on every upload and one value per variant (debug never compared with release); `base-sha` is the PR branch merge-base |
| x.build-distribution-signing | Android signing configs in `build.gradle*`; the Build Distribution upload command or `distribution` block | A build meant for in-place updates is an APK signed with one stable key; AABs are not used for it (each AAB upload is re-signed with a unique key) |
| x.snapshots-cli-token | CI step running `sentry-cli snapshots upload`; `sentry-cli --version` in CI logs or lockfile; token scope and GitHub App install (Sentry UI, ask the user, else UNVERIFIED) | sentry-cli >= 3.5.0; token has `project:write` (personal) or `org:ci` (org); GitHub App installed on the repo |
| x.mobile-builds-monitor | Settings > Mobile Builds in Sentry (UI only; ask the user, else UNVERIFIED) | Release line has a threshold monitor on its cadence (nightly or release); optional, not required for the other rows |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Size Analysis says "Missing ProGuard mapping" though the mapping uploaded | APK uploaded; APK uploads do not support R8 mapping correlation | Upload the AAB for Size Analysis | platforms/android/size-analysis, Troubleshooting |
| Tester cannot update an installed Android build from Build Distribution | AAB converted to a universal APK signed with a unique key per upload | Upload an APK signed with one stable key; keep AAB for Size Analysis | platforms/android/build-distribution |
| Huge size deltas between a PR and main | Debug and release (or flavors) compared; `build-configuration` missing or inconsistent | Set one `build-configuration` per variant; comparisons only match the same configuration | platforms/android/size-analysis, Build Configuration |
| Gradle upload never runs, build is green | Release variant excluded by `ignoredVariants`, `ignoredBuildTypes` or `ignoredFlavors`, or `sizeAnalysis` disabled on CI | Remove the exclusion for the CI variant; enable on CI | platforms/android/size-analysis |
| No PR status check | `vcs-provider` not github or github_enterprise; GitHub App not installed | Install the Sentry GitHub App; check `vcs-provider` | product/size-analysis, Upload Metadata; integrating-into-ci, Not Seeing Status Checks |
| Comparison against the wrong build | `base-sha` is not the merge-base | Pass the branch merge-base as `base-sha` | product/size-analysis, Upload Metadata |
| Uploads stop mid-period | Included builds used up; more builds only on an Enterprise plan | Limit triggers to PRs and main/release | pricing |
| `snapshots upload` fails | sentry-cli below 3.5.0 | Upgrade sentry-cli | product/snapshots, Prerequisites |
| Snapshot upload rejected (auth) | Token lacks `project:write` (personal) or `org:ci` (org) | Use a token with the right scope | product/snapshots, Prerequisites |

## Volume, cost and overhead
| Product | Status | Billed as | Included | Beyond |
|---|---|---|---|---|
| Size Analysis | GA | Builds per billing period | 100 per organization, on every plan | Enterprise plan only |
| Build Distribution | Not Beta on the docs page read; research note says Beta | UNVERIFIED (not on the pricing page under this name) | UNVERIFIED | UNVERIFIED |
| Snapshots | Beta | UNVERIFIED (not on the pricing page under this name) | UNVERIFIED | UNVERIFIED |

- Size Analysis and Snapshots uploads run in CI; the docs describe no in-app component for them.
- Build Distribution's Android auto-update SDK runs inside the app; its overhead is not documented on the pages read.
- Plan for the 100-build allowance before enabling uploads on every branch. The product page says "100 builds per month"; the pricing page says "per billing period". The pricing page is used here.

## Verify (R6)
A zero exit from `sentry-cli build upload` is not proof. Open the build in Sentry (Mobile Builds) and confirm:
1. `build-configuration` shows the intended value (Release) and `head-sha` matches `git rev-parse HEAD` in CI.
2. Android: the upload is an AAB and the Dex breakdown shows deobfuscated class names; no "Missing ProGuard mapping" message.
3. PR: a second upload with the same `build-configuration` produces a comparison, and a GitHub status check appears on the PR.
4. Snapshots: the PR shows a snapshot status check; approve from the PR or the Sentry UI.
5. Build Distribution (Android): install a new build over the previous installed build; it updates only when both use the same signing key.
These are UI observations; record them as UNVERIFIED unless the user confirms.

## Sources
- https://docs.sentry.io/product/size-analysis/
- https://docs.sentry.io/product/size-analysis/integrating-into-ci/ (headings only)
- https://docs.sentry.io/platforms/android/size-analysis/
- https://docs.sentry.io/platforms/apple/guides/ios/size-analysis/
- https://docs.sentry.io/product/build-distribution/
- https://docs.sentry.io/platforms/android/build-distribution/
- https://docs.sentry.io/platforms/apple/guides/ios/build-distribution/ (headings only)
- https://docs.sentry.io/product/snapshots/
- https://docs.sentry.io/product/monitors-and-alerts/monitors/
- https://docs.sentry.io/pricing/

## Identifiers
```identifiers
sizeAnalysis | https://docs.sentry.io/platforms/android/size-analysis/
vcsInfo | https://docs.sentry.io/platforms/android/size-analysis/
ignoredVariants | https://docs.sentry.io/platforms/android/size-analysis/
ignoredBuildTypes | https://docs.sentry.io/platforms/android/size-analysis/
ignoredFlavors | https://docs.sentry.io/platforms/android/size-analysis/
bundleRelease | https://docs.sentry.io/platforms/android/size-analysis/
GITHUB_ACTIONS | https://docs.sentry.io/platforms/android/size-analysis/
SENTRY_AUTH_TOKEN | https://docs.sentry.io/platforms/android/size-analysis/
--build-configuration | https://docs.sentry.io/platforms/android/size-analysis/
build-configuration | https://docs.sentry.io/product/size-analysis/
base-sha | https://docs.sentry.io/product/size-analysis/
head-sha | https://docs.sentry.io/product/size-analysis/
vcs-provider | https://docs.sentry.io/product/size-analysis/
pr-number | https://docs.sentry.io/product/size-analysis/
project:write | https://docs.sentry.io/product/snapshots/
org:ci | https://docs.sentry.io/product/snapshots/
sentry-cli | https://docs.sentry.io/cli/
```

## Unconfirmed
- `distribution` (Gradle block for Build Distribution): taken from the Android Build Distribution page text; re-check the exact block name before quoting it.
- Build Distribution and Snapshots billing: not found on https://docs.sentry.io/pricing/ under these names on 2026-10-20; verify before quoting any limit.
- Build Distribution iOS CLI version (research note says sentry-cli 3.8): iOS Build Distribution CLI section not read; verify.
