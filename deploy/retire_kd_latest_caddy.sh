#!/usr/bin/env bash
# Step 7 — retire public KD conviction path; no UI fallback to /api/kaaldrishti/latest.
set -euo pipefail

CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
STAMP="$(date -u +%Y%m%dT%H%MZ)"
cp -a "$CADDYFILE" "${CADDYFILE}.bak-kd-retire-${STAMP}"

python3 - "$CADDYFILE" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text()
block = """    handle /api/kaaldrishti/latest {
        respond "KAALDRISHTI conviction endpoint retired — use THESIS /trade and read-only /external_signals." 404
    }"""
pattern = re.compile(
    r"    handle /api/kaaldrishti/latest \{\n"
    r"        reverse_proxy 127\.0\.0\.1:5091\n"
    r"    \}\n",
    re.M,
)
if pattern.search(text):
    text = pattern.sub(block + "\n", text, count=1)
elif "KAALDRISHTI conviction endpoint retired" not in text:
    raise SystemExit("Could not find /api/kaaldrishti/latest reverse_proxy block in Caddyfile")
path.write_text(text)
print("patched", path)
PY

caddy validate --config "$CADDYFILE"
systemctl reload caddy
echo "Caddy reloaded — /api/kaaldrishti/latest now 404."
