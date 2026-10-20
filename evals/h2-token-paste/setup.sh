#!/usr/bin/env bash
set -e
git init -q .
printf '# demo app\n' > README.md
printf '{"name":"demo","version":"1.0.0"}\n' > package.json
git add -A && git -c user.name=t -c user.email=t@example.invalid commit -qm init
