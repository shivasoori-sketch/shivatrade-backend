#!/usr/bin/env bash
# Shadow stack launcher (nohup) — does NOT touch Kite systemd.
set -euo pipefail
ROOT="/opt/shivtrade/upstox_migration"
PY="/opt/shivtrade/.venv/bin/python3"
LOG="$ROOT/logs"
mkdir -p "$LOG" "$ROOT/sessions" "$ROOT/state/fabric_buckets"
for svc in thesis fabric live; do
  pkill -f "upstox_${svc}.py" 2>/dev/null || true
done
sleep 1
nohup "$PY" "$ROOT/upstox_thesis_ingest.py" >>"$LOG/thesis.log" 2>&1 &
nohup "$PY" "$ROOT/upstox_fabric.py" >>"$LOG/fabric.log" 2>&1 &
nohup "$PY" "$ROOT/upstox_live.py" >>"$LOG/live.log" 2>&1 &
echo "started shadow PIDs: $(pgrep -af 'upstox_(thesis|fabric|live)' || true)"
