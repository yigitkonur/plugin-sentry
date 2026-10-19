"""Hook entry points. bin/../hooks/run.sh prefilters in bash and calls `sentry-ctx hook <name>` only on a hit."""
from __future__ import annotations

import sys


def dispatch(argv):
    name = argv[0] if argv else ""
    try:
        if name == "session-start":
            from . import session_start as m
        elif name == "guard-write":
            from . import guard_write as m
        elif name == "gate-bash":
            from . import gate_bash as m
        elif name == "stale-api":
            from . import stale_api as m
        elif name == "stop-gate":
            from . import stop_gate as m
        else:
            return 0
        m.run()
    except Exception as e:  # a hook bug must never block the user's work
        sys.stderr.write("sentry hook %s failed open: %s\n" % (name, e))
    return 0
