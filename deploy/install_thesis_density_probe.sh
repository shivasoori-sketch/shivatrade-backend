#!/usr/bin/env bash
# Optional one-shot / timer density probe unit (independent KiteTicker).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="$ROOT/deploy/shivtrade-thesis-density-probe.service"
UNIT_DST="/etc/systemd/system/shivtrade-thesis-density-probe.service"
install -m 644 "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload
echo "Installed $UNIT_DST (run: systemctl start shivtrade-thesis-density-probe.service)"
