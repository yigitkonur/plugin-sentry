"""Port `sentry-cli` 3.x invocations found in CI files and scripts to the `sentry` v4 CLI.

Deterministic and conservative: a line is rewritten only when its subcommand has a known v4 counterpart (data/cli-map.json is the
reference table); flags without a v4 equivalent are reported, never silently dropped. The auditor puts this table in the
`rel.cli-version` finding and the implementer applies it line by line.
"""
from __future__ import annotations

import re
import shlex

# (v3 subcommand words, v4 subcommand words)
SUB = [
    (("releases", "new"), ("release", "create")),
    (("releases", "finalize"), ("release", "finalize")),
    (("releases", "set-commits"), ("release", "set-commits")),
    (("releases", "propose-version"), ("release", "propose-version")),
    (("releases", "info"), ("release", "view")),
    (("releases", "list"), ("release", "list")),
    (("releases", "delete"), ("release", "delete")),
    (("releases", "archive"), ("release", "archive")),
    (("releases", "restore"), ("release", "restore")),
    (("releases", "deploys"), ("release", "deploys")),
    (("deploys", "new"), ("release", "deploy")),
    (("deploys", "list"), ("release", "deploys")),
    (("sourcemaps", "upload"), ("sourcemap", "upload")),
    (("sourcemaps", "inject"), ("sourcemap", "inject")),
    (("sourcemaps", "resolve"), ("sourcemap", "resolve")),
    (("debug-files", "upload"), ("debug-files", "upload")),
    (("debug-files", "check"), ("debug-files", "check")),
    (("upload-dif",), ("debug-files", "upload")),
    (("upload-dsym",), ("debug-files", "upload")),
    (("difutil", "check"), ("debug-files", "check")),
    (("upload-proguard",), ("proguard", "upload")),
    (("proguard", "upload"), ("proguard", "upload")),
    (("monitors", "run"), ("monitor", "run")),
    (("monitors", "list"), ("monitor", "list")),
    (("send-event",), ("event", "send")),
    (("login",), ("auth", "login")),
    (("logout",), ("auth", "logout")),
    (("update",), ("cli", "upgrade")),
    (("organizations", "list"), ("org", "list")),
    (("projects", "list"), ("project", "list")),
    (("repos", "list"), ("repo", "list")),
    (("issues", "list"), ("issue", "list")),
    (("issues", "resolve"), ("issue", "resolve")),
    (("issues", "mute"), ("issue", "archive")),
]
NO_V4_FLAGS = {
    "--ignore-missing": "set-commits has no --ignore-missing: append `|| true` where a missing base commit must not fail the job",
    "--validate": "no v4 flag (Debug IDs match by id; drop it)", "--wait": None, "--wait-for": "no v4 flag", "--note": "no v4 flag",
    "--decompress": "no v4 flag", "--url-suffix": "no v4 flag", "--no-sourcemap-reference": "no v4 flag",
    "--symbol-maps": "no v4 flag", "--allow-failure": "removed: append `|| true`", "--quiet": "no global equivalent: redirect output", "--silent": "no global equivalent: redirect output",
}


HERMES_NOTE = ("`--debug-id-reference` has no v4 equivalent and the line must stay on sentry-cli 3: for a Hermes bytecode bundle, sentry-cli 3 uploads an empty placeholder that carries the map's Debug ID. `sentry sourcemap upload` 0.47.0 cannot do that (the bytecode file gives `js_no_source`, and the placeholder it rewrites gives `js_invalid_sourcemap_location`; observed 2026-10-21). Keep the React Native SDK's own upload (Xcode/Gradle build phase, `@sentry/expo-upload-sourcemaps`)")


def _tokens(cmd: str):
    try:
        return shlex.split(cmd, posix=True)
    except ValueError:
        return cmd.split()


ARG = r"""(?:"[^"]*"|'[^']*'|\$\{\{[^}]*\}\}|\S+)"""


def _flag_value(tail: str, names):
    m = re.search(r"(?:(?<=\s)|^)(?:%s)(?:=|\s+)(%s)" % ("|".join(re.escape(n) for n in names), ARG), tail)
    return m


def port_line(text: str):
    """Returns None when the line has no `sentry-cli` call, else {'v4': str, 'notes': [..]}. Works on the raw text so quoting is kept.
    A line with several calls (`sentry-cli releases new "$(sentry-cli releases propose-version)"`) is ported one call at a time."""
    out = _port_one(text)
    for _ in range(4):
        if not out or not out["v4"] or not V3_CALL.search(out["v4"]):
            break
        more = _port_one(out["v4"])
        if not more or not more["v4"] or more["v4"] == out["v4"]:
            break
        out = {"v4": more["v4"], "notes": out["notes"] + [n for n in more["notes"] if n not in out["notes"]]}
    return out


V3_CALL = re.compile(r"\bsentry-cli\b|@sentry/cli\b")


def _port_one(text: str):
    t = text.strip()
    if re.search(r"(?:npm|pnpm|yarn)\s+(?:i|install|add)\s+(?:-g\s+|--global\s+)?@sentry/cli\b", t):
        return {"v4": re.sub(r"@sentry/cli(@\S+)?", "sentry", t), "notes": ["the v4 CLI is the npm package `sentry` (it installs the `sentry` binary); pin an exact version", "or: curl https://cli.sentry.dev/install -fsS | bash"]}
    if re.search(r"get-cli", t):
        return {"v4": "curl https://cli.sentry.dev/install -fsS | bash", "notes": ["pin the version with SENTRY_VERSION for the install script"]}
    m = re.search(r"\b((?:npx\s+(?:--yes\s+)?(?:@sentry/cli(?:@\S+)?|sentry-cli))|sentry-cli)\s+(.*)$", t)
    if not m or re.match(r"^(name|id|description|uses)\s*:", t.lstrip("- ")):
        return None
    prefix, tail = t[: m.start()], m.group(2)
    notes = []
    words = None
    for v3, v4 in sorted(SUB, key=lambda sb: -len(sb[0])):
        mm = re.match(r"^" + r"\s+".join(re.escape(w) for w in v3) + r"\b\s*", tail)
        if mm:
            words, tail = v4, tail[mm.end():]
            break
    if words is None:
        w2 = " ".join(tail.split()[:2])
        return {"v4": None, "notes": ["no known v4 counterpart for `sentry-cli %s`: check `sentry-ctx cli-map --v3 \"%s\"`" % (w2, w2)]}
    sub = " ".join(words)
    if sub == "sourcemap upload" and re.search(r"(?:(?<=\s)|^)--debug-id-reference(?=\s|$)", tail):
        return {"v4": None, "notes": [HERMES_NOTE]}
    suffix = ""
    mt = _flag_value(tail, ["--auth-token"])
    if mt:
        tail = (tail[: mt.start()] + tail[mt.end():]).replace("  ", " ")
        notes.append("`--auth-token` is gone: authenticate with the stored login (`sentry auth login`) or the SENTRY_AUTH_TOKEN environment variable from the CI secret store; never on the command line")
    tail = re.sub(r"(?<=\s)-o(?=[\s=])", "--org", " " + tail).strip()
    tail = re.sub(r"(?<=\s)-p(?=[\s=])", "--project", " " + tail).strip()
    if sub == "release deploy":
        mr = _flag_value(tail, ["-r", "--release"])
        me = _flag_value(tail, ["-e", "--env"])
        mn = _flag_value(tail, ["-n", "--name"])
        pos = [x.group(1) for x in (mr, me, mn) if x]
        for x in sorted([x for x in (mr, me, mn) if x], key=lambda x: -x.start()):
            tail = (tail[: x.start()] + tail[x.end():])
        tail = (" ".join(pos) + " " + tail).strip()
    elif sub in ("sourcemap upload", "sourcemap inject", "debug-files upload"):
        tail = re.sub(r"(?<=\s)-r(?=[\s=])", "--release", " " + tail).strip()
    for flag, why in NO_V4_FLAGS.items():
        pat = r"(?:(?<=\s)|^)%s(?:=\S+)?(?=\s|$)" % re.escape(flag)
        if re.search(pat, tail):
            tail = re.sub(pat, "", tail).strip()
            if flag == "--ignore-missing":
                suffix = " || true"
            if why:
                notes.append("`%s`: %s" % (flag, why))
    if sub == "event send" and "--no-environ" not in tail:
        tail = (tail + " --no-environ").strip()
        notes.append("`event send` attaches the whole process environment unless `--no-environ` is given")
    if sub == "release propose-version":
        # sentry 0.47.0 prints a "Detected from ..." hint on stdout after the version, so a captured value holds both lines.
        cut = re.search(r"[)`>|;&]", tail)
        at = cut.start() if cut else len(tail)
        tail = (tail[:at].rstrip() + " | head -n 1" + (" " if cut and tail[at] != ")" and tail[at] != "`" else "") + tail[at:]).strip()
        notes.append("`release propose-version` prints a second line (`Detected from ...`) on stdout; `| head -n 1` keeps only the version")
    if sub == "release create" and not re.search(r"\S+/\S+", tail.split()[0] if tail.split() else ""):
        notes.append("the organization comes from SENTRY_ORG, `--org`, or an `ORG/` prefix on the version")
    v4 = (prefix + "sentry " + sub + (" " + re.sub(r"\s+", " ", tail).strip() if tail.strip() else "") + suffix).strip()
    return {"v4": v4, "notes": notes}


def port_repo(detect: dict):
    rows = []
    seen = set()
    for r in (detect.get("ci") or {}).get("sentry_refs", []):
        if r.get("kind") != "sentry-cli-v3":
            continue
        key = (r["file"], r["line"])
        if key in seen:
            continue
        seen.add(key)
        p = port_line(r.get("text", ""))
        if p is None:
            continue
        rows.append({"file": r["file"], "line": r["line"], "v3": r.get("text", ""), "v4": p["v4"], "notes": p["notes"]})
    return {"count": len(rows), "rows": rows,
            "reference": "data/cli-map.json (`sentry-ctx cli-map`), https://cli.sentry.dev/migrating-from-v3.md",
            "also": "the SENTRY_ORG / SENTRY_PROJECT / SENTRY_AUTH_TOKEN environment variables are unchanged"}
