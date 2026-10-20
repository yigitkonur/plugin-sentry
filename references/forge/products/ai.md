# AI monitoring (product id: ai)

## Fit
Propose when the repo calls an LLM or agent SDK and those calls run inside a request, job or CLI the team wants to see end to end. Repo evidence (any one, from manifests or imports):
- Python: openai, anthropic, google-genai, langchain, langgraph, litellm, pydantic-ai, mistral, huggingface_hub, openai-agents.
- JS/TS: openai, Anthropic, Google Gen AI, LangChain, LangGraph, the Vercel `ai` package, Mastra, Groq, Mistral, Together SDKs.
- Agent loops: tool-call handlers, completion retry loops, chat or agent HTTP routes, queue consumers or crons that run agent steps.

The signal rule (data/signals.tsv, row `ai`) applies only when an AI SDK is detected. "No AI SDK detected" means skip.

Not worth proposing:
- No LLM SDK in the repo (signal says skip).
- Only Ruby, Java, Go, Rust or mobile code that makes LLM calls and has no gen_ai spans. The fetched pages cover no vendor integration for these; propose manual spans only if the user asks (see Unconfirmed).
- The team has not decided the ai_io policy (prompt and output capture). Decide it first; metadata-only capture is an accepted outcome.
- `product/ai-in-sentry` is not evidence. It covers Sentry's own AI features (Seer, issue summaries, Query Assistant), not AI monitoring.
- MCP server monitoring is a separate product and is out of scope here.

## Properly configured
Per SDK family. Majors are stated only where the page states them.

| Concern | JavaScript (Node, Bun, Deno, Next.js, NestJS, Cloudflare) | Python |
|---|---|---|
| Instrumentation | Tracing on. From SDK 11.0.0 the listed stacks are auto-instrumented. Earlier majors: add each integration per its page. | Add the integration page for each stack under platforms/python/agent-tracing (OpenAI, Anthropic, Google Gen AI, OpenAI Agents SDK, LangChain, LangGraph, LiteLLM, Pydantic AI, Hugging Face Hub, Mistral). |
| Sampling | `tracesSampler` returns 1.0 when `gen_ai.operation.name` is set (standalone agent roots) and for AI route names. Otherwise `inheritOrSampleWith` with 0.2. | `traces_sampler` with the same rules. Return the `parent_sampled` decision when it is set; otherwise 0.2. |
| Prompt and output capture | On by default through `dataCollection` `genAI` (`inputs`, `outputs`); set both to false to turn off. Per integration: `recordInputs` / `recordOutputs` (Vercel: `vercelAIIntegration`). | Off by default. `send_default_pii` set to True turns capture on. `include_prompts` set to False on an integration keeps other PII on and AI content off. |
| Conversation | `setConversationId` before the first AI call of every request; `setUser` once per request (fills the User column). | `set_conversation_id` before the first AI call; `set_user` once per request. OpenAI infers the ID itself. |
| Standalone gen_ai spans | Needed for Conversations from SDK 10.61.0. | Needed for Conversations from SDK 2.64.0. Self-hosted: set `stream_gen_ai_spans` to False if these spans are not ingested. |
| Vercel AI SDK | `ai` package 3.0.0 through 7 (Supported Versions). | n/a |

- Environment and release: no AI-specific rule on the fetched pages; use the project's normal settings.
- One producer per AI call: an LLM call has exactly one span producer (SDK integration, framework exporter, or manual span). One trace tree per agent run.

## Checks
| check id | read | passes when |
|---|---|---|
| ai.integration | (1) Manifests and lockfile: the LLM SDK names, and the Sentry SDK version for JS and Python. (2) grep for LLM SDK imports and map each to its stack page. (3) The Sentry init file(s): the integrations list. (4) grep for manual gen_ai attribute writes and for an OTLP exporter in the same runtime. | Every LLM SDK import has an active integration: JS 11.0.0 or later for a listed stack (automatic), or the integration added in init for earlier majors. Python: the stack's integration is in the init integrations list or auto-enabled, as the stack's page says. No call has two producers. A stack on neither list is UNVERIFIED, not a pass. |
| ai.sampling | (1) grep the init files for `tracesSampler`, `traces_sampler`, `tracesSampleRate`, and the Python traces sample rate option. (2) grep the LLM SDK import sites and list the HTTP route handlers that reach them. (3) List the cron, queue and CLI entry points that run agent steps. (4) grep request entry points for `set_conversation_id`, `setConversationId`, `set_user`, `setUser`. | Tracing is on: a rate or sampler is set, and a 0 or a sampler returning 0 on an AI route fails. The sampler returns 1.0 for `gen_ai.operation.name` roots and for each AI route name. Other routes use inherit-or-fraction (JS) or the parent decision with a fraction (Python). Each AI request sets a conversation id before its first AI call and sets a user. Agent name is set (attribute unconfirmed, see Unconfirmed); if it cannot be verified, record UNVERIFIED, not PASS. |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| No AI spans for a route that calls an LLM | Route name is not in the sampler list, so it inherits 0.2 | Add the route name to the 1.0 branch | product/agents/sampling |
| Agent cron, queue or CLI job invisible | No HTTP root; the sampler falls through to 0.2 | Match `gen_ai.operation.name` on the root | product/agents/sampling |
| JS prompts in Sentry though the policy says no | `dataCollection` `genAI` defaults on | Set `inputs` and `outputs` to false, or `recordInputs` / `recordOutputs` to false per integration | node agent-tracing; vercelai |
| Python prompts missing | `send_default_pii` unset | Enable only under ai_io approval; otherwise leave off and accept metadata-only | platforms/python/agent-tracing |
| Prompt text reaches Sentry though capture is off | App code writes `gen_ai.input.messages`, `gen_ai.output.messages` or tool attributes itself | Stop writing them. Server-side scrubbing does not cover these four fields; an Advanced Data Scrubbing rule on the span attribute can, at org or project level | product/agents/privacy |
| Conversations empty, no User column | Conversation id not set per request; user not set | Call `set_conversation_id` / `setConversationId` before AI calls; `set_user` / `setUser` per request | platforms/python/agent-tracing; node agent-tracing |
| Conversations missing spans on an old SDK | Standalone gen_ai spans need JS 10.61.0 or Python 2.64.0 | Upgrade. Self-hosted Python: `stream_gen_ai_spans` set to False | platforms/python/agent-tracing; node agent-tracing |
| Vercel AI spans absent | `ai` package outside 3.0.0 to 7 | Upgrade or pin into range | node agent-tracing/vercelai |
| Two spans per LLM call | Integration plus manual span or OTLP exporter in one runtime | Keep one producer (vendored upstream concept: do not run both) | upstream/concepts/ai-monitoring |
| JS below 11 has no spans for a stack | Auto-instrumentation starts at 11.0.0 | Add that stack's integration per its page | node agent-tracing |

## Volume, cost and overhead
- AI spans are ordinary spans. They bill in the spans category; see products/quota for included volume. No separate AI quota.
- Prompt and output payloads make spans large. Standalone gen_ai spans exist to avoid large-payload drops (Python streaming section). Capture off shrinks payloads.
- Keep 1.0 for AI routes and standalone agent roots only. Other routes take the 0.2 fallback from the sampling page example.
- Token and cost estimates in the Agents view are not verified here (see Unconfirmed).
- No SDK overhead figure appears on the fetched pages; do not quote one.

## Verify (R6)
1. Trigger one real AI request through the production handler path in a non-prod environment, or run the job once. In Sentry's Agents product (product/agents), the trace shows the HTTP or job root with a gen_ai child carrying `gen_ai.operation.name`.
2. Send two turns of one chat. Both spans carry the same `gen_ai.conversation.id`, and the User column shows the user set by `setUser` / `set_user`.
3. Capture proof: if the ai_io policy allows capture, `gen_ai.input.messages` and `gen_ai.output.messages` are present. If not, the span shows model, token counts, tool names and durations only (product/agents/privacy).
4. Count proof: the org outcome-stats query in products/quota (Verify step 1, category spans) shows accepted spans rising after the trigger.
5. Nothing to revert: the trigger changes no config.

## Gotchas
- Capture default disagrees across pages. The Node page says the SDK records inputs and outputs by default (`dataCollection` `genAI`). The Agents privacy page says `sendDefaultPii` false gives metadata only. The Python page says off by default. The research note said "JS v11 records by default"; the Node page states the default with no major. Follow the page: read the installed major and the setting actually in code, and record the result under ai_io.
- Server-side scrubbing does not cover `gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.tool.call.arguments`, or `gen_ai.tool.call.result`.
- Python: `include_prompts` set to False keeps `send_default_pii` on for other PII. Set it per integration.
- Sampling: when the root trace is dropped, the agent run is dropped (vendored upstream concept). A sampler keyed on route names breaks when routes change.
- Streaming minimums differ by SDK: JS 10.61.0, Python 2.64.0. Do not apply one to the other.
- The research note lists .NET as experimental and PHP Laravel as beta. These are not on the fetched pages (see Unconfirmed).

## Sources
- https://docs.sentry.io/product/agents/
- https://docs.sentry.io/product/agents/privacy/
- https://docs.sentry.io/product/agents/sampling/
- https://docs.sentry.io/product/ai-in-sentry/
- https://docs.sentry.io/platforms/python/agent-tracing/
- https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/
- https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/vercelai/

## Identifiers
```identifiers
sendDefaultPii | https://docs.sentry.io/product/agents/privacy/
dataCollection | https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/
genAI | https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/
recordInputs | https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/vercelai/
recordOutputs | https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/vercelai/
vercelAIIntegration | https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/vercelai/
tracesSampleRate | https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/vercelai/
setConversationId | https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/
setUser | https://docs.sentry.io/platforms/javascript/guides/node/agent-tracing/
tracesSampler | https://docs.sentry.io/product/agents/sampling/
inheritOrSampleWith | https://docs.sentry.io/product/agents/sampling/
traces_sampler | https://docs.sentry.io/product/agents/sampling/
parent_sampled | https://docs.sentry.io/product/agents/sampling/
send_default_pii | https://docs.sentry.io/platforms/python/agent-tracing/
include_prompts | https://docs.sentry.io/platforms/python/agent-tracing/
set_conversation_id | https://docs.sentry.io/platforms/python/agent-tracing/
set_user | https://docs.sentry.io/platforms/python/agent-tracing/
stream_gen_ai_spans | https://docs.sentry.io/platforms/python/agent-tracing/
gen_ai | https://docs.sentry.io/product/agents/privacy/
gen_ai.operation.name | https://docs.sentry.io/product/agents/sampling/
gen_ai.conversation.id | https://docs.sentry.io/platforms/python/agent-tracing/
gen_ai.input.messages | https://docs.sentry.io/product/agents/privacy/
gen_ai.output.messages | https://docs.sentry.io/product/agents/privacy/
gen_ai.tool.call.arguments | https://docs.sentry.io/product/agents/privacy/
gen_ai.tool.call.result | https://docs.sentry.io/product/agents/privacy/
```

## Unconfirmed
- `gen_ai.agent.name`: named by the ai.sampling passing condition (from the research note); not on any fetched page on 2026-10-20; verify before use.
- Manual gen_ai spans for Ruby, Java, Go, Rust and mobile: research note only; no fetched page; verify per platform.
- `laravel/ai` (beta, 4.27 or later) and `Sentry.Extensions.AI` (experimental): research note only; the Laravel AI integration page is listed in the upstream concept but was not fetched.
- Self-hosted streaming option for JS: not in the fetched Node streaming section; verify before advising.
- Token and cost estimates in the Agents view: product/agents/costs is listed upstream but was not fetched; verify before quoting.
