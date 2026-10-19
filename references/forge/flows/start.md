# Flow: start (router)

The user wants Sentry set up, checked or fixed in this repo and has not said which. Do not ask them to pick a mode: detect and decide.

1. Follow `sentry-ctx flow preamble` through step 3 (tools, existing run, detect and confirm).
2. Decide from the confirmed table:
   - every unit absent -> init (`sentry-ctx flow init`)
   - at least one unit present, partial or legacy -> audit (`sentry-ctx flow audit`); units without Sentry in the same repo join
     the run in baseline mode.
   - only libraries -> say that nothing needs Sentry here and stop.
   - an unfinished run exists -> offer to continue it.
3. Say in one sentence which flow you chose and why, then continue with preamble steps 4-7 and that flow's steps.
4. If the user is asking about a production incident rather than setup, use the `triage` skill instead (`sentry-ctx ref forge/triage`).
