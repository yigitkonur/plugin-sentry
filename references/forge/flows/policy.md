# Flow: policy (always asked)

Privacy and cost decisions are the user's every time. Never reuse an old answer silently: show it as the first option, labelled
"(previous)", and let them confirm or change it.

1. **Headless only:** if the environment variable `SENTRY_PLUGIN_POLICY_ANSWERS` is set (CI, evals), run `sentry-ctx policy from-env`,
   say clearly that the answers came from that file, and stop here. Otherwise ask.
2. Run `sentry-ctx policy questions`. It returns `calls.A`, `calls.B` and, for a Cloudflare unit, `calls.C`, each a list of questions already filtered to what this
   repo needs (no replay-masking question for a Go API) and already ordered with the previous answer first.
3. Ask call A with one `AskUserQuestion`, then call B with another, then call C when it has questions (an empty call is skipped). Map each question as-is: `header`, `question`, `multiSelect`,
   and `options[].label/description`. Do not add, drop or reword options. Save each answer as the option's `value`, never its label (a label may end in " (previous)").
4. If privacy preset is `custom`, ask follow-ups for: user info, IP, cookies and headers, request/response bodies, DB query data,
   local variables, screenshots/attachments. Record them under `privacy.custom`.
5. Build one flat JSON object keyed by question id and save it:
   ```
   sentry-ctx policy set <<'JSON'
   {"privacy.preset": "strict", "privacy.ai_io": "off", "privacy.replay_mask": "all", "org_access": "read-write",
    "environments": ["production", "staging"], "volume": "medium-budget", "release_owner": "ci", "products": ["exclude:profiling"],
    "cloudflare.owner": "split"}
   JSON
   ```
6. Show the saved digest (`sentry-ctx policy get`) in two lines. It is stored in `.sentry-plugin/policy.md`: the one artifact worth
   keeping after cleanup, and only if the user says so.

What the presets mean (say it, do not assume it): **strict** no user info, IP, cookies, headers, bodies, DB values or local
variables; **standard** opaque user id, no IP/cookies/auth headers/bodies; **permissive** SDK defaults; **custom** per dimension.
JS v11 and Python 3 collect user info, bodies and AI inputs/outputs when nothing is set, so "strict" always means writing the
settings explicitly.
