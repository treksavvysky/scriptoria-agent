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

# The curation signal (design direction phase 4): records must not age at
# 'captured'. Lead the digest with the count so drift is visible daily.
curation_line="$(curl -sf --max-time 30 "$LIBRARY_URL/records?status=captured&limit=200" | python3 -c '
import json, sys
records = json.load(sys.stdin)
if not records:
    print("Shelves fully curated - nothing waiting at captured.")
else:
    oldest = min(r["timestamp"] for r in records)[:10]
    print(f"{len(records)} record(s) need curation (oldest: {oldest}).")
    print("Ritual: ask the scriptoria sub-agent to run a curation triage.")
' 2>/dev/null)" || curation_line=""

# The scriptorium sweep (Accessions Desk phase 4): drift in cardable
# workspaces — uncarded files, hash drift, cards whose draft is gone.
sweep_lines="$(LIBRARY_URL="$LIBRARY_URL" python3 "$REPO_DIR/scripts/scriptorium_sweep.py" 2>/dev/null)" || sweep_lines=""

if [ -n "$sweep_lines" ]; then
  digest="$sweep_lines

$digest"
fi

if [ -n "$curation_line" ]; then
  digest="$curation_line

$digest"
fi

# ntfy caps message bodies (~4 KiB); trim politely rather than get bounced.
if [ "${#digest}" -gt 3800 ]; then
  digest="${digest:0:3800}
…(truncated — full shelves at $LIBRARY_URL/digest)"
fi

curl -sf -X POST "$NTFY_URL" \
  -H "Authorization: Bearer $NTFY_TOKEN" \
  -H "Title: The Library — nightly digest" -H "Tags: books" \
  --data-binary "$digest" >/dev/null
