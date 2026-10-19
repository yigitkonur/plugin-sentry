---
name: triage
description: Use when the user asks why something is failing in production, names a Sentry issue (short id like API-7 or a sentry.io URL), or wants the top errors. Walks the CLI funnel rank, view, corroborate; Seer only on request.
allowed-tools: Bash(sentry *), Bash(sentry-ctx *), Read, Grep, Glob
argument-hint: "[issue id, URL or question]"
---
# Triage a production symptom with the sentry CLI

!`sentry-ctx ref forge/triage`

Start from: $ARGUMENTS
