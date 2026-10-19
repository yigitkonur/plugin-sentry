from __future__ import annotations

import argparse
import sys

from . import paths, util


def _root(args):
    return paths.project_root(getattr(args, "path", None))


def cmd_version(args):
    util.emit({"version": paths.plugin_version(), "root": paths.plugin_root()}, args.json)


def cmd_doctor(args):
    from . import doctor
    d = doctor.run(_root(args), want_auth=not args.no_auth)
    if args.json:
        util.emit(d)
    else:
        print(doctor.render_text(d))


def build_parser():
    p = argparse.ArgumentParser(prog="sentry-ctx", description="Engine behind the `sentry` Claude Code plugin")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--path", default=None, help="project directory (default: CLAUDE_PROJECT_DIR or git root)")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("version").set_defaults(fn=cmd_version)
    d = sub.add_parser("doctor", help="tools, login, scopes, regions, coexistence")
    d.add_argument("--no-auth", action="store_true")
    d.set_defaults(fn=cmd_doctor)
    from . import registry
    registry.register(sub)
    return p


def main(argv):
    # Hooks bypass argparse to stay cheap.
    if argv and argv[0] == "hook":
        from .hooks import dispatch
        return dispatch(argv[1:])
    parser = build_parser()
    args, rest = parser.parse_known_args(argv)
    if not getattr(args, "fn", None):
        parser.print_help()
        return 2
    # allow --json / --path after the subcommand too
    if "--json" in rest:
        args.json = True
        rest.remove("--json")
    if rest:
        parser.error("unrecognized arguments: " + " ".join(rest))
    try:
        rc = args.fn(args)
        return rc or 0
    except util.EngineError as e:
        sys.stderr.write("sentry-ctx: %s\n" % e)
        return e.code
    except BrokenPipeError:
        return 0
