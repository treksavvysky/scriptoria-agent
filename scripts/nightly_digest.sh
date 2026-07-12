#!/usr/bin/env bash
# Nightly ritual: the librarian reads the shelves aloud.
# Pulls the Library digest and publishes it to the ntfy 'library' topic.
# Cron-friendly: config comes from the repo .env (NTFY_TOKEN) unless already set.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -z "${NTFY_TOKEN:-}" ] && [ -f "$REPO_DIR/.env" ]; then
  # shellcheck disable=SC1091
  . "$REPO_DIR/.env"
fi

LIBRARY_URL="${LIBRARY_URL:-http://127.0.0.1:8021}"
NTFY_URL="${NTFY_URL:-https://ntfy.codejourney.com/library}"
: "${NTFY_TOKEN:?NTFY_TOKEN not set (expected in $REPO_DIR/.env)}"

digest="$(curl -sf --max-time 30 "$LIBRARY_URL/digest?limit=50")" || {
  curl -sf -X POST "$NTFY_URL" \
    -H "Authorization: Bearer $NTFY_TOKEN" \
    -H "Title: The Library — digest failed" -H "Tags: warning,books" \
    -d "The librarian could not reach The Library at $LIBRARY_URL. Is the cortex-library container running?" >/dev/null
  exit 1
}

# ntfy caps message bodies (~4 KiB); trim politely rather than get bounced.
if [ "${#digest}" -gt 3800 ]; then
  digest="${digest:0:3800}
…(truncated — full shelves at $LIBRARY_URL/digest)"
fi

curl -sf -X POST "$NTFY_URL" \
  -H "Authorization: Bearer $NTFY_TOKEN" \
  -H "Title: The Library — nightly digest" -H "Tags: books" \
  --data-binary "$digest" >/dev/null
