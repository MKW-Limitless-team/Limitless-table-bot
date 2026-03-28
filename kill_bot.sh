#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT_DIR/bot.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "No bot PID file found. Bot does not appear to be running."
  exit 0
fi

BOT_PID="$(cat "$PID_FILE" 2>/dev/null || true)"

if [[ -z "${BOT_PID:-}" ]]; then
  rm -f "$PID_FILE"
  echo "PID file was empty. Removed stale PID file."
  exit 0
fi

if ! kill -0 "$BOT_PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "No running process found for PID $BOT_PID. Removed stale PID file."
  exit 0
fi

kill "$BOT_PID"
rm -f "$PID_FILE"

echo "Stopped Limitless table bot."
echo "PID: $BOT_PID"
