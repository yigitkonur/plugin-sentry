# Changelog

## 0.4.1 - 2026-10-25

- fix: sp is idempotent on both hosts (#5) (c0b46f1)

## 0.4.0 - 2026-10-25

- feat: run in codex too; install globally off, enable per project (#4) (ffa5f6d)
- ci: link check retries a 5xx or dropped connection twice (0a66095)
- docs: install globally but off, switch on per project; scripts/sp toggles it (1a79132)

## 0.3.0 - 2026-10-25

- feat(doctor): warn when the plugin-sentry marketplace will not auto-update (399b6ac)
- ci: use the shared release.py and release.yml (canonical copy: plugin-agentic-maker); README says how to turn on marketplace auto-update (bbdc527)
- ci: release job decides per plugin from its own files and tags (dry-run on dispatch); notes from commit subjects (8086c58)

