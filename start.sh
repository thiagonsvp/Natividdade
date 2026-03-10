#!/usr/bin/env bash
set -euo pipefail
PORT="${1:-5000}"
exec python3 app.py --port "$PORT"
