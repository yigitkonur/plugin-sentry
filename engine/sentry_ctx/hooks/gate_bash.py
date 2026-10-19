"""H4: gate Sentry shell commands.

deny  : anything that prints or copies a raw credential, a token on a command line, `event send` without --no-environ,
        and any Sentry mutation from a read-only agent.
ask   : outward-facing Sentry mutations that the user has not already approved in this run (run.json approved_writes/approved_cli).
Reads are never gated. Best-effort parsing: this is a guard rail for an agent, not a sandbox.
"""
from __future__ import annotations

import os
import re
import shlex

from .. import runstate, tokens
from . import common

WRAPPERS = {"env", "sudo", "command", "time", "nohup", "exec", "xargs", "npx", "pnpx", "bunx", "dlx", "exec", "--yes", "-y", "--no-install", "--"}
SENTRY_BINS = {"sentry", "sentry-cli"}
READ_AGENTS = {"sentry:auditor", "sentry:verifier"}

# subcommand prefixes (v4 names; v3 plural/old names normalized below) that change state
MUTATING = [
    "issue resolve", "issue unresolve", "issue archive", "issue merge", "issue explain", "issue plan",
    "project create", "project delete", "project remove", "project rm",
    "release create", "release new", "release finalize", "release delete", "release archive", "release restore", "release deploy", "release set-commits",
    "sourcemap upload", "sourcemap inject", "debug-files upload", "proguard upload", "code-mappings upload", "build upload", "dart-symbol-map upload",
    "feedback resolve", "feedback unresolve", "feedback spam", "dashboard create", "dashboard widget", "dashboard restore",
    "monitor run", "trial start", "init", "snapshots upload",
]
V3_NORMALIZE = [
    (r"^releases (new|finalize|delete|archive|restore|set-commits)", r"release \1"),
    (r"^deploys new", "release deploy"),
    (r"^sourcemaps (upload|inject)", r"sourcemap \1"),
    (r"^upload-(dif|dsym|proguard)", "debug-files upload"),
    (r"^issues (resolve|mute|unresolve)", r"issue \1"),
    (r"^projects create", "project create"),
    (r"^monitors run", "monitor run"),
]
CRED_FILES = re.compile(r"(\.sentryclirc|\.env\.sentry-build-plugin|sentry\.properties|SentryCliOptions\.asset|sentry/cli\.db)")
READERS = {"cat", "less", "more", "head", "tail", "grep", "egrep", "rg", "sed", "awk", "bat", "strings", "xxd", "hexdump", "sqlite3", "cp", "mv", "open", "code", "vim", "nano", "base64"}


def _segments(cmd: str):
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=";&|\n")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = cmd.split()
    seg, out = [], []
    for t in toks:
        if t and set(t) <= set(";&|\n"):
            if seg:
                out.append(seg)
            seg = []
        else:
            seg.append(t)
    if seg:
        out.append(seg)
    return out


def _program(seg):
    """Index of the real program in a segment, skipping env assignments and wrappers."""
    i = 0
    while i < len(seg):
        t = seg[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t) or t in WRAPPERS or (t.startswith("-") and i > 0 and seg[i - 1] in WRAPPERS):
            i += 1
            continue
        break
    return i


def _flag(args, *names):
    return any(a in names or any(a.startswith(n + "=") for n in names if n.startswith("--")) for a in args)


def _opt(args, *names):
    for i, a in enumerate(args):
        for n in names:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if n.startswith("--") and a.startswith(n + "="):
                return a.split("=", 1)[1]
    return None


def _norm_sub(args):
    words = []
    for a in args:
        if a.startswith("-"):
            continue
        words.append(a)
        if len(words) == 2:
            break
    sub = " ".join(words)
    for rx, rep in V3_NORMALIZE:
        sub = re.sub(rx, rep, sub)
    return sub


VALUE_FLAGS = {"-X", "--method", "-d", "--data", "-F", "--field", "-f", "--raw-field", "-H", "--header", "--input", "-i", "--fields", "--request", "--url", "-o", "--output", "-u", "--user"}


def _api_path(args):
    """First positional argument (the endpoint), skipping option values such as `-X POST`."""
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a in VALUE_FLAGS:
            skip = True
            continue
        if a.startswith("-"):
            continue
        if a == "api":
            continue
        p = re.sub(r"^https?://[^/]+", "", a)
        p = re.sub(r"^/?api/0", "", p)
        p = p.split("?", 1)[0]
        return "/" + p.lstrip("/")
    return ""


def _sentry_program(raw: str):
    """'sentry' | 'sentry-cli' when `raw` names the Sentry CLI (path, @version suffix or @sentry/cli package), else None."""
    m = re.match(r"^(@?[^@]+)(@[\w.\-]+)?$", raw)
    base = m.group(1) if m else raw
    if base == "@sentry/cli":
        return "sentry-cli"
    b = os.path.basename(base)
    return b if b in SENTRY_BINS else None


def classify(cmd: str):
    """Returns (verdict, reason, key): verdict in allow|deny|mutation. key identifies the mutation for approval lookup."""
    if tokens.has_token(cmd):
        return "deny", "A Sentry credential-shaped string is on the command line (shell history, process list, CI logs). Use an environment variable from the secret store; never paste a token.", None
    for seg in _segments(cmd):
        i = _program(seg)
        if i >= len(seg):
            continue
        prog = os.path.basename(seg[i])
        args = seg[i + 1:]
        if prog in ("bash", "sh", "zsh") and "-c" in args:
            j = args.index("-c")
            if j + 1 < len(args):
                v = classify(args[j + 1])
                if v[0] != "allow":
                    return v
            continue
        if prog in ("echo", "printf") and re.search(r"\$\{?SENTRY_(AUTH_)?TOKEN", " ".join(args)):
            return "deny", "Printing SENTRY_AUTH_TOKEN would put the token in the transcript. Test that it is set with `[ -n \"$SENTRY_AUTH_TOKEN\" ] && echo set`.", None
        if prog == "printenv" and any(re.match(r"SENTRY_(AUTH_)?TOKEN", a) for a in args):
            return "deny", "Printing the token would put it in the transcript. Test that it is set with `[ -n \"$SENTRY_AUTH_TOKEN\" ] && echo set`.", None
        if prog in READERS and any(CRED_FILES.search(a) for a in args):
            return "deny", "That file holds Sentry credentials; reading it prints them into the transcript. Audit with `git ls-files`, `git check-ignore -v <file>` or `sentry-ctx detect` (masked) instead.", None
        if prog in ("curl", "wget", "http", "https", "xh"):
            line = " ".join(seg)
            if re.search(r"sentry\.io/api/|\.sentry\.io", line):
                m = (_opt(args, "-X", "--request") or "").upper()
                body = any(a in ("-d", "--data", "--data-binary", "--data-raw", "--data-urlencode", "-F", "--form", "-T", "--upload-file", "--json") or a.startswith(("--data", "--form")) for a in args)
                if m in ("POST", "PUT", "PATCH", "DELETE") or (not m and body):
                    return "mutation", "curl/wget %s to the Sentry API" % (m or "POST"), "http %s %s" % (m or "POST", _api_path(args))
            continue
        which = _sentry_program(seg[i])
        if not which:
            continue
        # a sentry / sentry-cli invocation
        if args[:1] == ["auth"] and (args[1:2] == ["token"] or _flag(args, "--show-token")):
            return "deny", "That prints the raw Sentry token into the transcript. The plugin reuses the CLI login through `sentry api`; it never needs the token itself.", None
        sub = _norm_sub(args)
        if sub.startswith("event send") or sub.startswith("send-event"):
            if not _flag(args, "--no-environ"):
                return "deny", "`event send` attaches the whole process environment (every variable in this shell) to the event unless `--no-environ` is given. Add `--no-environ`.", None
            continue
        if sub.split(" ")[0] == "api":
            m = (_opt(args, "-X", "--method") or "").upper()
            body = _flag(args, "-d", "--data", "--input", "-F", "--field", "-f", "--raw-field")
            if m in ("POST", "PUT", "PATCH", "DELETE") or (not m and body):
                return "mutation", "sentry api %s %s" % (m or "POST", _api_path(args)), "api %s %s" % (m or "POST", _api_path(args))
            continue
        for mut in MUTATING:
            if sub == mut or sub.startswith(mut + " "):
                if mut == "init" and _flag(args, "--dry-run", "-n"):
                    break
                if mut == "monitor run":
                    break  # DSN check-ins around the user's own job: not an org mutation
                if _flag(args, "--dry-run", "-n") and mut != "init":
                    break
                return "mutation", "sentry %s" % sub, "cli " + mut
    return "allow", "", None


def run():
    inp = common.read_input()
    if common.mode() == "off":
        return
    ti = inp.get("tool_input") or {}
    cmd = ti.get("command") or ""
    if not cmd:
        return
    verdict, reason, key = classify(cmd)
    if verdict == "deny":
        common.decide("deny", reason)
        return
    if verdict != "mutation":
        return
    if inp.get("agent_type") in READ_AGENTS:
        common.decide("deny", "%s is a read-only agent and cannot change Sentry state (%s)." % (inp.get("agent_type"), reason))
        return
    root = common.project_dir(inp)
    st = runstate.load(root)
    if st:
        if key and key.startswith("cli "):
            if runstate.cli_is_approved(st, key[4:]):
                return
        elif key and (key.startswith("api ") or key.startswith("http ")):
            _, method, path = (key.split(" ", 2) + ["", ""])[:3]
            if runstate.write_is_approved(st, method, path):
                return
    common.decide("ask", "This changes Sentry state: %s. Confirm it, or record the approval first with `sentry-ctx run approve-write` (REST: --method M <path>, CLI: --cli \"<subcommand>\"). Seer runs (`issue explain|plan`) spend money." % reason)
