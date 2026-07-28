"""Allow ``python -m ddd`` in addition to the installed ``ddd`` script."""

from __future__ import annotations

import sys

from ddd.cli import main

if __name__ == "__main__":
    sys.exit(main())
