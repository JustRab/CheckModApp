"""Allow ``python -m checkmod`` to launch the application."""

from __future__ import annotations

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
