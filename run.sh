#!/usr/bin/env bash
# Run CheckMod from source on Linux/macOS.
#   ./run.sh
# Requires Python 3.9+ with Tk (Debian/Ubuntu: sudo apt install python3-tk).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec "${PYTHON:-python3}" -m checkmod "$@"
