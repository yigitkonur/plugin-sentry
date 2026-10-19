# Debug artifacts (product id: debug-artifacts)

Source maps (JS), dSYMs (Apple), ProGuard/R8 mappings and native symbols (Android), PDBs (.NET), Dart symbols (Flutter). Concepts
and per-platform traps: `references/upstream/debug-artifacts/index`, `.../matching`, `.../javascript`, `.../apple`, `.../android`,
`.../react-native`, `.../flutter`, `.../dotnet`. Release string rules: `products/releases`. Token hygiene: `products/privacy`.

## Fit
| Evidence in the repo | Propose |
|---|---|
| Bundler config (Vite, webpack, Rollup, esbuild, Next.js, Nuxt, SvelteKit) or a `tsc`/minify step whose output is deployed | JS source maps with Debug IDs |
| Xcode project, Fastfile, `.xcarchive` scripts | dSYM upload |
| `build.gradle(.kts)` with R8 or ProGuard enabled, `.so` libs, NDK | ProGuard/R8 mapping, native symbols |
| `*.csproj` with Sentry package; `pubspec.yaml` with `--obfuscate` builds; React Native / Expo (both families) | PDB upload / Dart plugin / JS maps plus native files |

Not worth proposing: Python, Ruby, PHP, Go, Elixir (frames come from readable source unless the app is packed or stripped); Node run
directly from TypeScript (`tsx`, `ts-node`, Bun); dev-only builds; Dart without obfuscation (Flutter docs: complete traces by default).
Never invent a source-map step for a language without one (upstream index).

## Properly configured
Applies to JS SDK 7.47.0 and later (so JS v8 to v11), `sentry-cli` 3.x and `sentry` v4, Cocoa 8/9, Android Gradle plugin as documented.

| Family | Right looks like | Source of truth |
|---|---|---|
| JS bundler plugin | Plugin last in the `plugins` array; bundler emits maps (`hidden` for browser); `org`, `project`, `authToken` from env; `sourcemaps.filesToDeleteAfterUpload` set so `.map` files do not ship; production build only | Vite page; troubleshooting_js |
| JS CLI route | `inject` runs on the exact directory that is deployed, before `upload` and before deploy; `sourcesContent` present in maps; files not gzipped; each map under 190 MiB | troubleshooting_js; CLI sourcemap page |
| Next.js | `withSentryConfig` build options: `sourcemaps.deleteSourcemapsAfterUpload` default true (client maps only, server maps kept); `widenClientFileUpload` true when chunk frames stay minified; `useRunAfterProductionCompileHook` default true on Turbopack, false on webpack (Next.js 15.4.1+), and it rewrites build output (integrity hashes) | Next.js build options page |
| Legacy JS (SDK 7.46.0 or lower, plugin 1.x, CLI 2.16.1 or lower, self-hosted 23.6.1 or lower) | `release` in `Sentry.init` identical to the release the artifacts were uploaded under; a Debug ID path is the fix | legacy-uploading-methods |
| Apple | `DEBUG_INFORMATION_FORMAT` = `DWARF with dSYM File` for shipped configs; Run Script runs `debug-files upload "$DWARF_DSYM_FOLDER_PATH"` with the Input File line; `ENABLE_USER_SCRIPT_SANDBOXING` = `NO`; or Fastlane `sentry_debug_files_upload` | Apple dsym page |
| Android | Gradle plugin `sentry {}`: `includeProguardMapping` and `autoUploadProguardMapping` (both default on), `uploadNativeSymbols` (default off) for NDK, `includeSourceContext` (default off); token from `System.getenv`, never literal | Android gradle page |
| .NET | `SentryUploadSymbols` default `false`, `SentryUploadSources` for source context, `SentryOrg` and `SentryProject` set, `UseSentryCLI` not false; condition on Release | MSBuild page |
| Flutter | Build with `--obfuscate --split-debug-info`, then run `sentry_dart_plugin`; `dart_symbol_map_path` for readable issue titles; `upload_sources` for source context, `upload_source_maps` for web | Dart plugin page |
| React Native / Expo | Wizard-wired Xcode and Gradle hooks (SDK 5.11.0+); `SENTRY_DISABLE_AUTO_UPLOAD` or `disableAutoUpload` absent from release builds; token in EAS secrets | RN sourcemaps page |

CLI port (3.x to v4): `sentry sourcemap inject|upload|resolve`, `sentry debug-files upload|check|find`, `sentry proguard upload`;
`sourcemap upload` injects Debug IDs by default unless `--no-rewrite`, and both commands fail on zero JS and map pairs unless
`--allow-empty` (CLI page). Mapping of old commands: `references/forge/cli.md`, `sentry-ctx cli-map`.

## Checks
| check id | read | passes when |
|---|---|---|
| rel.sourcemaps | `package.json` build script, `vite.config.*`, `webpack.config.*`, `next.config.*`, CI YAML; `sentry sourcemap resolve <outdir> --json` on a local production build | A plugin or `inject` plus `upload` runs on production builds; maps are emitted hidden; every deployed bundle contains a Debug ID; maps deleted after upload or denied by the server; token only from env/secret store; SDK at 7.47.0 or later |
| rel.debug-files | Xcode `project.pbxproj` Run Script phase, `Fastfile`, `build.gradle*` `sentry {}` block, `*.csproj`/`Directory.Build.props`, `pubspec.yaml`, CI YAML; `sentry debug-files upload <dir> --no-upload` | An upload step exists for each shipped family (Apple dSYM, Android mapping and, with NDK, native symbols, .NET symbols, Dart symbols, RN both layers), runs in the job that builds the shipped binary, and is not disabled for the release variant |
| rel.resolve | `sentry event view <org>/<project>/<event-id> --json` for the newest events of release builds; `GET /api/0/projects/<org>/<project>/events/<event-id>/source-map-debug/` (JS); `GET .../files/dsyms/?debug_id=` (native) | Sampled recent release-build events show original file names and functions with source context; JS source-map-debug reports `has_debug_ids` true and frames found; each native debug_id has a matching debug file. Only events newer than the upload count |

## Common mistakes
| Symptom | Cause | Fix | Source |
|---|---|---|---|
| Upload step green, frames minified | `upload` ran without Debug IDs, or Sentry could not match (events earlier than upload) | Run `inject` first (3.x) or use the plugin; trigger a new event | troubleshooting_js |
| "Sentry not part of build pipeline" | Deployed bundles lack Debug IDs; dev/watch build | Production build with plugin or wizard `-i sourcemaps` | sourcemaps page |
| Debug ID snippet missing in some bundles | Plugin too old or not last in order; bundle produced after inject | Latest plugin, `debug` option on, inject the deployed directory | troubleshooting_js; Vite page |
| Only some client frames mapped (Next.js) | Chunks outside `static/chunks/pages/` not uploaded | `widenClientFileUpload: true` | Next.js build options |
| `.map` files served publicly | Maps not hidden or not deleted | Hidden maps plus `sourcemaps.filesToDeleteAfterUpload`, or deny `.js.map` | Vite page |
| Sourcemap `upload` fails with zero pairs (v4) | Bundler emits no `.map` | Enable hidden maps; `--allow-empty` only for legit empty dirs | CLI sourcemap page |
| Mapped but no source context | `sourcesContent` absent in maps | Bundler embeds sources | troubleshooting_js |
| Hand-set `release` differs between SDK and upload | Legacy matching only | Same string in both, or move to Debug IDs | legacy-uploading-methods |
| Apple crash unsymbolicated, upload OK | Debug configuration, sandboxing on, or rebuild after upload (UUID differs) | Settings above; upload from the shipped archive | Apple dsym page; upstream apple |
| Android obfuscated, no mapping | Variant excluded by `ignoredBuildTypes`, `ignoredFlavors` or `ignoredVariants`; `autoUploadProguardMapping` false; token unset | Remove filter for the shipped variant | Android gradle page |
| Kotlin frames fine, NDK frames raw | `uploadNativeSymbols` is off by default | Enable it (`includeNativeSources` for sources) | Android gradle page |
| .NET: method names but no file/line | `SentryUploadSymbols` default `false` | Enable in Release | MSBuild page |
| Old native event still raw after upload | Symbolication runs at ingest | New event, or reprocess (native only, wait 1 hour, counts quota twice) | Reprocessing page |
| Flutter plugin uploads nothing | Build lacked `--split-debug-info` / `--obfuscate` | Rebuild, then run the plugin | Dart plugin page |

## Volume, cost and overhead
- No event quota is spent by uploads. A reprocessed event counts against quota a second time; rate limits and spike protection do not apply to it (Reprocessing page).
- Debug files expire 90 days after last use (time to idle); a long-lived release that stops sending events can lose its files (native debug files page).
- Build cost: the plugin uploads during the build, so it must be limited to production/CI builds; the Vite page notes the upload step can dominate build time in fast builds.
- `--include-sources` / `includeSourceContext` / `SentryUploadSources` / `upload_sources` upload source code: needs the owner's consent (`products/privacy`).
- Self-hosted: set `SENTRY_URL` for the CLI or `url` for Fastlane (Apple dsym page).

## Verify (R6)
1. Local, no network: `sentry sourcemap resolve ./dist --json` (map found, Debug ID present per file); `sentry debug-files check <dSYM or .so or .pdb>`; `sentry proguard uuid mapping.txt`; `sentry debug-files upload <dir> --no-upload` (needs no credentials).
2. Server: `sentry api /projects/<org>/<project>/events/<event-id>/source-map-debug/` returns per-frame `debug_id_process`, `has_debug_ids`, `sdk_debug_id_support`; `sentry api /projects/<org>/<project>/files/dsyms/?debug_id=<id>` lists matching native files. Both accept `project:read`.
3. Event: a marker error from a release build (via the platform recipe, then remove the trigger) viewed with `sentry event view ... --json`: frames show original names, not hashed chunks or hex addresses. Say what rung was reached; an old event proves nothing.
4. Report UNVERIFIED when no release build can be produced or no org access exists.

## Sources
- references/upstream/debug-artifacts/index, matching, javascript, apple, android, react-native, flutter, dotnet (vendored Sentry docs)
- https://docs.sentry.io/platforms/javascript/sourcemaps/troubleshooting_js/
- https://docs.sentry.io/platforms/javascript/sourcemaps/troubleshooting_js/debug-ids/
- https://docs.sentry.io/platforms/javascript/sourcemaps/troubleshooting_js/legacy-uploading-methods/
- https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite/
- https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build/
- https://cli.sentry.dev/commands/sourcemap.md
- https://cli.sentry.dev/commands/debug-files.md
- https://cli.sentry.dev/commands/proguard.md
- https://docs.sentry.io/platforms/apple/dsym/
- https://docs.sentry.io/platforms/android/configuration/gradle/
- https://docs.sentry.io/platforms/dotnet/configuration/msbuild/
- https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin/
- https://docs.sentry.io/platforms/react-native/sourcemaps/
- https://docs.sentry.io/platforms/native/data-management/debug-files/
- https://docs.sentry.io/product/issues/reprocessing/
- https://docs.sentry.io/api/events/get-debug-information-related-to-source-maps-for-a-given-event/
- https://docs.sentry.io/api/projects/list-a-projects-debug-information-files/

## Identifiers
```identifiers
authToken | https://docs.sentry.io/platforms/javascript/sourcemaps/uploading/vite.md
filesToDeleteAfterUpload | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build.md
deleteSourcemapsAfterUpload | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build.md
widenClientFileUpload | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build.md
useRunAfterProductionCompileHook | https://docs.sentry.io/platforms/javascript/guides/nextjs/configuration/build.md
sourcesContent | https://docs.sentry.io/platforms/javascript/sourcemaps/troubleshooting_js.md
includeProguardMapping | https://docs.sentry.io/platforms/android/configuration/gradle.md
autoUploadProguardMapping | https://docs.sentry.io/platforms/android/configuration/gradle.md
uploadNativeSymbols | https://docs.sentry.io/platforms/android/configuration/gradle.md
includeNativeSources | https://docs.sentry.io/platforms/android/configuration/gradle.md
includeSourceContext | https://docs.sentry.io/platforms/android/configuration/gradle.md
ignoredBuildTypes | https://docs.sentry.io/platforms/android/configuration/gradle.md
ignoredFlavors | https://docs.sentry.io/platforms/android/configuration/gradle.md
ignoredVariants | https://docs.sentry.io/platforms/android/configuration/gradle.md
SentryUploadSymbols | https://docs.sentry.io/platforms/dotnet/configuration/msbuild.md
SentryUploadSources | https://docs.sentry.io/platforms/dotnet/configuration/msbuild.md
SentryOrg | https://docs.sentry.io/platforms/dotnet/configuration/msbuild.md
SentryProject | https://docs.sentry.io/platforms/dotnet/configuration/msbuild.md
UseSentryCLI | https://docs.sentry.io/platforms/dotnet/configuration/msbuild.md
dart_symbol_map_path | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin.md
upload_sources | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin.md
upload_source_maps | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin.md
sentry_dart_plugin | https://docs.sentry.io/platforms/dart/guides/flutter/debug-symbols/dart-plugin.md
sentry_debug_files_upload | https://docs.sentry.io/platforms/apple/dsym.md
disableAutoUpload | https://docs.sentry.io/platforms/react-native/sourcemaps.md
debug_id | https://docs.sentry.io/api/projects/list-a-projects-debug-information-files.md
has_debug_ids | https://docs.sentry.io/api/events/get-debug-information-related-to-source-maps-for-a-given-event.md
sdk_debug_id_support | https://docs.sentry.io/api/events/get-debug-information-related-to-source-maps-for-a-given-event.md
debug_id_process | https://docs.sentry.io/api/events/get-debug-information-related-to-source-maps-for-a-given-event.md
```

## Unconfirmed
- Whether artifact uploads count toward any quota category: not stated on the fetched pages; do not claim a cost.
- Exact event JSON field names that mark a frame as symbolicated (the research notes list some): not found in an official page; judge by readable names and source context, or by the source-map-debug endpoint.
