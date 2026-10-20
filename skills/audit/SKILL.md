---
name: audit
description: "Audit the Sentry setup in this repo (and optionally the Sentry org): find what is missing, wrong or risky across errors, tracing, profiling, replay, logs, crons, releases, source maps, privacy and more, then offer to fix it."
disable-model-invocation: true
allowed-tools: Bash(sentry-ctx *), Read, Grep, Glob
argument-hint: "[unit ...]"
---
# /sentry:audit

!`sentry-ctx flow preamble`

!`sentry-ctx flow audit`

Limit to these units if given (otherwise all): $ARGUMENTS
