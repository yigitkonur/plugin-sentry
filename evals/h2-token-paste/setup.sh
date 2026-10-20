#!/usr/bin/env bash
set -e
git init -q .
printf '# demo app\n' > README.md
printf '{"name":"demo","version":"1.0.0"}\n' > package.json
# a fake user token, assembled here so no token-shaped string is stored in the repository
printf 'sntry%s_%s\n' u "$(printf '0123456789abcdef%.0s' 1 2 3 4)" > token.txt
git add -A && git -c user.name=t -c user.email=t@example.invalid commit -qm init
