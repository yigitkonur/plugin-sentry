# Errors (product id: errors)

Concepts: references/upstream/concepts/errors, references/upstream/concepts/data-scrubbing, references/upstream/concepts/reduce-volume.

## Fit

- Always proposed for any unit with an SDK. Errors is the base product: unhandled exceptions are captured with no option, and Python's docs call Issues "always enabled".
- Evidence to audit: init file(s), framework error hooks (Next.js `instrumentation.ts`, `app/global-error.tsx`, Express/Fastify/Gin/ASP.NET wiring), `beforeSend`-style hooks, ignore lists, `CODEOWNERS` file, ownership rules in the project.
- Not worth proposing: ignore lists for a project with no event history (no noise to measure yet); `sampleRate` below 1.0 (see Volume); `err.ownership` on a free org (Code Owners import needs a Business or Enterprise plan; ownership rules themselves still work).
- Out of scope here: scrubbing (module privacy), release strings and source maps (modules releases, debug-artifacts), quota controls (module quota).

## Properly configured

| Family | Capture path that must exist | Noise / expected-error control (docs name) |
|---|---|---|
| JS browser (v11) | Init in the earliest client file; React 19 root `onUncaughtError`/`onCaughtError`/`onRecoverableError` set to `reactErrorHandler()` plus `ErrorBoundary` per subtree | `ignoreErrors` (strings match part of the message, regex for exact), `denyUrls`/`allowUrls` (match the top stack frame URL, not the page URL), `thirdPartyErrorFilterIntegration` (needs a bundler plugin `applicationKey`, `filterKeys` equal to it; browser SDKs from 8.10.0) |
| Next.js (`@sentry/nextjs` 11) | `instrumentation.ts` exports `onRequestError` = `Sentry.captureRequestError` (needs `@sentry/nextjs` 8.28.0+ and Next.js 15); `app/global-error.tsx` calls `Sentry.captureException`; Pages Router adds `pages/_error.tsx`; Server Actions wrapped in `withServerActionInstrumentation` | same options as browser for the client file |
| Node: Express / Fastify (JS v11) | `expressIntegration` / `fastifyIntegration` capture route and hook errors automatically; 3xx/4xx are skipped | `shouldHandleError` passed to the integration decides what counts; with a custom error middleware that also captures, set `shouldHandleError: false` |
| Python 2.x / 3.0 alpha | Flask/Django integrations auto-enable when the package is installed; init as early as possible | `ignore_errors` (exception class names, subclasses included), `error_sampler`, `before_send`; ignoring a noisy logger is the documented fix for error-log spam |
| Go | `sentrygin` middleware on the Gin engine | `IgnoreErrors`, `BeforeSend` |
| .NET | `UseSentry` on the web host (ASP.NET Core) | `AddExceptionFilterForType`, `BeforeSend` |
| Ruby | Rails integration | `excluded_exceptions` (append with `+=` rather than overwrite the defaults), `before_send` |
| Java / Android | SDK init | `ignoredErrors` (property `ignored-errors`; string entries are FULL matches, unlike JS), `beforeSend` |
| PHP | `\Sentry\init` | `ignore_exceptions` (type or subtype), `before_send` |
| Apple (Cocoa 9) | SDK start | `beforeSend` only on the filtering page |
| Rust | `sentry::init` | `before_send` |

Grouping: leave the default fingerprint unless one bug shows as many issues or many bugs as one. Order of tools: Fingerprint Rules / Stack Trace Rules in project settings (no deploy), then SDK-side `setFingerprint` or an `event.fingerprint` set in `beforeSend`. `{{ default }}` keeps the generated hash inside a custom fingerprint. Changes affect future events only.

Ownership: `type:pattern owners` rules (`path`, `module`, `url`, `tags.TAG_NAME`; glob, not regex; owners are emails or `#team`). Evaluation order is code owners then ownership rules; the LAST matching rule wins and the first owner on it is assigned. Code Owners need code mappings (stack trace linking) imported first; rules whose users/teams have no mapping are ignored silently; CODEOWNERS max 3MB; GitLab-only syntax (sections, `!`) is unsupported.

## Checks

| check id | read | passes when |
|---|---|---|
| err.boundaries | Next.js: `instrumentation.ts`, `app/global-error.tsx`, `pages/_error.tsx`; React: root `createRoot`/`hydrateRoot` options and `ErrorBoundary` usage; Express/Fastify: init file and error middleware; Gin: router setup; ASP.NET: `Program.cs`/host builder; `stale-apis/js.tsv` for the installed major | Every framework hook the platform module lists exists and is reachable. JS v11 Express/Fastify: no `setupExpressErrorHandler`/`setupFastifyErrorHandler` call (deprecated, errors are captured automatically; keeping both risks duplicates). Custom error middleware that captures also sets `shouldHandleError: false`. React: no second manual capture of what `ErrorBoundary` already reports (dev mode double reports; judge on a production build) |
| err.noise | Ignore lists and `beforeSend` in the init files; if org access: `sentry api /api/0/projects/<org>/<project>/filters/` and `.../custom-inbound-filters/`; `sentry issue list <org>/<project> -q 'is:unresolved' --json --fields title,count` sorted by count | Client unit: `ignoreErrors`/`denyUrls`/`thirdPartyErrorFilterIntegration` or inbound filters cover the top repeating non-actionable titles (browser extensions, crawlers, legacy browsers, chunk-load, hydration). Entries are specific: no bare substring such as `Error` or `Network` that hides real bugs; Java string entries are written as full messages. Org side: every inbound filter you rely on is `active`, and a filter you disabled has a reason. No finding when there is no noisy history to point at |
| err.expected-as-error | Server error handlers, framework status handling, `shouldHandleError` or equivalent, `captureException` calls inside `catch` blocks for validation/auth/not-found | 4xx and domain-validation outcomes are not captured as errors (framework default or an explicit filter); 401/403 are captured only on purpose. `excluded_exceptions`/`ignore_errors`/`ignore_exceptions` hold the expected exception classes. Handled exceptions that are captured explicitly carry tags or context, not just a bare message |
| err.ownership | `CODEOWNERS` in the repo; `sentry api /api/0/projects/<org>/<project>/ownership/` (fields `raw`, `autoAssignment`, `codeownersAutoSync`) and `.../codeowners/` | Ownership rules or an imported CODEOWNERS exist with code mappings behind them; owners resolve to real users/teams; a chosen `autoAssignment` mode matches the team's intent. On a plan without Code Owners, ownership rules in project settings count instead |

## Common mistakes

| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Same error twice per request | Framework integration plus a manual `captureException` in error middleware, or `setupExpressErrorHandler` kept on JS v11 | Remove the manual capture or set `shouldHandleError: false`; drop the deprecated setup call | Express guide; stale-apis/js.tsv |
| Every 404/validation failure is an issue | Catch blocks capture control-flow exceptions; custom `shouldHandleError` returns true for 4xx | Return false below 500 (or the documented status list), add the class to the ignore list | Express/Fastify pages |
| `ignoreErrors` entry hides real bugs | Strings match part of the message | Anchored regex for exact match | JS filtering page |
| `denyUrls` does nothing for a page URL | It matches the script URL in the stack frame, not the page | Filter in `beforeSend` on `event.request.url`, or use an inbound filter | JS options page |
| `thirdPartyErrorFilterIntegration` drops everything or nothing | Bundler plugin `applicationKey` missing or different from `filterKeys`; no bundler plugin | Same string in both places; Next.js sets `applicationKey` as a build option | JS filtering page |
| Inbound error-message filter does not match | It runs on the incoming `{exception.type}: {exception.value}`, before symbolication/deobfuscation; ProGuard-obfuscated types never match | Match the raw type, or keep the exception class name unobfuscated | Inbound Filters page |
| Server errors from Next.js missing | `onRequestError` not exported, SDK older than 8.28.0, or Next.js older than 15 | Export it from `instrumentation.ts` | Next.js manual setup |
| One bug split across many issues | Message contains ids, hosts, timestamps | Fingerprint Rules with `*` in the message match, or `setFingerprint` | Grouping page |
| Ignored issue still costs quota | "Ignore" archives alerts but events still count; only Delete and discard stops counting (Business/Enterprise) | Fix in the SDK (`beforeSend`) or discard the issue | Manage Your Error Quota |
| Code owners never assign | No code mapping, CODEOWNERS user/team has no mapping, GitLab-only syntax, plan lacks Code Owners | Add mappings, use emails, simplify syntax | Ownership Rules page |

## Volume, cost and overhead

- Billing category: Errors (error events). Quota only counts what reaches Sentry and survives inbound filters; filtered events do not consume quota.
- Cheapest first: SDK-side drop (`ignoreErrors`, `before_send`, exception filters) removes the network and quota cost; an inbound filter needs no deploy and works across SDK versions; `sampleRate` samples errors uniformly and loses rare ones (default 1.0, JS and Python both 0.0 to 1.0), so prefer filters. Python `error_sampler` replaces `sample_rate` when set.
- `sendClientReports` (default true in JS) emits outcomes for events never sent; leave it on so Stats shows client-side drops.
- A resolved issue that fires again, and an ignored issue that keeps firing, both count toward quota again.
- Overhead: one handler per process; duplicates (two global handlers, framework plus manual capture) double both overhead and billing.

## Verify (R6)

1. Marker error from the real path (platform module recipe), then `sentry issue list <org>/<project> -q 'is:unresolved' --json --fields shortId,title,count` shows exactly ONE new issue for ONE trigger (no duplicate from double capture).
2. `sentry event view <org>/<project>/<event-id> --json` shows `release`, `environment`, readable frames, and the expected `fingerprint` (`{{ default }}` unless you set one).
3. Expected-error check: trigger a 4xx path; no new issue appears.
4. Noise: after adding a filter, the title stops growing in `sentry issue list ... --json --fields title,count`, and Stats shows the drops as filtered or client discards.
5. Ownership: `sentry api /api/0/projects/<org>/<project>/ownership/` returns the rules; a new test issue on an owned path shows the expected assignee.

## Sources

- https://docs.sentry.io/platforms/javascript/configuration/filtering/
- https://docs.sentry.io/platforms/javascript/configuration/options/
- https://docs.sentry.io/platforms/javascript/enriching-events/fingerprinting/
- https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
- https://docs.sentry.io/platforms/javascript/guides/express/
- https://docs.sentry.io/platforms/javascript/guides/fastify/features/error-handler/
- https://docs.sentry.io/platforms/javascript/guides/react/features/error-boundary/
- https://docs.sentry.io/platforms/python/configuration/options/
- https://docs.sentry.io/platforms/python/configuration/filtering/
- https://docs.sentry.io/platforms/go/configuration/filtering/
- https://docs.sentry.io/platforms/go/guides/gin/
- https://docs.sentry.io/platforms/dotnet/configuration/filtering/
- https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
- https://docs.sentry.io/platforms/ruby/configuration/options/
- https://docs.sentry.io/platforms/java/configuration/filtering/
- https://docs.sentry.io/platforms/php/configuration/filtering/
- https://docs.sentry.io/platforms/apple/configuration/filtering/
- https://docs.sentry.io/platforms/rust/configuration/filtering/
- https://docs.sentry.io/concepts/data-management/filtering/
- https://docs.sentry.io/product/issues/grouping-and-fingerprints/
- https://docs.sentry.io/product/issues/ownership-rules/
- https://docs.sentry.io/pricing/quotas/manage-event-stream-guide/
- https://docs.sentry.io/api/projects/list-a-projects-data-filters/
- https://docs.sentry.io/api/projects/retrieve-ownership-configuration-for-a-project/
- https://docs.sentry.io/api/projects/list-a-projects-codeowners-configurations/
- References: references/upstream/concepts/errors, references/upstream/concepts/reduce-volume, data/stale-apis/js.tsv

## Identifiers

```identifiers
ignoreErrors | https://docs.sentry.io/platforms/javascript/configuration/options/
denyUrls | https://docs.sentry.io/platforms/javascript/configuration/options/
allowUrls | https://docs.sentry.io/platforms/javascript/configuration/options/
sampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSend | https://docs.sentry.io/platforms/javascript/configuration/options/
sendClientReports | https://docs.sentry.io/platforms/javascript/configuration/options/
thirdPartyErrorFilterIntegration | https://docs.sentry.io/platforms/javascript/configuration/filtering/
filterKeys | https://docs.sentry.io/platforms/javascript/configuration/filtering/
applicationKey | https://docs.sentry.io/platforms/javascript/configuration/filtering/
setFingerprint | https://docs.sentry.io/platforms/javascript/enriching-events/fingerprinting/
onRequestError | https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
captureRequestError | https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
withServerActionInstrumentation | https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/
expressIntegration | https://docs.sentry.io/platforms/javascript/guides/express/
shouldHandleError | https://docs.sentry.io/platforms/javascript/guides/express/
fastifyIntegration | https://docs.sentry.io/platforms/javascript/guides/fastify/features/error-handler/
reactErrorHandler | https://docs.sentry.io/platforms/javascript/guides/react/features/error-boundary/
onUncaughtError | https://docs.sentry.io/platforms/javascript/guides/react/features/error-boundary/
onCaughtError | https://docs.sentry.io/platforms/javascript/guides/react/features/error-boundary/
onRecoverableError | https://docs.sentry.io/platforms/javascript/guides/react/features/error-boundary/
ErrorBoundary | https://docs.sentry.io/platforms/javascript/guides/react/features/error-boundary/
ignore_errors | https://docs.sentry.io/platforms/python/configuration/options/
error_sampler | https://docs.sentry.io/platforms/python/configuration/options/
sample_rate | https://docs.sentry.io/platforms/python/configuration/options/
before_send | https://docs.sentry.io/platforms/python/configuration/options/
IgnoreErrors | https://docs.sentry.io/platforms/go/configuration/filtering/
BeforeSend | https://docs.sentry.io/platforms/go/configuration/filtering/
AddExceptionFilterForType | https://docs.sentry.io/platforms/dotnet/configuration/filtering/
UseSentry | https://docs.sentry.io/platforms/dotnet/guides/aspnetcore/
excluded_exceptions | https://docs.sentry.io/platforms/ruby/configuration/options/
ignoredErrors | https://docs.sentry.io/platforms/java/configuration/filtering/
ignore_exceptions | https://docs.sentry.io/platforms/php/configuration/filtering/
autoAssignment | https://docs.sentry.io/api/projects/retrieve-ownership-configuration-for-a-project/
codeownersAutoSync | https://docs.sentry.io/api/projects/retrieve-ownership-configuration-for-a-project/
```

## Unconfirmed

- `captureException`: used by the Next.js `global-error` snippet; the page shows it only in code. Treat the call as documented there, not as an option.
