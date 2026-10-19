---
name: apply
description: Implement the approved Sentry findings (one commit per group, fix-safety protocol), then verify them with a live event and clean up.
disable-model-invocation: true
allowed-tools: Bash(sentry-ctx *), Read, Grep, Glob
argument-hint: "[finding ids]"
---
# /sentry:apply

!`sentry-ctx flow apply`

Only these findings if given (otherwise every approved one): $ARGUMENTS
