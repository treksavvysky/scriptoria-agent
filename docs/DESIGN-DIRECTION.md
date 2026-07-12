# Design Direction: The Working Librarian

**Status:** adopted by operator, 2026-07-12
**Scope:** the path from a deployed agent shell to a librarian whose enrichment is real, whose catalog is curated, and whose shelves are cross-referenced.
**Predecessor:** cortex-os `docs/DESIGN-DIRECTION.md` (2026-07-04), whose Phase 4 — "Scriptoria becomes a librarian" — this document picks up and carries forward.

## Where this starts

As of 2026-07-12 the shell is live and verified end-to-end:

- Three doors open on one HTTP boundary: stdio MCP server (Claude Code, Antigravity, Codex pending), bearer-gated REST at `https://scriptoria.codejourney.com` importable directly as custom GPT actions, and the `scriptoria` Claude Code sub-agent.
- The scriptorium (sandboxed drafting workspaces at `~/agents/workspaces`, successor to ai-file-manager) works from all doors; the custom GPT has drafted and retrieved real files.
- The nightly digest ritual runs at 21:00 (`scripts/nightly_digest.sh` → ntfy topic `library`).

And three measured facts define the gap between *deployed* and *working*:

1. **The Library's brain is simulated.** `/status` reports `brain.configured: simulation`; every record's `clarification` is mock filler ("Simulated brain breakdown…").
2. **The Library's API is open.** `/status` reports `auth: open` — anything on the `cortex` docker network can write to The Stack.
3. **The catalog is uncurated and sparsely linked.** 10 of 12 records sit at `captured`; only 4 carry links.

## Doctrine carried forward

- **HTTP-only boundary.** This shell never imports cortex-os code. Phases below that change the Library (notably Phase 3) are cortex-os work; the shell should require zero changes when they land. That insulation is the point.
- **The shell holds no records.** Scriptoria is custodian, not tenant: workspaces belong to other agents (one workspace per agent by naming convention — `gpt-drafts`, `fionn`, …), and all durable knowledge lives in The Stack.
- **Raw capture stays immutable.** Enrichment, curation, and linking only ever touch the mutable shell.

## Phases

### Phase 1 — Finish the rollout (operator + shell, small)

- Push the repo to `github.com/treksavvysky/scriptoria-agent` (commits exist only on the host).
- Operator checklist (published to keryx as `scriptoria-launch-operator-checklist`): add the MCP entry to root-owned `~/.codex/config.toml`; subscribe to the `library` ntfy topic; invoke the sub-agent in a fresh session to confirm her MCP tools connect.

### Phase 2 — Close the open door (config only, small)

Set `CORTEX_API_TOKEN` on the `cortex-library` container and mirror it in this repo's `.env`. The daemon already enforces the bearer on mutations when the variable is set, and `library_client.py` already sends it — this is two env vars and two restarts, no code. Exit criterion: `/status` reports `auth: bearer` and an unauthenticated `POST /ingest` on the cortex network gets 401.

### Phase 3 — A real brain for ingest (cortex-os work, the big one)

Wire cortex-os's `AgentBrain` to a real inference provider (Claude API) so enrichment stops being canned filler. A genuine brain gives every capture:

- a real `clarification` of intent,
- classification suggestions (type / domain / packet / conversion pressure) for the curation queue,
- candidate `links` to existing records (the candidate-link machinery already exists in `core_ace.py`).

This is the single highest-leverage change on the board, and per the boundary doctrine it happens entirely in cortex-os — this shell, all three doors, and the custom GPT continue working unchanged. Exit criterion: `/status` reports a non-simulation brain mode and a fresh ingest produces a clarification that is not templated.

### Phase 4 — Curation as ritual, not backlog

Records must not age at `captured`. Two steps, cheap one first:

1. **Signal:** the nightly digest line gains a "needs curation" count (records at `captured`, oldest-first) so drift is visible daily.
2. **Ritual:** a recurring triage session — operator plus the sub-agent, driven by the existing `curation_triage` MCP prompt — that moves records through the lifecycle (captured → incubating → exploring → pre-planning → active → completed / archived / superseded / contradicted) and sets classification axes with justification.

Exit criterion: the `captured` count trends toward zero between rituals instead of monotonically up.

### Phase 5 — The connective tissue

A library's value is its cross-references, not its shelves.

- **Links first:** once Phase 3 lands, ingest-time link proposals populate the graph; triage (Phase 4) accepts or rejects them. Target: a majority of records carry at least one link.
- **Semantic search:** today's `text` filter is substring matching. Add embedding-based search over `raw_capture` so recall works by meaning ("what do we know about container auth?") rather than by remembered phrasing. This is an index-contract (SMI) change in cortex-os; the shell just passes a query string through, as it already does.
- **SMI's canonical home:** already ratified in the predecessor doc — cortex-os. The HTTP boundary means this shell never had to care, and still doesn't.

## Sequencing

Phases 1–2 are an hour of operator + config work and should happen immediately. Phase 3 is the next real work session and multiplies the value of everything after it: triage (4) gets machine-suggested classifications instead of blank cards, and the graph (5) gets seeded automatically instead of by hand. 4 and 5 then run as ongoing practice, not projects.
