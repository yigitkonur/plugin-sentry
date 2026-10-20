#!/usr/bin/env bash
# Hook A/B evals: each case runs with the plugin and with no plugin; a hook earns its place only if the delta is positive.
# Models are pinned to haiku. Needs the claude CLI logged in. Results: evals/results/<timestamp>/ (gitignored).
set -u
cd "$(dirname "$0")/.."
exec claude plugin eval . --case 'h*' --scaffold --trust-plugin --allow-tools Write Edit Bash \
  --model haiku --judge-model haiku --runs "${RUNS:-3}" --ablation with-without --no-publish "$@"
