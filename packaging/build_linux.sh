#!/usr/bin/env bash
# Build a portable CheckMod binary on Linux/macOS.
#
# Mirrors packaging/build_windows.ps1 so the recipe can be validated on CI
# runners that are not Windows. The Windows .exe must still be built on
# Windows: PyInstaller does not cross-compile.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV="$ROOT/.buildenv"

echo "==> CheckMod build ($ROOT)"
[ -d "$VENV" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip --quiet
"$VENV/bin/python" -m pip install "pyinstaller>=6.3" --quiet

echo "==> generating icon"
"$VENV/bin/python" tools/make_icon.py

echo "==> running PyInstaller (one file)"
"$VENV/bin/python" -m PyInstaller packaging/CheckMod.spec --noconfirm --clean

echo "==> running PyInstaller (one folder)"
"$VENV/bin/python" -m PyInstaller packaging/CheckModFolder.spec \
    --noconfirm --clean --distpath dist-folder

echo
echo "==> done"
ls -lh "$ROOT/dist/CheckMod"
ls -lh "$ROOT/dist-folder/CheckMod/CheckMod"
