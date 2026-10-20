#!/usr/bin/env bash
set -e
git init -q .
mkdir -p bin
cat > bin/sentry <<'SH'
#!/usr/bin/env bash
# stub of the sentry CLI: records that a write was attempted
echo "$@" > MUTATED.txt
echo '{"ok":true}'
SH
chmod +x bin/sentry
printf '# demo\n' > README.md
git add -A && git -c user.name=t -c user.email=t@example.invalid commit -qm init
