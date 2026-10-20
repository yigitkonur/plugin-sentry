# MCP server monitoring (product id: mcp)

## Fit
Propose this only when the repo implements an MCP server with an official SDK, because the Sentry SDK instruments the server object. This module covers the SDK integration in your own server code. It is not about Sentry's hosted MCP server, and it does not cover an app that only calls other MCP servers as a client.

Applies only when the `sig:mcp` signal fires (`data/signals.tsv`: "no MCP SDK detected" means do not propose).

Evidence that makes it worth proposing:

| Repo evidence | Where to look | Why it matters |
|---|---|---|
| `@modelcontextprotocol/server` or `@modelcontextprotocol/sdk` in dependencies | `package.json`, lockfile | JS server SDK; instrumented automatically from Node SDK 11.1 |
| `mcp` or `fastmcp` in Python dependencies | `pyproject.toml`, `requirements*.txt`, lockfile | Python server SDK (low-level API and FastMCP) |
| `McpServer` or `FastMCP` constructed in source | `grep -rn "McpServer\|FastMCP" <repo>` excluding node_modules and .venv | a server object exists to instrument |
| Tool handlers that call databases, files, paid APIs or hold private data | the tool registration files | failing and slow tools are what the traces answer; privacy settings matter most here |

Detection-only MCP packages (`data/detect/signal_deps.tsv`, `mcp` rows): `mcp-use`, `@mastra/mcp`, `mcp-handler`, `@vercel/mcp-adapter` (JS); `mcp-use`, `fastmcp` (Python); Go and JVM SDKs. The fetched Sentry pages cover only the JS and Python SDKs, so the other packages are unconfirmed (see Unconfirmed).

Not worth proposing:
- No server object in the code. A client-only repo has nothing for the integrations to instrument.
- The MCP server is a third-party hosted service the team does not run.
- The only evidence is a transitive dependency with no server code.
- Go or JVM server code: no Sentry MCP page was fetched for these.
- The user declines to add a Sentry SDK.

## Properly configured
Tracing must be on. The JS page instruments MCP work "when tracing is enabled", and the Python examples set `traces_sample_rate`. Production sampling is a volume decision (see `products/quota`). The fetched MCP pages say nothing about environments or releases; take those from the core modules.

| SDK family | Right | Source |
|---|---|---|
| JS, Node SDK 11.1+ | `Sentry.init` runs before the server is created, with `tracesSampleRate` set. No wrapping needed: every `McpServer` from `@modelcontextprotocol/server` 2.x or `@modelcontextprotocol/sdk` 1.x is instrumented automatically. Wrap a server only to give it its own recording settings. | Get Started page, Version requirement |
| JS, Node SDK 9.46 to 11.0 | `wrapMcpServerWithSentry(server)` for every `McpServer` instance. Minimum 9.46 for MCP Monitoring; `recordInputs` and `recordOutputs` need 10.33; stable `@modelcontextprotocol/server` 2.x support needs 10.70. | Get Started page |
| Cloudflare Workers | Automatic only when built with the Sentry Cloudflare Vite plugin. Without it, or on SDK below 11.1, wrap each server instance. Keep the default streamed spans; `traceLifecycle: "static"` drops spans that finish after the response. | Get Started page, Cloudflare Workers section |
| Python SDK 2.43.0+ (Get Started page); MCP SDK 1.15.0+ with Sentry Python SDK below 3.0, MCP SDK 2.0+ with Sentry Python SDK 3.0+; Python 3.9+ | `MCPIntegration()` in the `integrations` list of `sentry_sdk.init`, and `sentry_sdk.init` runs before the server is constructed. Covers the low-level API, FastMCP and standalone FastMCP. | Python MCP page (Supported Versions, Configure) |

Privacy, by SDK family:

| SDK | Recorded by default | Right for a repo whose tools handle private data | Source |
|---|---|---|---|
| JS, v11 | Tool and prompt inputs and outputs, and resource reads | `dataCollection.genAI` with inputs and outputs set to false in `Sentry.init`; or `recordInputs: false, recordOutputs: false` on one wrapper, which overrides the global setting | Node MCP page, Configure Input and Output Recording |
| Python | Tool inputs and outputs and prompt content are PII and are not sent unless `send_default_pii=True` | Leave `send_default_pii` off; if it is on for other reasons, add `MCPIntegration(include_prompts=False)` so tool and prompt content is still dropped | Python MCP page, Behavior and Options |
| JS, v10 | Unclear across the two pages (see Common mistakes) | Set `dataCollection.genAI` explicitly | both JS pages |

## Checks
| check id | read | passes when |
|---|---|---|
| ai.mcp | (1) Versions: `package.json` and its lockfile for `@sentry/node` or `@sentry/cloudflare` and `@modelcontextprotocol/server` or `@modelcontextprotocol/sdk`; `pyproject.toml`, `requirements*.txt` or lockfile for `sentry-sdk` and `mcp`/`fastmcp`. (2) Server objects: `grep -rn "McpServer\|wrapMcpServerWithSentry\|FastMCP\|MCPIntegration" <repo>` excluding node_modules and .venv. (3) Init order: the file containing `Sentry.init` or `sentry_sdk.init` and the file that constructs the server. (4) Privacy: the `dataCollection`, `recordInputs`, `recordOutputs`, `send_default_pii` and `include_prompts` settings in those same files. | JS 11.1+: tracing on and `Sentry.init` before server construction; JS 9.46 to 11.0, or Cloudflare without the Vite plugin: every `McpServer` instance wrapped; Python: `MCPIntegration` in `integrations` and `sentry_sdk.init` executed before the server is built; SDK versions meet the floor for their family; no `traceLifecycle: "static"` unless the team accepts dropped post-response spans; if tools handle private data, the privacy setting is explicit in code, not left to default |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| No MCP spans, tool calls work | Tracing off: no `tracesSampleRate` (JS) or `traces_sample_rate` (Python) | Set a sample rate; the instrumentation runs only with tracing on | Get Started page; Python MCP page |
| JS 9.46 to 11.0: no server spans | Auto-instrumentation starts at 11.1.0; older SDKs need a wrapper | `wrapMcpServerWithSentry(server)` on each `McpServer` | Get Started page |
| Cloudflare: spans for work after the response missing | `traceLifecycle: "static"` drops spans that finish after the response | Remove it (streamed spans are the default) | Get Started page, Cloudflare Workers section |
| Python: no MCP spans | `MCPIntegration()` missing from `integrations`, or `sentry_sdk.init` runs after the server is built | Add the integration; move init above everything else | Python MCP page; Get Started page (init "above everything else") |
| Python: spans without tool arguments or results | `send_default_pii` not set; PII is off by default | Set it only if the data policy allows, else leave as is | Python MCP page, Behavior |
| Python: tool arguments or results in Sentry although the team wanted them off | `send_default_pii=True` set elsewhere, and `include_prompts` left at its default | `MCPIntegration(include_prompts=False)` | Python MCP page, Options |
| JS v11: tool inputs and outputs in Sentry | Recording is on by default from v11 | `dataCollection.genAI` false globally, or `recordInputs`/`recordOutputs` false per server | Node MCP page |
| JS v10: unclear whether inputs and outputs are recorded | The Node page says v10 records only when `dataCollection` is set or the wrapper enables it; the Get Started page says that when `dataCollection` is unset, v10 follows `sendDefaultPii`. With `sendDefaultPii: true` and no `dataCollection`, the pages disagree | Set `dataCollection.genAI` explicitly and confirm on a marked call | Node MCP page; Get Started page, Options |
| Python `include_prompts` read as an on switch | Its default is True, but nothing is sent unless `send_default_pii=True`; True does not enable capture | Judge the setting together with `send_default_pii` | Python MCP page, Options |
| Session or request attribute queries return nothing for one SDK | Attribute names differ: Python `mcp.session_id` and `mcp.request_id`; Node `mcp.session.id` and `mcp.request.id` | Query the names for the SDK in use | Python MCP page, Captured Span Data; Node MCP page, Common Span Attributes |

## Volume, cost and overhead
- Billing: each MCP handler invocation (tool call, prompt, resource read) produces spans, so MCP cost lands in the Spans category. Included volume and pay-as-you-go rates are in `products/quota`; this module does not restate them.
- Runtime overhead: no figure on the fetched pages. Do not state one.
- Recording inputs and outputs puts argument and result values on the spans. The fetched pages do not say whether that changes billed size.

## Verify (R6)
1. Run the server from its real entry point, call one tool through a real MCP client, then open the trace in Sentry. The tool span should carry `mcp.tool.name` (Python) and `mcp.method.name` with `tools/call`, plus `mcp.transport` (`stdio`, `sse` or `http`). Node names this span "Tool Execution Span".
2. Privacy proof: call one tool with a marker string in an argument (for example `probe-<random>`) under the settings you plan to ship. With recording off, the marker must not appear in any MCP span attribute. Then stop using the marker.
3. A CLI or API proof of span attributes is not on the fetched pages; use the Sentry UI and mark the result UNVERIFIED for CLI use.

## Sources
- https://docs.sentry.io/product/mcp-servers/
- https://docs.sentry.io/product/mcp-servers/getting-started/
- https://docs.sentry.io/platforms/python/integrations/mcp/
- https://docs.sentry.io/platforms/javascript/guides/node/mcp-monitoring/

## Identifiers
```identifiers
McpServer | https://docs.sentry.io/product/mcp-servers/getting-started/
wrapMcpServerWithSentry | https://docs.sentry.io/product/mcp-servers/getting-started/
recordInputs | https://docs.sentry.io/product/mcp-servers/getting-started/
recordOutputs | https://docs.sentry.io/product/mcp-servers/getting-started/
sendDefaultPii | https://docs.sentry.io/product/mcp-servers/getting-started/
tracesSampleRate | https://docs.sentry.io/product/mcp-servers/getting-started/
traceLifecycle | https://docs.sentry.io/product/mcp-servers/getting-started/
Sentry.init | https://docs.sentry.io/product/mcp-servers/getting-started/
@modelcontextprotocol/server | https://docs.sentry.io/product/mcp-servers/getting-started/
@modelcontextprotocol/sdk | https://docs.sentry.io/product/mcp-servers/getting-started/
dataCollection | https://docs.sentry.io/platforms/javascript/guides/node/mcp-monitoring/
dataCollection.genAI | https://docs.sentry.io/platforms/javascript/guides/node/mcp-monitoring/
mcp.session.id | https://docs.sentry.io/platforms/javascript/guides/node/mcp-monitoring/
mcp.request.id | https://docs.sentry.io/platforms/javascript/guides/node/mcp-monitoring/
MCPIntegration | https://docs.sentry.io/platforms/python/integrations/mcp/
FastMCP | https://docs.sentry.io/platforms/python/integrations/mcp/
sentry_sdk.init | https://docs.sentry.io/platforms/python/integrations/mcp/
send_default_pii | https://docs.sentry.io/platforms/python/integrations/mcp/
include_prompts | https://docs.sentry.io/platforms/python/integrations/mcp/
traces_sample_rate | https://docs.sentry.io/platforms/python/integrations/mcp/
mcp.tool.name | https://docs.sentry.io/platforms/python/integrations/mcp/
mcp.method.name | https://docs.sentry.io/platforms/python/integrations/mcp/
mcp.transport | https://docs.sentry.io/platforms/python/integrations/mcp/
mcp.request_id | https://docs.sentry.io/platforms/python/integrations/mcp/
mcp.session_id | https://docs.sentry.io/platforms/python/integrations/mcp/
```

## Unconfirmed
- `sentry api` route for reading MCP span attributes: no fetched page names one; verify before use.
- `github.com/mark3labs/mcp-go`, `github.com/modelcontextprotocol/go-sdk`, `io.modelcontextprotocol`: Go and JVM MCP SDKs; no Sentry MCP page was fetched for them; verify before proposing.
- `mcp-use`, `@mastra/mcp`, `mcp-handler`, `@vercel/mcp-adapter`: detection-only packages; no Sentry integration page was fetched for them.
- Hono and Cloudflare MCP guides (`platforms/javascript/guides/hono/mcp-monitoring`, `platforms/javascript/guides/cloudflare/mcp-monitoring`): linked from the Get Started page, not fetched.
