#!/usr/bin/env python3
"""The scriptorium sweep (Accessions Desk, phase 4) — drift signals.

Read-only: compares cardable workspaces against the Library's card drawer
and prints human-readable drift lines for the nightly digest. Reports,
never mutates — flagging is the ruling; silent re-carding is not.

A workspace opts in by containing a `.cardable` marker file (ruling 2:
scratch workspaces stay invisible by default). Signals:
  - uncarded: a file in a cardable workspace with no catalog card
  - drifted:  a carded draft whose content hash no longer matches its card
  - missing:  a card whose draft file is gone (operator decides its fate)

Env: LIBRARY_URL (default http://127.0.0.1:8021),
     SCRIPTORIA_WORKSPACES_ROOT (default ~/agents/workspaces).
"""

import hashlib
import json
import os
import pathlib
import sys
import urllib.request

LIBRARY_URL = os.environ.get("LIBRARY_URL", "http://127.0.0.1:8021").rstrip("/")
ROOT = pathlib.Path(os.environ.get(
    "SCRIPTORIA_WORKSPACES_ROOT", os.path.expanduser("~/agents/workspaces")))
MARKER = ".cardable"


def fetch_cards():
    url = f"{LIBRARY_URL}/catalog?source=scriptorium&limit=500"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.load(response)
    return payload.get("cards", payload if isinstance(payload, list) else [])


def sweep():
    cardable = [d for d in sorted(ROOT.iterdir())
                if d.is_dir() and (d / MARKER).exists()] if ROOT.is_dir() else []
    if not cardable:
        return []

    cards = {card["external_id"]: card for card in fetch_cards()}
    uncarded, drifted = [], []
    seen = set()

    for workspace in cardable:
        for path in sorted(workspace.rglob("*")):
            if not path.is_file() or path.name == MARKER:
                continue
            external_id = f"{workspace.name}/{path.relative_to(workspace)}"
            seen.add(external_id)
            card = cards.get(external_id)
            if card is None:
                uncarded.append(external_id)
            elif card.get("content_hash") and \
                    card["content_hash"] != hashlib.sha256(path.read_bytes()).hexdigest():
                drifted.append(external_id)

    cardable_names = {w.name for w in cardable}
    missing = [ext for ext in cards
               if ext.split("/", 1)[0] in cardable_names and ext not in seen]

    lines = []
    if uncarded:
        lines.append(f"Scriptorium: {len(uncarded)} uncarded draft(s): " + ", ".join(uncarded[:5])
                     + ("…" if len(uncarded) > 5 else ""))
    if drifted:
        lines.append(f"Scriptorium: {len(drifted)} draft(s) drifted since carding: "
                     + ", ".join(drifted[:5]) + ("…" if len(drifted) > 5 else ""))
    if missing:
        lines.append(f"Scriptorium: {len(missing)} card(s) whose draft is gone: "
                     + ", ".join(missing[:5]) + ("…" if len(missing) > 5 else ""))
    return lines


if __name__ == "__main__":
    try:
        for line in sweep():
            print(line)
    except Exception as e:
        print(f"Scriptorium sweep failed: {e}", file=sys.stderr)
        sys.exit(1)
