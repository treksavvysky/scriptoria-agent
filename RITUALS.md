# Rituals — scriptoria-agent

Every recurring or on-demand job this agent runs, in one place, per the
convention in [`~/agents/RITUALS.md`](../RITUALS.md). Facts below come from the
live crontab, the scripts, and `scriptoria/mcp_server.py` — not from memory.

## 1. Nightly Library digest

| Field | Value |
| --- | --- |
| **Schedule** | `0 21 * * *` — every day at 21:00 (host local time) |
| **Trigger** | cron (operator crontab, `crontab -l`) |
| **Channel** | ntfy topic `library` on the self-hosted server — subscribe at `https://ntfy.codejourney.com/library` (auth: `NTFY_TOKEN` bearer from this repo's `.env`; overridable via `NTFY_URL`) |
| **Driver** | `scripts/nightly_digest.sh`; stdout/stderr appended to `digest-cron.log` in this repo |
| **Silence / adjust** | `crontab -e` — remove or retime the `nightly_digest.sh` line. Env overrides: `LIBRARY_URL`, `NTFY_URL`, `NTFY_TOKEN`. |

**Message contents** (title *"The Library — nightly digest"*, tags `books`):

1. **Needs-curation lead line** — count of records still at status `captured`
   with the oldest capture date, plus a nudge to run a curation triage; or
   *"Shelves fully curated - nothing waiting at captured."* when clean.
   (Queries `GET $LIBRARY_URL/records?status=captured&limit=200`.)
2. **The Library digest** — the markdown from
   `GET $LIBRARY_URL/digest?limit=50` (`LIBRARY_URL` defaults to
   `http://127.0.0.1:8021`, the cortex-library container's host port):
   record count, then records grouped by type (`## DOCTRINE`, `## IDEA`, …)
   with id, status, and summary per record.
3. Bodies over ~3800 chars are truncated with a pointer to
   `$LIBRARY_URL/digest` (ntfy caps bodies at ~4 KiB).

**Failure mode:** if The Library is unreachable, the script instead posts
*"The Library — digest failed"* (tags `warning,books`) to the same topic and
exits 1 — so a silent night means cron itself didn't fire; check
`digest-cron.log`.

## 2. Curation triage

| Field | Value |
| --- | --- |
| **Schedule** | on demand |
| **Trigger** | manual — MCP prompt `curation_triage` (`scriptoria/mcp_server.py`) |
| **Channel** | interactive session (no ntfy) |
| **Driver** | prompt walks the `captured` shelves oldest-first, proposes type/status/classification axes per record, asks the operator to confirm in batches, then applies with `curate_record` |
| **Silence / adjust** | nothing to silence; edit the prompt text in `mcp_server.py` |

The nightly digest's needs-curation lead line is the standing reminder to run
this ritual.

## 3. Shelve this session

| Field | Value |
| --- | --- |
| **Schedule** | on demand (end of session) |
| **Trigger** | manual — MCP prompt `shelve_this_session` (`scriptoria/mcp_server.py`) |
| **Channel** | interactive session (no ntfy) |
| **Driver** | prompt distills the session's decisions, learnings, and open threads into self-contained `log_to_the_stack` captures, then reports the record IDs |
| **Silence / adjust** | nothing to silence; edit the prompt text in `mcp_server.py` |

## 4. Scriptorium drift sweep — **planned, not active**

Phase 4 of the adopted design direction
[`docs/DESIGN-DIRECTION-ACCESSIONS-DESK.md`](docs/DESIGN-DIRECTION-ACCESSIONS-DESK.md)
("The sweep") will extend the nightly digest with scriptorium drift signals:
files in cardable workspaces with no card, carded drafts whose content hash no
longer matches, and archiving the cards of drafts deleted before check-in.
Exit criterion: drift visible daily without anyone asking. No code exists yet;
when implemented it will ride ritual #1's schedule and channel.
