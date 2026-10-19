"""`sentry-ctx clean`: remove run artifacts. Dry-run unless --yes. Deletes only inside .sentry-plugin/ and registered temp triggers."""
from __future__ import annotations

import os
import shutil

from . import paths, runstate, util


def plan(root, keep):
    sd = paths.state_dir(root)
    st = runstate.load(root) or {}
    triggers = [t["path"] for t in runstate.live_triggers(root, st)]
    state_exists = os.path.isdir(sd)
    remove, keepers = [], []
    if state_exists:
        for name in sorted(os.listdir(sd)):
            if keep == "all" or (keep == "policy" and name == "policy.md"):
                keepers.append(name)
            else:
                remove.append(name)
    return {
        "state_dir": os.path.relpath(sd, root) if state_exists else None,
        "remove": remove, "keep": keepers, "temp_triggers_to_delete": triggers,
        "gitignore_line_added_by_plugin": bool(st.get("gitignore_added_by_plugin")),
    }


def execute(root, keep, gitignore_line):
    p = plan(root, keep)
    sd = paths.state_dir(root)
    done = {"deleted_triggers": [], "deleted": [], "gitignore": "unchanged"}
    for rel in p["temp_triggers_to_delete"]:
        safe = util.rel_inside(root, rel)
        if safe:
            fp = os.path.join(root, safe)
            if os.path.isdir(fp):
                shutil.rmtree(fp)
            else:
                os.remove(fp)
            done["deleted_triggers"].append(safe)
    for name in p["remove"]:
        fp = os.path.join(sd, name)
        if os.path.isdir(fp):
            shutil.rmtree(fp)
        else:
            os.remove(fp)
        done["deleted"].append(name)
    if os.path.isdir(sd) and not os.listdir(sd):
        os.rmdir(sd)
    if gitignore_line == "remove" and p["gitignore_line_added_by_plugin"] and not os.path.isdir(sd):
        gi = os.path.join(root, ".gitignore")
        if os.path.isfile(gi):
            line = paths.STATE_DIRNAME + "/"
            lines = [l for l in util.read_text(gi).splitlines() if l.strip() != line]
            util.write_text(gi, "\n".join(lines) + ("\n" if lines else ""))
            done["gitignore"] = "line removed"
    return done
