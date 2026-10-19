# Module templates

Every file under `products/` and `platforms/` follows one of these shapes. `sentry-ctx ref verify <name>` enforces them:
sections must exist, every option-shaped token in backticks must be declared with the page that documents it (or listed under
`## Unconfirmed`), and every declared name must appear in the text of its URL. If you cannot find a name in an official page, do
not write it: put it under Unconfirmed or leave it out.

Write for an auditor that already has the repo open: say what to look for, in which file, and what "right" is. No tutorials.
Keep each file under ~180 lines. Prefer tables. Quote option names exactly as the docs spell them.

## Product module (`products/<id>.md`, ids in data/products.json)

````
# <Product> (product id: <id>)

## Fit
Evidence in a repo that makes this product worth proposing, and when it is NOT worth proposing.

## Properly configured
What a correct setup looks like, per SDK family. Sampling, environments, releases, PII and overhead belong here.

## Checks
| check id | read | passes when |      (ids from data/checks.tsv only; use x.<slug> for an unlisted one)

## Common mistakes
Symptom -> cause -> fix, each tied to a source.

## Volume, cost and overhead
Which quota category it bills, the default/typical rates, runtime cost, what needs a pay-as-you-go budget.

## Verify (R6)
The product-specific proof beyond "an event arrived" (CLI/API command and what to see).

## Sources
- <official URL>

## Identifiers
```identifiers
tracesSampleRate | https://docs.sentry.io/platforms/javascript/configuration/options/
```

## Unconfirmed
- `someName`: could not find it in an official page on <date>; verify before use.
````

## Platform module (`platforms/<id>.md`, id = framework id from data/detect/frameworks.json or an ecosystem name)

````
# <Platform> (module: platforms/<id>)

## Detect
Manifests, imports, config files that identify it; the init file(s) to read.

## Install route
Which accelerator applies (`sentry init`, `@sentry/wizard -i <x>`, or manual from the live docs page), with the docs path for
`sentry-ctx docs page`. Never paste install steps from memory.

## Init placement
Where Sentry must start so it sees everything (file, hook, ordering relative to the framework).

## Options by SDK major
| option | v(N-1) | v(N) | note |      only options the docs list for this platform

## Product support matrix
| product | supported | notes |      what this platform can and cannot do (replay, profiling, logs, crons, ...)

## Release and artifacts
Release string rule, source maps / debug files / symbols route, the CI step.

## Privacy
Platform-specific data that leaves by default and the option that controls it.

## Verify recipe
How to emit a marked event from the real code path of this platform, and how to remove the trigger.

## Gotchas
Platform-specific traps with sources.

## Sources
- <official URL>

## Identifiers
```identifiers
name | https://docs.sentry.io/...
```

## Unconfirmed
- `name`: ...
````
