#!/usr/bin/env bash
# Install shivtrade-thesis-ingest.service — never touches shivtrade-kaaldrishti-feed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="$ROOT/deploy/shivtrade-thesis-ingest.service"
UNIT_DST="/etc/systemd/system/shivtrade-thesis-ingest.service"

mkdir -p /opt/shivtrade/research/thesis-feed/sessions
cp "$UNIT_SRC" "$UNIT_DST"
systemctl daemon-reload
systemctl enable shivtrade-thesis-ingest.service
systemctl restart shivtrade-thesis-ingest.service
echo "shivtrade-thesis-ingest started (shivtrade-kaaldrishti-feed not modified)."
