"""H4: gate shell commands that touch Sentry.

deny  : anything that prints or copies a raw credential, a token on a command line, `event send` without --no-environ,
        a credential file written where git would track it, a hand edit of the run state (approvals), and any Sentry mutation
        from the read-only auditor agent.
ask   : every outward-facing Sentry mutation the user has not approved in THIS run and session, and every attempt to record
        an approval (a human sees the exact command; `SENTRY_PLUGIN_APPROVE_WRITES=1` in the operator's environment, which the
        model cannot set for the hook process, turns that prompt off for CI and tests).
Every segment of a compound command is inspected: a denial anywhere denies the whole command, and every mutation in it must be
approved on its own. Reads are never gated. Best-effort parsing: a guard rail for an agent, not a sandbox.
"""
from __future__ import annotations

import os
import re
import shlex

from .. import runstate, tokens, util
from . import common

WRAPPERS = {"env", "sudo", "command", "time", "nohup", "exec", "xargs", "npx", "pnpx", "bunx", "dlx", "--yes", "-y", "--no-install", "--", "builtin", "nice", "timeout", "gtimeout"}
SENTRY_BINS = {"sentry", "sentry-cli"}
READ_AGENTS = {"sentry:auditor"}  # the verifier may run mutations the user approved in this run (artifact uploads); nothing else

# command-word pairs (v4 names; v3 names are normalized below) that change state or spend money
MUTATING = {
    "issue resolve", "issue unresolve", "issue archive", "issue merge", "issue explain", "issue plan",
    "project create", "project delete", "project remove", "project rm",
    "release create", "release new", "release finalize", "release delete", "release archive", "release restore", "release deploy", "release set-commits",
    "sourcemap upload", "debug-files upload", "proguard upload", "code-mappings upload", "build upload", "dart-symbol-map upload",
    "feedback resolve", "feedback unresolve", "feedback spam", "dashboard create", "dashboard widget", "dashboard restore",
    "trial start", "init", "snapshots upload",
}
SEER = {"issue explain", "issue plan"}
V3_PAIRS = {
    ("releases", "new"): "release create", ("releases", "finalize"): "release finalize", ("releases", "delete"): "release delete",
    ("releases", "archive"): "release archive", ("releases", "restore"): "release restore", ("releases", "set-commits"): "release set-commits",
    ("deploys", "new"): "release deploy", ("sourcemaps", "upload"): "sourcemap upload", ("issues", "resolve"): "issue resolve",
    ("issues", "mute"): "issue archive", ("issues", "unresolve"): "issue unresolve", ("projects", "create"): "project create",
}
V3_SINGLE = {"upload-dif": "debug-files upload", "upload-dsym": "debug-files upload", "upload-proguard": "proguard upload"}
CRED_FILES = re.compile(r"(\.sentryclirc|\.env\.sentry-build-plugin|sentry\.properties|SentryCliOptions\.asset|sentry/cli\.db)")
READERS = {"cat", "less", "more", "head", "tail", "grep", "egrep", "rg", "sed", "awk", "bat", "strings", "xxd", "hexdump", "sqlite3", "cp", "mv", "open", "code", "vim", "nano", "base64"}
STATE_FILE = re.compile(r"\.sentry-plugin/run\.json|(?<![\w/.-])run\.json")
INTERPRETERS = {"python", "python3", "python3.9", "python3.14", "perl", "ruby", "node", "bun", "deno", "php", "sh", "bash", "zsh"}


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


def _nested(cmd: str):
    """Command substitutions and process substitutions inside a command string (one level; callers recurse)."""
    out = []
    depth, start = 0, None
    i = 0
    while i < len(cmd):
        if cmd.startswith("$(", i) or cmd.startswith("<(", i) or cmd.startswith(">(", i):
            if depth == 0:
                start = i + 2
            depth += 1
            i += 2
            continue
        if depth and cmd[i] == "(":
            depth += 1
        elif depth and cmd[i] == ")":
            depth -= 1
            if depth == 0 and start is not None:
                out.append(cmd[start:i])
                start = None
        i += 1
    out += re.findall(r"`([^`]+)`", cmd)
    return out


def _program(seg):
    """Index of the real program in a segment, skipping env assignments and wrappers (and their option values)."""
    i = 0
    while i < len(seg):
        t = seg[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t) or t in WRAPPERS:
            i += 1
            continue
        if t.startswith("-") and i > 0 and seg[i - 1] in WRAPPERS:
            i += 1
            continue
        if i > 0 and seg[i - 1] in ("timeout", "gtimeout") and re.match(r"^\d+[smhd]?$", t):
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


def _words(args):
    return [a for a in args if not a.startswith("-")]


def _mutation_in(args):
    """The mutating command pair anywhere in the non-option words. A sliding window, so global options with values
    (`sentry --org acme issue plan X`) cannot hide the subcommand."""
    w = _words(args)
    for i in range(len(w)):
        if w[i] in V3_SINGLE:
            return V3_SINGLE[w[i]]
        if i + 1 < len(w):
            pair = (w[i], w[i + 1])
            if pair in V3_PAIRS:
                return V3_PAIRS[pair]
            if " ".join(pair) in MUTATING:
                return " ".join(pair)
    sw = _words_skipping_values(args)
    if sw and sw[0] == "init":
        return "init"
    return None


GLOBAL_VALUE_FLAGS = {"--org", "--project", "--url", "--log-level", "--fields", "--team", "-t", "-n", "--limit", "-q", "--query"}


def _words_skipping_values(args):
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in GLOBAL_VALUE_FLAGS:
            skip = True
            continue
        if not a.startswith("-"):
            out.append(a)
    return out


def _has_pair(args, a, b):
    w = _words(args)
    return any(w[i] == a and w[i + 1] == b for i in range(len(w) - 1))


VALUE_FLAGS = {"-X", "--method", "-d", "--data", "-F", "--field", "-f", "--raw-field", "-H", "--header", "--input", "-i", "--fields", "--request", "--url", "-o", "--output", "-u", "--user", "--org", "--project", "--log-level"}


def _api_path(args):
    """The endpoint of a `sentry api` call: the first positional after the `api` word, skipping option values."""
    try:
        start = _words(args).index("api")
    except ValueError:
        start = -1
    seen_api = False
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
        if not seen_api:
            seen_api = a == "api"
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


REDIRECT_RX = re.compile(r"""(?:^|[\s;&|(])(?:\d?>>?|&>>?)\s*(?:"([^"]+)"|'([^']+)'|([^\s;&|<>()]+))""")


def cred_write_targets(cmd: str):
    """Paths a command writes to that are named like a Sentry credential file (redirects, tee, cp/mv/install, sed -i, dd of=)."""
    out = []
    for m in REDIRECT_RX.finditer(cmd):
        out.append(next(g for g in m.groups() if g))
    for seg in _segments(cmd):
        i = _program(seg)
        if i >= len(seg):
            continue
        prog, args = os.path.basename(seg[i]), seg[i + 1:]
        pos = [a for a in args if not a.startswith("-")]
        if prog == "tee":
            out += pos
        elif prog in ("cp", "mv", "install", "ln") and len(pos) >= 2:
            out.append(pos[-1])
        elif prog in ("sed", "perl") and any(a.startswith("-i") or a.startswith("-pi") for a in args):
            out += pos[1:]
        elif prog == "dd":
            out += [a[3:] for a in args if a.startswith("of=")]
    return [t for t in out if CRED_FILES.search(t)]


def _touches_state(cmd: str):
    """Hand edits of the run state (it holds the approvals). Reading is fine."""
    if not STATE_FILE.search(cmd):
        return False
    for seg in _segments(cmd):
        i = _program(seg)
        if i >= len(seg):
            continue
        prog, args = os.path.basename(seg[i]), seg[i + 1:]
        line = " ".join(seg)
        if not STATE_FILE.search(line):
            continue
        if prog in ("cat", "head", "tail", "jq", "grep", "egrep", "rg", "ls", "wc", "stat", "less", "more", "diff", "cmp", "file", "sentry-ctx"):
            continue
        if prog in INTERPRETERS or prog in ("sed", "awk", "tee", "cp", "mv", "rm", "truncate", "dd", "install", "ln", "ed", "ex", "vi", "vim", "nano", "git"):
            if prog in ("sed", "awk") and not any(a.startswith("-i") for a in args):
                continue
            if prog in INTERPRETERS and not re.search(r"""['"]w\+?b?['"]|['"]a\+?['"]|write|dump\(|writeFile|File\.open|>>?\s*|os\.replace|rename|unlink|remove""", line):
                continue
            return True
    if re.search(r"(?:>|>>)\s*\S*run\.json", cmd):
        return True
    return False


def _approve_cmd(prog_base, args):
    """`sentry-ctx run approve-write` / `run adopt` (they record consent or take over a run)."""
    if prog_base != "sentry-ctx":
        return False
    w = _words(args)
    return len(w) >= 2 and w[0] == "run" and w[1] in ("approve-write",)


def classify(cmd: str, depth: int = 0):
    """Returns (verdict, reason, keys): verdict allow|deny|mutation|approval. `keys` lists the mutations to look up:
    ('cli', normalized command line) or ('api', METHOD, path)."""
    if tokens.has_token(cmd):
        return "deny", "A Sentry credential-shaped string is on the command line (shell history, process list, CI logs). Use an environment variable from the secret store; never paste a token.", []
    if _touches_state(cmd):
        return "deny", "That edits the run state (.sentry-plugin/run.json), which holds the user's approvals. Approvals are recorded only with `sentry-ctx run approve-write`, which asks the user.", []
    mutations, approval = [], False
    seen = set()
    stack = [cmd]
    while stack:
        c = stack.pop()
        if c in seen or len(seen) > 40:
            continue
        seen.add(c)
        if depth < 3:
            stack.extend(_nested(c))
        for seg in _segments(c):
            res = _classify_segment(seg, depth)
            if res is None:
                continue
            verdict, reason, keys = res
            if verdict == "deny":
                return "deny", reason, []
            if verdict == "approval":
                approval = True
            elif verdict == "mutation":
                mutations.append((reason, keys))
    # last resort for forms the parser could not see (a mutation named inside a string handed to an interpreter): Seer spends money
    if not mutations and re.search(r"\bsentry(?:-cli)?\b[^\n;|&]*\bissues?\s+(?:explain|plan)\b", cmd):
        mutations.append(("sentry issue explain|plan (Seer run, spends budget)", [("seer", cmd)]))
    if mutations:
        return "mutation", "; ".join(r for r, _ in mutations), [k for _, ks in mutations for k in ks]
    if approval:
        return "approval", "records an approval for a Sentry write", []
    return "allow", "", []


def _classify_segment(seg, depth):
    i = _program(seg)
    if i >= len(seg):
        return None
    prog = os.path.basename(seg[i])
    args = seg[i + 1:]
    if prog in ("bash", "sh", "zsh") and "-c" in args:
        j = args.index("-c")
        if j + 1 < len(args):
            return _classify_inner(args[j + 1], depth)
        return None
    if prog == "eval":
        return _classify_inner(" ".join(args), depth)
    if prog == "find" and ("-exec" in args or "-execdir" in args):
        k = args.index("-exec") if "-exec" in args else args.index("-execdir")
        tail = []
        for a in args[k + 1:]:
            if a in (";", "\\;", "+"):
                break
            tail.append(a)
        return _classify_inner(" ".join(shlex.quote(t) for t in tail), depth)
    if _approve_cmd(prog, args):
        return "approval", "records an approval", []
    if prog in ("echo", "printf") and re.search(r"\$\{?SENTRY_(AUTH_)?TOKEN", " ".join(args)):
        return "deny", "Printing SENTRY_AUTH_TOKEN would put the token in the transcript. Test that it is set with `[ -n \"$SENTRY_AUTH_TOKEN\" ] && echo set`.", []
    if prog == "printenv" and any(re.match(r"SENTRY_(AUTH_)?TOKEN", a) for a in args):
        return "deny", "Printing the token would put it in the transcript. Test that it is set with `[ -n \"$SENTRY_AUTH_TOKEN\" ] && echo set`.", []
    if prog in READERS and any(CRED_FILES.search(a) for a in args):
        return "deny", "That file holds Sentry credentials; reading it prints them into the transcript. Audit with `git ls-files`, `git check-ignore -v <file>` or `sentry-ctx detect` (masked) instead.", []
    if prog in ("curl", "wget", "http", "https", "xh"):
        line = " ".join(seg)
        if re.search(r"sentry\.io/api/|\.sentry\.io", line):
            m = (_opt(args, "-X", "--request") or "").upper()
            body = any(a in ("-d", "--data", "--data-binary", "--data-raw", "--data-urlencode", "-F", "--form", "-T", "--upload-file", "--json") or a.startswith(("--data", "--form")) for a in args)
            if m in ("POST", "PUT", "PATCH", "DELETE") or (not m and body):
                return "mutation", "curl/wget %s to the Sentry API" % (m or "POST"), [("api", m or "POST", _api_path(args) or _url_path(args))]
        return None
    which = _sentry_program(seg[i])
    if not which:
        return None
    if _flag(args, "--help", "-h", "--version"):
        return None  # help and version output never change state
    w = _words(args)
    if w[:1] == ["auth"] and (w[1:2] == ["token"] or _flag(args, "--show-token")) or (_flag(args, "--show-token") and "auth" in w):
        return "deny", "That prints the raw Sentry token into the transcript. The plugin reuses the CLI login through `sentry api`; it never needs the token itself.", []
    if w[:2] == ["auth", "status"]:
        return "deny", "`sentry auth status` prints part of the login token (first and last characters). Use `sentry-ctx doctor` instead: it shows who is logged in, the org, region and scopes without any token text.", []
    if (_has_pair(args, "event", "send") or "send-event" in w) and not _flag(args, "--no-environ"):
        return "deny", "`event send` attaches the whole process environment (every variable in this shell) to the event unless `--no-environ` is given. Add `--no-environ`.", []
    if "api" in w:
        m = (_opt(args, "-X", "--method") or "").upper()
        body = _flag(args, "-d", "--data", "--input", "-F", "--field", "-f", "--raw-field")
        if m in ("POST", "PUT", "PATCH", "DELETE") or (not m and body):
            return "mutation", "sentry api %s %s" % (m or "POST", _api_path(args)), [("api", m or "POST", _api_path(args))]
        return None
    mut = _mutation_in(args)
    if mut:
        if mut == "init" and _flag(args, "--dry-run", "-n"):
            return None
        if _flag(args, "--dry-run", "-n") and mut != "init" and mut not in SEER:
            return None
        norm = " ".join(a for a in args if a not in ("--dry-run", "-n", "--json", "--yes"))
        return "mutation", "sentry %s%s" % (mut, " (Seer run, spends budget)" if mut in SEER else ""), [("cli", runstate._norm_cli(norm), mut)]
    return None


def _url_path(args):
    for a in args:
        m = re.search(r"sentry\.io/api/0(/[^\s?\"']*)", a)
        if m:
            return m.group(1)
    return ""


def _classify_inner(inner, depth):
    if depth >= 3:
        return "deny", "Too deeply nested shell: run the Sentry command directly.", []
    v, reason, keys = classify(inner, depth + 1)
    if v == "allow":
        return None
    return v, reason, keys


def _approved(st, key, session_id):
    kind = key[0]
    if kind == "cli":
        return runstate.cli_is_approved(st, key[1], session_id)
    if kind == "api":
        return runstate.write_is_approved(st, key[1], key[2], session_id)
    return False  # seer: needs an explicit class approval below


def run():
    inp = common.read_input()
    if common.mode() == "off":
        return
    ti = inp.get("tool_input") or {}
    cmd = ti.get("command") or ""
    if not cmd:
        return
    verdict, reason, keys = classify(cmd)
    root = common.project_dir(inp)
    if verdict != "deny":
        cwd = inp.get("cwd") or root
        for t in cred_write_targets(cmd):
            ap = t if os.path.isabs(t) else os.path.join(cwd, t)
            rel = os.path.relpath(ap, root)
            if rel.startswith("..") or not util.is_git_repo(root):
                continue  # outside the repo (e.g. ~/.sentryclirc) or no git: nothing can commit it
            rc, _, _ = util.git(root, "check-ignore", "-q", rel)
            if rc != 0:
                verdict, reason = "deny", ("This command writes %s, a Sentry credential file that git does not ignore: one `git add .` would commit the token. "
                                           "Add it to .gitignore first (and `git check-ignore -v %s` must print the rule), then write it. The token itself still never goes on a command line." % (rel, rel))
                break
    if verdict == "deny":
        common.decide("deny", reason)
        return
    if verdict == "approval":
        if os.environ.get("SENTRY_PLUGIN_APPROVE_WRITES") == "1":
            return
        common.decide("ask", "This records the user's approval for a Sentry write (%s). Only approve it if you asked for exactly this operation; the run will treat it as your consent." % cmd[:300])
        return
    if verdict != "mutation":
        return
    if inp.get("agent_type") in READ_AGENTS:
        common.decide("deny", "%s is a read-only agent and cannot change Sentry state (%s)." % (inp.get("agent_type"), reason))
        return
    st = runstate.load(root)
    sid = inp.get("session_id")
    pending = [k for k in keys if not _approved(st, k, sid)]
    if not pending:
        return
    seer = any(k[0] == "seer" or (k[0] == "cli" and len(k) > 2 and k[2] in SEER) for k in pending)
    common.decide("ask", "This changes Sentry state: %s. %s Record the approval first (the user is asked): `sentry-ctx run approve-write` (REST: --method M <exact path>, CLI: --cli \"<command>\"), always in this run and session. Seer runs (`issue explain|plan`) spend money." % (reason, "It includes a Seer run, which spends budget." if seer else ""))
