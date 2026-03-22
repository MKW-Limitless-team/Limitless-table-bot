#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
LOG_FILE="$LOG_DIR/bot.out"
PID_FILE="$ROOT_DIR/bot.pid"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

mkdir -p "$LOG_DIR"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "${OLD_PID:-}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "Bot already appears to be running with PID $OLD_PID"
    exit 0
  fi
fi

cd "$ROOT_DIR"
nohup "$PYTHON_BIN" app.py >"$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "$NEW_PID" >"$PID_FILE"

echo "Started Limitless table bot in background."
echo "PID: $NEW_PID"
echo "Log: $LOG_FILE"
