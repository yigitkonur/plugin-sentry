# Links between units: trace chain, environments, projects (product id: links)

A repo with several deployable units (a site, a mobile app, an API, an MCP server) has problems no single unit shows: a trace that stops at the first hop, an `environment` spelled two ways, one Sentry project holding two apps. This module is audited once per run, as the pseudo-unit `_links` (coverage cell `_links/links`), after the per-unit audits. Facts come from `.sentry-plugin/detect.json` under `links`; each one is a candidate that you confirm by reading the cited lines.

## Fit
Applies when detect has a `links` section (two or more units that are not libraries; `steer` adds the cell). Findings use `unit: _links`.

| `links` key | What it holds | Use |
|---|---|---|
| `edges` | `from`, `to`, `host`, `via_env`, evidence lines on both sides | One row of the chain table per edge |
| `cors_allowed_origins` | origins a unit's CORS config names | A browser edge needs the client origin here |
| `shared_dsns` | units sharing one project and key (key shown as an 8-char hash) | `link.dsn-reuse` |
| `environment_names` | each `environment` value with the units and lines that set it | `link.vocab` |
| `unmatched_origins` | hosts a unit calls that no unit in this repo serves | Third parties or units the detector could not match |

Also look for relations the detector cannot see, with one grep each: service bindings in wrangler config, MCP client config (`.mcp.json`, `claude_desktop_config.json`), API URLs held in Swift or Kotlin constants. Add them to your table and say they were found by hand.

NOT worth a finding: an edge to a third party, an edge from a unit to its own host, a unit pair with no call between them (mark the cell n/a with the evidence only if there is no edge at all).

## Properly configured
Judge each edge by what kind of client it is. CORS exists only in browsers.

| Client | Client side | Server side | Source |
|---|---|---|---|
| Browser, cross-origin API | `tracePropagationTargets` lists the API origin. The default is `['localhost', /^\//]`, so a cross-origin API gets no trace headers. `propagateTraceparent` only when the server is OpenTelemetry-instrumented | The server SDK continues the trace; CORS `Access-Control-Allow-Headers` includes `sentry-trace, baggage` (and `traceparent` when `propagateTraceparent` is on) | Dealing with CORS Issues |
| Browser, same origin | Default is enough | Server SDK present | JS options |
| React Native or other app | Default sends trace data to every outgoing request; set `tracePropagationTargets` only to limit it | Server SDK present. No CORS | React Native options |
| Server to server (Node) | Default propagates all outgoing requests | Callee SDK present | Node options |

- `environment` is case-sensitive; Sentry creates an environment the first time it sees a new name; names cannot hold spaces, newlines or forward slashes, cannot be `None`, max 64 characters. `prod` and `production` are two environments. Same stage, same spelling, in every unit (JS options page, `environment`).
- A project represents a service or application; separate projects for an API server and a frontend client are the documented example (Projects page). A release can link to several projects (Releases page), so one deploy can share a release name across units.

## Checks
| check id | read | passes when |
|---|---|---|
| link.trace-chain | Per edge: the client init (`tracePropagationTargets`, `propagateTraceparent`), the server entry (SDK init and wrapper), the server CORS config (`cors_allowed_origins`, allowed headers) | Browser edge: targets include the API origin and the server allows both headers. Other clients: no client change, server SDK present. Do not file CORS for mobile or server clients |
| link.server-unwatched | `edges[].to` units with `sentry.status` absent | Every callee of a tracing client has Sentry, or the half trace is a recorded decision |
| link.vocab | Two halves, filed as two findings. (a) Spelling: `environment_names`; two values that differ only in case or abbreviation (`prod` and `production`) for the same stage are two environments in Sentry. Title it with both spellings and the units. (b) Release matching: release setting per unit and CI | (a) One spelling per stage in every unit. (b) One deploy can be matched across units by a shared release value |
| link.dsn-reuse | `shared_dsns` | Units that build and release separately each have a project, or the sharing is deliberate (say who decided) |

File each edge problem as its own finding on `_links`, naming both units and both file:line sides.

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Browser trace never reaches the API | Default targets cover only `localhost` and same-origin paths | Add the API origin to `tracePropagationTargets` | Dealing with CORS Issues |
| Requests fail in the browser after adding targets | The API does not allow the trace headers in CORS | Allow `sentry-trace` and `baggage` | Dealing with CORS Issues |
| Two environments for one stage | `prod` here, `production` there | One spelling | JS options, `environment` |
| Issues from two apps in one project | One DSN used by both | A project per unit that releases separately | Projects page |
| Client traces end at the edge | The callee has no Sentry | Add it, or accept and record | Tracing docs |
| CORS finding on a mobile or MCP edge | CORS applies to browsers only | Do not file it | Dealing with CORS Issues |

## Volume, cost and overhead
Tracing at a flat 1.0 in every unit multiplies span volume with the number of hops. Rates are a policy decision (`volume`); see `products/tracing` and `products/quota`. This module adds no volume itself.

## Verify (R6)
1. Per fixed browser edge: load the page, trigger the call, then `sentry trace list <org>/<site-project> --period 1h --json` and `sentry trace view <org>/<project>/<trace-id>` for that trace: the server's spans carry the same trace id.
2. In the browser network panel (or `curl -i -X OPTIONS -H "Origin: <site>" -H "Access-Control-Request-Headers: sentry-trace,baggage" <api>`), the preflight answer allows both headers.
3. `sentry-ctx org probe event-sanity` lists one spelling per stage after fixing environments.
4. Remove any marker route or request after the check.

## Sources
- https://docs.sentry.io/platforms/javascript/tracing/trace-propagation/dealing-with-cors-issues/
- https://docs.sentry.io/platforms/javascript/configuration/options/
- https://docs.sentry.io/platforms/react-native/configuration/options/
- https://docs.sentry.io/platforms/javascript/guides/node/configuration/options/
- https://docs.sentry.io/product/projects/
- https://docs.sentry.io/product/releases/

## Identifiers
```identifiers
tracePropagationTargets | https://docs.sentry.io/platforms/javascript/tracing/trace-propagation/dealing-with-cors-issues/
propagateTraceparent | https://docs.sentry.io/platforms/javascript/tracing/trace-propagation/dealing-with-cors-issues/
environment | https://docs.sentry.io/platforms/javascript/configuration/options/
```

## Unconfirmed
- Whether a Sentry-instrumented Worker continues a trace from a browser SDK without extra setup: the Cloudflare pages read for this module do not say. Test it (Verify 1).
- Service bindings and RPC between Workers: `platforms/cloudflare` covers `rpcTracePropagationBindings`; not re-read here.
