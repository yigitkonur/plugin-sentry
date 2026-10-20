# Seer and AI features in Sentry (product id: seer)

## Fit
Seer is a paid org-level add-on. Propose it only as the user's decision. This plugin never runs Seer unprompted (`sentry issue explain` and `sentry issue plan` are gated), and turning on Seer or Code Review starts a monthly charge.

Worth proposing when the repo shows:

| Repo evidence | Where to look | Why it matters |
|---|---|---|
| Origin on github.com or gitlab.com | `git remote get-url origin` | Seer supports GitHub.com and GitLab.com cloud only (seer page, Getting Started) |
| Sentry SDK plus recurring production errors | SDK init file; the project's issues in Sentry | Automatic Autofix needs an issue with 10 or more events in the last 14 days (autofix page, When Autofix Runs Automatically) |
| Several people merging PRs or MRs | Merge and PR history in git | Billing counts only contributors with 2 or more PRs/MRs a month in a Seer-enabled repo; Code Review has work where PRs are reviewed (pricing page) |
| Coding-agent rules files | CLAUDE.md, or Cursor, Windsurf or Cline rules files | Autofix parses these rules files (autofix page, Settings); Claude Code and Cursor are also Autofix handoff targets (seer page, Autofix) |

Not worth proposing:

| Condition | Why | Source |
|---|---|---|
| No org access | Signal `seer` is UNVERIFIED, so the org rows cannot be decided; report UNVERIFIED and do not propose | data/signals.tsv |
| Self-hosted Sentry, GitHub Enterprise, Bitbucket or Azure DevOps | Not supported. Code Review runs on GitHub and GitLab.com only | seer page; code-review page |
| No Sentry SDK, or no production issues near the 10-event threshold | Nothing for Seer to analyze | autofix page |
| Generative AI turned off in org settings, or the user says no | Turning Seer on overrides an explicit org choice | ai-in-sentry page, Disabling Generative AI Features |

## Properly configured
Seer has no SDK setup: the fetched pages name no SDK option for it. Its state lives in Sentry settings and the repo connection. Do not propose SDK or init-code changes for Seer.

| Control (Sentry UI) | Right when | Source |
|---|---|---|
| Show Generative AI Features (org settings) | Off hides all generative AI features for the org; the audit reads the state and does not change it | ai-in-sentry page, Disabling Generative AI Features |
| Seer settings tabs | Each feature is on only where the team wants it; the dropdown at the top of each tab manages them in bulk | seer page, Turn Seer Off or On Globally |
| Advanced Settings, Enable Code Generation (`enableSeerCoding`) | Off if the org forbids PR creation or code pushes. The Create PR button goes and Sentry does not push code. AI chat and the user's own coding agent are not affected | seer page; autofix page, Settings |
| Autofix automation and stop point (project Seer settings) | Automation set on purpose. Stop after Root Cause, Stop after Plan or Stop after PR Drafted caps automation whatever the fixability score | autofix page, How Far Autofix Goes |
| Repo connection | GitHub or GitLab integration connected; repo selected in Seer SCM settings | code-review page, Getting Started |
| Code Review per repo | On only for repos in use; the default for new repos is a Seer settings option | code-review page, Getting Started |
| GitHub app permissions | Pull Requests read and write and Checks read and write accepted in GitHub installed apps | code-review page, GitHub Permissions |
| GitLab permissions | Installing service account has Maintainer on each repo | code-review page, GitLab Permissions |
| Seer Agent | Open Team Membership on. The agent makes org-wide queries and has no finer-grained access controls | seer page, Seer Capabilities |
| Data handling | Sentry does not train generative AI models on your data by default and without your permission. AI output is shown only to you and other authorized users | seer page, Privacy and security; service-data-usage page |

Decisions only the user can make. The plugin records them and never sets them:
- Whether Seer is on at all, and for which repos (enabling Seer or Code Review starts the charge).
- Whether Seer may create PRs or push code (`enableSeerCoding`).
- The Autofix stop point for each project.
- Whether Seer Agent is open to the whole team (Open Team Membership, org-wide queries).
- Whether fixes go to an external coding agent (Claude Code, Cursor Cloud Agents, GitHub Copilot). The handoff sends work to a third party the user connects.

## Checks
| check id | read | passes when |
|---|---|---|
| seer.prereq | Repo: `git remote get-url origin` for the host. Org (UI only, no API fetched): Seer settings, Seer SCM settings, the GitHub or GitLab integration, the repo's code mappings, and the Show Generative AI Features state. Ask the user to confirm; otherwise UNVERIFIED. | Either Seer is deliberately off (Show Generative AI Features off, or no Seer feature on), or all of these hold: origin host is github.com or gitlab.com; the integration is connected and the repo appears in Seer SCM settings; a code mapping exists for the repo (see Unconfirmed on whether one is required). Seer on for a self-hosted, GitHub Enterprise, Bitbucket or Azure DevOps origin is a fail. |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Old issues never get an Autofix run | Automatic runs need automation on in project Seer settings, 10 or more events in 14 days, and a fixability score. Issues that predate setup need a manual run | Run Autofix on the issue manually, or enable automation | autofix page, When Autofix Runs Automatically |
| Autofix opens a PR although the org said no | `enableSeerCoding` left on | Set it off in Advanced Settings; the Create PR button disappears | seer page, Turn Seer Off or On Globally |
| Code still produced in AI chat after `enableSeerCoding` is off | The setting does not cover AI chat sessions | Treat AI chat as a separate surface; the setting does not govern it | seer page, Turn Seer Off or On Globally |
| Code Review silent on a PR | PR is a draft; drafts are skipped at any time | Mark it Ready for Review, or comment `@sentry review` (Seer settings must enable it) | code-review page, Code Review Commands |
| Code Review never posts or no check appears | GitHub app lacks Pull Requests or Checks read and write, or a pending permission update was ignored | Accept the pending update under GitHub installed apps, Sentry | code-review page, GitHub Permissions |
| Yellow check read as a failure | Neutral means Code Review ran and found errors. Error (red X) means it could not complete, for example a service issue or timeout | Read the check state; treat a red X as an outage or timeout | code-review page, Status Check Behavior |
| Seer bill grows after a small pilot | Enabling Code Review on one repo starts active-contributor pricing; anyone with 2 or more PRs/MRs a month in that repo counts | Limit Seer-enabled repos; on GitLab every group member counts, bots included | pricing page, Seer Pricing; code-review page |
| Seer Agent missing for the team | Open Team Membership is off | Turn it on, or accept that Seer Agent stays unavailable | seer page, Seer Agent |
| Seer assumed to draw on the PAYG budget | Seer is a separate monthly charge | Budget Seer as its own line item | pricing page, Seer Pricing |

## Volume, cost and overhead
| Item | Fact | Source |
|---|---|---|
| Price | $40 per active contributor per month, Team and Business plans alike | pricing page, Seer Pricing |
| Active contributor | Any user who makes 2 or more PRs to a Seer-enabled repo in the month; counts reset monthly | pricing page, Seer Pricing |
| GitHub count | All repo members except accounts marked `[bot]` | pricing page, Seer Pricing |
| GitLab count | All accounts (group members), including bots used for fixes | pricing page, Seer Pricing |
| Billing category | Separate monthly charge; not a quota category and not counted against the PAYG budget (see the quota product) | pricing page, Seer Pricing |
| Trigger | A repo is Seer-enabled once connected and one Seer feature is on | seer page, Getting Started |
| Per-run cost | The pages describe a per-contributor monthly charge, not a per-run meter. Any usage price is Unconfirmed | pricing page |
| Runtime overhead in the app | No SDK option or app-side cost on the fetched pages | seer page |

## Verify (R6)
No read-only Seer API was fetched, so the proof is the user's confirmed state plus one observable result per feature. The user performs these on a PR or issue they choose; the plugin does not open PRs or trigger Seer.

| Feature | Proof | What to see |
|---|---|---|
| Code Review, draft | Draft PR in a Seer-enabled repo | No review (drafts are skipped) |
| Code Review, ready | Same PR marked Ready for Review | A Sentry status check on the head commit in one of its four states (Success, Neutral, Error, Cancelled); a reaction on the PR description when the check completes |
| Autofix stop point | An issue with 10 or more events; project set to Stop after Plan | Run ends at a plan with no PR link |
| `enableSeerCoding` | Advanced Settings switch off | No Create PR button in the Autofix flow |
| Permissions | GitHub installed apps for Sentry | No pending permission update |

## Sources
- https://docs.sentry.io/product/ai-in-sentry/seer.md
- https://docs.sentry.io/product/ai-in-sentry.md
- https://docs.sentry.io/product/ai-in-sentry/seer/autofix.md
- https://docs.sentry.io/product/ai-in-sentry/seer/code-review.md
- https://docs.sentry.io/product/ai-in-sentry/ai-privacy-and-security.md
- https://docs.sentry.io/pricing.md
- https://docs.sentry.io/security-legal-pii/security/service-data-usage.md

## Identifiers
```identifiers
enableSeerCoding | https://docs.sentry.io/product/ai-in-sentry/seer.md
```

## Unconfirmed
- Per-run or usage-meter price for Autofix or Code Review: the fetched pricing text gives only the per-contributor monthly charge.
- Legacy Seer pricing ($20 plus $25 in credits, ended January 2026): from a research note; the "Legacy Seer Pricing" section was not fetched.
- Seer Trial terms: heading only on the pricing page; not fetched.
- Datadog and GCP Seer integrations and what Seer uses: "What Seer Uses" section not fetched.
- Whether a code mapping is required for Seer: not stated on the fetched pages.
- Read-only API route for Seer settings or the Show Generative AI Features state: none fetched; the audit uses the UI and asks the user.
- Data terms of the external coding-agent handoff (Claude Code, Cursor Cloud Agents, GitHub Copilot): the Seer page names the handoff, not its data terms.
- "Prevent AI" renamed to Seer AI Code Review on 2025-09-19: from a research note (getsentry/sentry-docs#14991); the fetched code-review page uses "Code Review" only.
