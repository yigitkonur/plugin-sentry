# Findings: the contract between auditor and implementer

Findings are files in `.sentry-plugin/findings/<unit>/F-NNN-<product>-<slug>.md`. They are created only by
`sentry-ctx finding add` (one JSON object on stdin), which validates and masks. Never write them by hand. Never put a token in one.

```
sentry-ctx finding add <<'JSON'
{
  "unit": "web",
  "check": "priv.data-collection",
  "severity": "P1",
  "confidence": 0.9,
  "kind": "fix",
  "title": "dataCollection unset on JS v11: everything is collected",
  "files": ["src/instrumentation-client.ts"],
  "requires": [],
  "fix_ref": "platforms/nextjs#privacy",
  "verify": {"rung": "R5", "how": "event", "expect": "no user.ip_address, no cookie header"},
  "docs": ["https://docs.sentry.io/platforms/javascript/configuration/options/"],
  "sdk": {"pkg": "@sentry/nextjs", "version": "11.8.0"},
  "org_write": null,
  "evidence": {"ran": "grep -n dataCollection src/instrumentation-client.ts", "saw": "(no match)"},
  "what": "...", "why": "...", "fix": "...", "verify_text": "...", "source": "https://..."
}
JSON
```

Field meanings

| field | rule |
|---|---|
| `unit` | a detected unit id (see `sentry-ctx steer`), or `_org` for organization-level findings |
| `check` | an id from `data/checks.tsv`; the product is derived from it. Use `x.<slug>` (plus a valid `product`) for an unlisted check |
| `severity` | P0 leak or harm, P1 broken or wrong, P2 missing with clear fit, P3 advisory (rubric below) |
| `kind` | `fix` change existing code, `add` new setup, `remove` delete something, `org-write` a Sentry API change, `manual` a human step |
| `files` | the implementer's allowed touch set, repo-relative; required for fix/add/remove |
| `requires` | `token`, `org-write`, `deploy`, `tty`, `policy:<key>` |
| `verify.rung` | R0..R6, the highest rung that can prove this finding |
| `evidence` | `ran` (what you executed or read) and `saw` (what came back). Required: a finding you did not check is a guess |
| `org_write` | required for `org-write`: a REST call `{"method":"POST|PUT|PATCH|DELETE","path":"/organizations/...","body":{...},"effect":"..."}` or a CLI subcommand `{"cli":"project create ORG/name:platform --team T","effect":"..."}`. `sentry-ctx org apply <id>` shows the dry run, then `--run` performs it only if the exact call was approved in this run |

The engine rejects: an unknown unit or check, missing evidence (use `"status":"unverified"` with a `reason` when access is
missing), a file outside the repo, a docs URL outside docs.sentry.io / develop.sentry.dev / cli.sentry.dev / skills.sentry.dev /
mcp.sentry.dev / spotlightjs.com / sentry.io / github.com/getsentry, `org-write` without the exact call, and a duplicate of an
open finding (same unit, check and files).

Statuses: `open -> approved -> applied -> verified`, plus `skipped`, `blocked`, `waived`, `unverified`. Change them with
`sentry-ctx finding set-status <id> <status> --reason ... [--ran ... --saw ...]` (`verified` requires `--ran` and `--saw`).

Coverage is its own ledger, one cell per unit x product: `clean | findings | n/a | unverified | pending`.
`sentry-ctx coverage set --unit U --product P --state clean --note "..."` (clean is refused while open findings exist;
`unverified` needs `--reason`). `sentry-ctx ledger` exits 1 while any applicable cell is still `pending`.

## Severity rubric

- **P0** a token in tracked files/logs/client bundle; PII or AI I/O collected against policy; replay masking disabled; TLS verification disabled.
- **P1** init not loaded or loaded late; removed or renamed options for the installed major; release string differs between SDK and upload; artifacts not resolving; no `environment`; missing flush in a short-lived process; legacy alert APIs referenced; DSN region differs from the org region.
- **P2** a product with clear fit is missing (crons for schedulers, uptime for a public URL, logs, profiling, AI monitoring, release health); monitors with no alert.
- **P3** ownership rules, fingerprint rules, naming, Spotlight, dashboards.
