"""Double-click launcher for running CheckMod from source on Windows.

The ``.pyw`` extension is associated with ``pythonw.exe``, which starts the
app without a console window - the same experience as the built executable,
but straight from the repository. Useful while customising the app or when a
team prefers to review the source before running a binary.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from checkmod.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
