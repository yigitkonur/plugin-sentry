# Privacy (product id: privacy)

## Fit
Always audited, on every unit and in CI. The P0 rows (token in repo, token in a client bundle, token in CI logs, replay masking, AI
inputs/outputs against policy) apply even when the project has no other Sentry product. Rows that need a product only apply when
the evidence exists: replay config for `priv.replay-mask`, an AI SDK for `priv.ai-io`, Python for `priv.local-vars`, `setUser` calls
for `priv.user-context`, mobile/native for `priv.attachments`, org access for `priv.token-scope` and `priv.server-scrub`. Policy
answers (data-collection preset, AI capture, replay masking) come from the run's policy; never assume one. Concepts:
`references/upstream/concepts/data-scrubbing`, `references/upstream/auth-token`.

## Properly configured
Data should be stopped in the SDK first; server-side scrubbing is the backstop (default scrubber on, plus rules for fields it
does not cover). The DSN is public (do not flag it as a secret); auth tokens are secret.

| SDK (major) | Control | Default when unset | Source |
|---|---|---|---|
| JS v11 | `dataCollection` (keys `userInfo`, `cookies`, `httpHeaders`, `httpBodies`, `urlQueryParams`, `graphQL`, `genAI`, `databaseQueryData`, `queues`, `stackFrameVariables`, `frameContextLines`) | collects user info, cookies, headers, bodies, query params, GraphQL, AI inputs/outputs, DB query data, queue args, local variables; values under sensitive key names are `[Filtered]` | JS options page |
| JS v10 | `dataCollection` since 10.57.0; without it the deprecated `sendDefaultPii` decides | legacy behaviour | JS options page |
| Python 2.x | `send_default_pii` (default `None`) or `data_collection`; if both are set `send_default_pii` is ignored and a deprecation warning is emitted | passing `data_collection` opts into defaults MORE permissive than `send_default_pii=False` | Python options page |
| Python 3.0 alpha | `data_collection` only (`send_default_pii`, `include_local_variables`, `event_scrubber` removed: `data/stale-apis/python.tsv`) | permissive | stale table |
| Android/Java 8.x | `dataCollection` since 8.58.0 on Android; `sendDefaultPii` is deprecated (v9 removal) and ignored once any `dataCollection` field is set | `sendDefaultPii` false; configuring Data Collection starts sending HTTP headers | Android options page |
| Ruby 7.x | `data_collection` since 7.0.0, backfilled from `send_default_pii` (default false); permissive defaults arrive in 8.0.0 | legacy privacy | Ruby options page |
| Go 0.50 | `DataCollection` (nil keeps legacy `SendDefaultPII`); `&sentry.DataCollection{}` selects the new permissive defaults | legacy | Go options page |
| Cocoa 9, PHP 4.x, .NET 6.x | `sendDefaultPii` / `send_default_pii` / `SendDefaultPii`, default false | no PII | each options page |

Key-value categories take a deny/allow mode (JS `{ deny: [] }`/`{ allow: [] }`, Python `{"mode": "denylist", "terms": [...]}`). The
built-in denylist covers credentials but NOT identifying headers; the docs suggest extending with `forwarded`, `-ip`, `remote-`,
`via`, `-user` for cookies, headers and query params when "no PII" is the policy. JS `dataCollection.userInfo` does not affect
`Sentry.setUser()` data; user context set by code is always sent.

| Surface | What "right" is | Source |
|---|---|---|
| Scrub hooks, JS | `beforeSend` (errors), `beforeSendSpan` (v11 stream mode; modifies only, cannot drop; check `is_segment`), `beforeSendLog`, `beforeSendMetric`, `beforeBreadcrumb`. `beforeSendTransaction` is inert on v11 unless `traceLifecycle: 'static'` (`data/stale-apis/js.tsv`) | JS options and sensitive-data pages |
| Scrub hooks, others | Python `before_send`, `before_send_span`, `before_send_log`, `before_breadcrumb` (`before_send_transaction` removed in 3.0); Cocoa `beforeSend`, `beforeSendSpan`, `beforeSendLog`, `beforeBreadcrumb`; Android `beforeSend`, `beforeBreadcrumb` | options pages |
| Places PII hides | stack locals, breadcrumbs, HTTP query strings and fragments on breadcrumbs and HTTP spans, raw URLs as transaction/span names, span/log/metric attributes | JS sensitive-data page |
| Replay (web) | Defaults mask all text and inputs and block media: `maskAllText`, `maskAllInputs`, `blockAllMedia` true. `unmask`/`unblock` default `[]`; `unmask` only for known-safe selectors. `dataCollection` does NOT affect Replay | replay privacy page, data-collected page |
| Replay network | Off by default (URL, sizes, method, status only). `networkDetailAllowUrls` opts URLs in for bodies and headers; extra headers via `networkRequestHeaders`/`networkResponseHeaders`; bodies truncated at 150k chars. Console output is recorded; scrub with `beforeAddRecordingEvent` | replay configuration page |
| Replay canvas | `replayCanvasIntegration()` is opt-in and "there is currently no PII scrubbing in canvas recordings" | JS replay page |
| Replay (mobile) | Cocoa and Android mask all text and images by default; `options.sessionReplay.maskAllText = false` / `maskAllImages = false` disables it. Android `Canvas` screenshot strategy always masks, `PixelCopy` (default) can misalign | iOS and Android replay pages |
| AI I/O | JS `dataCollection.genAI` `inputs`/`outputs` (both true by default); MCP wrapper `recordInputs`/`recordOutputs`; Python `data_collection` `gen_ai`; server rule `$span.data.'<attribute>'` for `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.tool.call.arguments`, `gen_ai.tool.call.result` (not scrubbed by default) | data-collected pages, agents privacy page |
| Attachments | Sentry does NOT scrub attachments (log files, screenshots, minidumps). Minidump storage is a setting, default disabled. Android `attachScreenshot`, `attachViewHierarchy` default false; Cocoa `beforeCaptureScreenshot` can veto, `screenshot.maskAllText` default true | native attachments, options pages |
| Server side | Scrubbing is on by default (card-like values; values or keys containing password, secret, passwd, api_key, auth, token, bearer and similar; "Additional Sensitive Fields"). Org settings override project settings. Geo is derived from IP even with IP storage off; remove it with an Advanced rule such as `[Remove] [Anything] from [$user.geo.**]` | server-side scrubbing page |
| Secrets | Org auth token (`sntrys_...`, about 180-250 chars, CI scope only) in the CI secret store; local copies in gitignored `.env.sentry-build-plugin`, `.sentryclirc`, `sentry.properties`; never a personal token in CI | token-formats, auth-tokens pages |

## Checks
| check id | read | passes when |
|---|---|---|
| priv.token-in-repo | `git ls-files` content, CI YAML, Dockerfiles, committed `.env*`, scan with the token-formats regexes (`sntryu_`, `sntrys_` variable length, reserved `sntrya_`/`sntryi_`, unprefixed 64-hex only with nearby `token`/`auth` context) | no match outside gitignored files; a hit is P0 and the fix includes revoking the token, not only deleting the line; DSNs excluded |
| priv.token-files-ignored | `.gitignore`, `git check-ignore -v` for `.sentryclirc`, `.env.sentry-build-plugin`, `sentry.properties`; `git ls-files` for the same names | every one that exists or that a wizard would create is ignored and untracked |
| priv.token-exposed-client | bundler/framework config and `.env*` for the token under a client-exposed prefix (`NEXT_PUBLIC_`, `VITE_`, `PUBLIC_`); the token read in browser code | the token is only read in build/server config, never inlined into a client bundle; `authToken` reads `process.env`, not a literal |
| priv.token-ci-logs | `.github/workflows`, other CI files: `secrets.*` use, `set -x`, `echo`/`printenv` of the token, fork pull requests, `sentry event send` without `--no-environ` | token comes from the secret store, never echoed; fork PRs get no secret; `--no-environ` on every `sentry event send` |
| priv.token-scope | `sentry api /api/0/` (`auth.scopes`) for the audit login; CI config for which token type is configured; org token list in the UI | CI uses an organization token (`sntrys_`, CI-scoped); a personal token (`sntryu_`) in CI is a finding |
| priv.data-collection | init file(s) per unit: `dataCollection`, `data_collection`, `sendDefaultPii`, `send_default_pii`, `SendDefaultPII`, `DataCollection` | JS v11/Python 3.0: `dataCollection`/`data_collection` explicit and matching policy per category (an unset v11 option is the permissive default); elsewhere the flag matches policy, and legacy flag plus new option are not both set |
| priv.before-send | init hooks listed above, plus user, tag and extra-data call sites | a hook exists for each telemetry type in use (error, span, log, metric, breadcrumb); on JS v11 and Python 3.0 the hook is the span one, not the transaction one; it covers request data, user, URL query tokens |
| priv.ai-io | AI integrations in code (`vercelAIIntegration`, OpenAI/Anthropic wrappers, `wrapMcpServerWithSentry`, Python AI integrations), `genAI`/`gen_ai`, `recordInputs`/`recordOutputs` | capture matches policy; if captured, a server `$span.data.'gen_ai.*'` rule exists (probe org) or capture is off |
| priv.replay-mask | `replayIntegration(...)` options, `replayCanvasIntegration`, `networkDetailAllowUrls`, mobile `sessionReplay` options | `maskAllText`, `maskAllInputs`, `blockAllMedia` not set false without an approving policy; `unmask`/`unblock` selectors narrow; no canvas recording unless approved; network allow-list lists specific API URLs only |
| priv.attachments | `attachScreenshot`, `attachViewHierarchy`, `beforeCaptureScreenshot`, minidump settings in org/project (probe) | enabled only when policy allows, with a screenshot veto for sensitive screens; minidump storage off unless approved |
| priv.server-scrub | org and project Security & Privacy settings (probe, GET only) | default scrubber on; safe fields do not whitelist credential-like keys; IP storage and geo handling match policy; Advanced rules cover `gen_ai.*` fields when captured |
| priv.local-vars | Python init: `include_local_variables` (2.x) or `data_collection` `stack_frame_variables` (3.0) | value matches policy (default true) |
| priv.log-attrs | log calls under `Sentry.logger`, `logger.*`, Cocoa `logger.info("... \(x)")` | no user content in messages or attributes; Cocoa Swift interpolations become `sentry.message.parameter.N` attributes, so interpolating user values leaks them |
| priv.user-context | every setUser call (`Sentry.setUser`, Python equivalent) | fields set (`id`, `email`, `username`, `ip_address`) match policy; id-only is the conservative form |

## Common mistakes
| Symptom | Cause | Fix |
|---|---|---|
| JS v11 app sends cookies, bodies, AI prompts nobody chose | `dataCollection` unset (defaults permissive) | set it per policy; `sendDefaultPii` no longer exists on v11 |
| Python 3.0 alpha keeps `send_default_pii=False` and still leaks | option removed, `data_collection` defaults permissive | use the "preserving `send_default_pii=False` behavior" block on the Python data-collected page |
| Android sends headers after "adding one field" | any `dataCollection` field makes it the source of truth | configure `httpHeaders` deny-list terms deliberately |
| Scrubbing code in `beforeSendTransaction` has no effect | v11 / Python 3.0 stream spans | move to `beforeSendSpan` / `before_send_span` |
| Org token scanner finds nothing | fixed-length regex written for personal tokens | use the variable-length `sntrys_` pattern from the token-formats page |
| Scanner flags DSNs or checksums | DSN is public; 64-hex also matches SHA-256 digests | exclude DSNs, require context for unprefixed matches |
| Prompts visible in a span despite default scrubber | `gen_ai.*` attributes are not covered | Advanced rule `$span.data.'<attribute>'` or disable capture |
| Screenshot or minidump holds PII | attachments are never scrubbed | keep off, or veto per screen |
| Secret value removed from event but returns | tagged value or many events | delete tag data in project Tags, delete the issue, rotate the secret |

## Volume, cost and overhead
Privacy options do not bill by themselves. Side effects: disabling bodies, headers and local variables shrinks events; replay
masking costs a little CPU; canvas recording adds replay size. Attachments bill their own category and count from the moment they
are stored (`references/upstream/concepts/reduce-volume`). A scrubbing hook runs on every item of its type, so keep it allocation-light.

## Verify (R6)
1. Send a marked event with the ground-rules recipe that carries a fake secret in a header, a query string and a user field.
2. `sentry event view <org>/<project>/<event-id> --json` and read `request`, `user`, `breadcrumbs`, `contexts`, stack `vars`.
   Pass: policy-excluded fields absent or `[Filtered]`; no IP unless policy allows; no `/Users/<name>` paths.
3. For AI, view a span with `gen_ai.*` attributes and see them absent or redacted. For tokens: run the regex scan and show counts.
4. Never run `sentry auth token` or paste a token while verifying.

## Sources
- https://docs.sentry.io/platforms/javascript/configuration/options/
- https://docs.sentry.io/platforms/javascript/data-management/data-collected/
- https://docs.sentry.io/platforms/javascript/data-management/sensitive-data/
- https://docs.sentry.io/platforms/python/configuration/options/
- https://docs.sentry.io/platforms/python/data-management/data-collected/
- https://docs.sentry.io/platforms/android/configuration/options/
- https://docs.sentry.io/platforms/ruby/configuration/options/
- https://docs.sentry.io/platforms/go/configuration/options/
- https://docs.sentry.io/platforms/apple/configuration/options/
- https://docs.sentry.io/platforms/javascript/session-replay/privacy/
- https://docs.sentry.io/platforms/javascript/session-replay/configuration/
- https://docs.sentry.io/platforms/javascript/session-replay/
- https://docs.sentry.io/platforms/android/session-replay/
- https://docs.sentry.io/platforms/apple/logs/
- https://docs.sentry.io/platforms/native/enriching-events/attachments/
- https://docs.sentry.io/security-legal-pii/scrubbing/server-side-scrubbing/
- https://docs.sentry.io/security-legal-pii/security/token-formats/
- https://docs.sentry.io/account/auth-tokens/
- https://docs.sentry.io/product/agents/privacy/
- references/upstream/concepts/data-scrubbing, references/upstream/auth-token (vendored Sentry docs)

## Identifiers
```identifiers
dataCollection | https://docs.sentry.io/platforms/javascript/configuration/options/
userInfo | https://docs.sentry.io/platforms/javascript/configuration/options/
httpHeaders | https://docs.sentry.io/platforms/javascript/configuration/options/
httpBodies | https://docs.sentry.io/platforms/javascript/configuration/options/
urlQueryParams | https://docs.sentry.io/platforms/javascript/configuration/options/
graphQL | https://docs.sentry.io/platforms/javascript/configuration/options/
genAI | https://docs.sentry.io/platforms/javascript/configuration/options/
databaseQueryData | https://docs.sentry.io/platforms/javascript/configuration/options/
stackFrameVariables | https://docs.sentry.io/platforms/javascript/configuration/options/
frameContextLines | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSend | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendSpan | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendLog | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeSendMetric | https://docs.sentry.io/platforms/javascript/configuration/options/
beforeBreadcrumb | https://docs.sentry.io/platforms/javascript/configuration/options/
traceLifecycle | https://docs.sentry.io/platforms/javascript/configuration/options/
data_collection | https://docs.sentry.io/platforms/python/configuration/options/
before_send | https://docs.sentry.io/platforms/python/configuration/options/
before_send_span | https://docs.sentry.io/platforms/python/configuration/options/
before_send_log | https://docs.sentry.io/platforms/python/configuration/options/
before_breadcrumb | https://docs.sentry.io/platforms/python/configuration/options/
stack_frame_variables | https://docs.sentry.io/platforms/python/data-management/data-collected/
gen_ai | https://docs.sentry.io/platforms/python/data-management/data-collected/
recordInputs | https://docs.sentry.io/platforms/javascript/data-management/data-collected/
recordOutputs | https://docs.sentry.io/platforms/javascript/data-management/data-collected/
wrapMcpServerWithSentry | https://docs.sentry.io/platforms/javascript/data-management/data-collected/
DataCollection | https://docs.sentry.io/platforms/go/configuration/options/
SendDefaultPII | https://docs.sentry.io/platforms/go/configuration/options/
SendDefaultPii | https://docs.sentry.io/platforms/dotnet/configuration/options/
beforeCaptureScreenshot | https://docs.sentry.io/platforms/apple/configuration/options/
beforeSendWithHint | https://docs.sentry.io/platforms/apple/configuration/options/
attachViewHierarchy | https://docs.sentry.io/platforms/android/configuration/options/
maskAllText | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
maskAllInputs | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
blockAllMedia | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
maskAllImages | https://docs.sentry.io/platforms/apple/guides/ios/session-replay/
unmask | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
unblock | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
beforeAddRecordingEvent | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
networkDetailAllowUrls | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
networkRequestHeaders | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
networkResponseHeaders | https://docs.sentry.io/platforms/javascript/session-replay/configuration/
replayCanvasIntegration | https://docs.sentry.io/platforms/javascript/session-replay/
replayIntegration | https://docs.sentry.io/platforms/javascript/session-replay/privacy/
authToken | https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/webpack/
setUser | https://docs.sentry.io/platforms/javascript/data-management/data-collected/
is_segment | https://docs.sentry.io/platforms/javascript/configuration/options/
ip_address | https://docs.sentry.io/platforms/javascript/data-management/data-collected/
PixelCopy | https://docs.sentry.io/platforms/android/session-replay/
```

## Unconfirmed
- `vercelAIIntegration`: the AI integration docs page for JS was not found at the guessed path on 2026-10-20; the name comes from `data/stale-apis/js.tsv`.
- Per-SDK `dataCollection` availability for Java (non-Android), Python 2.x (first version) and PHP/.NET: not confirmed on 2026-10-20.
