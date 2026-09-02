"""PyInstaller entry point.

A tiny module rather than pointing PyInstaller at ``checkmod/__main__.py``:
keeping the entry script outside the package avoids the double-import that
``__main__`` inside a package causes when frozen.
"""

from __future__ import annotations

import os
import sys

# When frozen, the bundle root is the parent of this file's directory.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from checkmod.app import main  # noqa: E402  (path juggling must come first)

if __name__ == "__main__":
    sys.exit(main())
