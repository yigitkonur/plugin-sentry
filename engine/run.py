# Entry point used by bin/sentry-ctx. Runs with `python3 -I -S`, so the package
# directory is added explicitly (isolated mode ignores PYTHONPATH and cwd).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sentry_ctx.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
