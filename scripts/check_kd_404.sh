#!/usr/bin/env bash
# CI hook — public KD conviction path must stay retired (404).
set -euo pipefail

URL="${KD_LATEST_URL:-https://shivatrade.store/api/kaaldrishti/latest}"
TIMEOUT="${KD_CURL_TIMEOUT_SEC:-15}"

code="$(curl -sS -m "$TIMEOUT" -o /dev/null -w '%{http_code}' "$URL" || echo "000")"
echo "GET $URL -> HTTP $code"

if [[ "$code" == "404" ]]; then
  exit 0
fi

echo "Expected HTTP 404 for retired KD conviction endpoint" >&2
exit 1
