---
name: init
description: Set up Sentry properly in a repo that has none: picks the install route, proposes the base setup plus extras that fit, applies only what you approve, and proves it with a live event.
disable-model-invocation: true
allowed-tools: Bash(sentry-ctx *), Read, Grep, Glob
argument-hint: "[unit ...]"
---
# /sentry:init

!`sentry-ctx flow preamble`

!`sentry-ctx flow init`

Limit to these units if given (otherwise every unit without Sentry): $ARGUMENTS
