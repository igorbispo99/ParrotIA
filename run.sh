#!/usr/bin/env bash
# Launch the Audio Transcriber GUI.
# Edit PYTHON below if your Python is not on PATH (e.g. a specific conda env).
PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$PYTHON" "$SCRIPT_DIR/app.py"
