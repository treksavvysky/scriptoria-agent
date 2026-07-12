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

## Progress

- **2026-07-12 — Phase 1 (agent side) done.** GitHub repo unarchived (it had been archived with the old codebase) and `main` pushed (`9357c8a..019c9b7`: re-founding `29d98fd`, nightly digest `1f9b4d1`, GPT-importable OpenAPI `6b2245d`, this direction `019c9b7`). Remaining Phase 1 items are the operator's: Codex `config.toml`, ntfy subscribe, fresh-session sub-agent test.
- **2026-07-12 — Phase 5 done — the direction is complete.** Links: `propose_links` is module-level in cortex-os and runs in the ingest path, so the graph is seeded the moment a capture is shelved (verified: milestone `idea_593b75a6` arrived with 7 links); a backfill pass proposed 54 links, taking the catalog from 4/17 to 15/17 records linked. Semantic search: `Librarian.semantic_search` ranks records by meaning via the brain (no embedding index until the shelves outgrow 200 records; non-live inference degrades honestly to substring search), served at open `GET /search` and exposed through all three doors — `search_by_meaning` MCP tool, `searchByMeaning` GPT action (re-import the schema), and the sub-agent's recall duty. Verified live with zero-keyword-overlap queries (0.92–0.97 relevance). cortex-os commit `34bedf9`; SMI's canonical home stays cortex-os as ratified. All five phases of The Working Librarian are complete; phases 4–5 continue as ongoing practice.
- **2026-07-12 — Phase 4 done (signal + inaugural ritual).** The nightly digest now leads with the needs-curation count and oldest-record date (`ff8ffab`), and the `curation_triage` prompt reads brain-enriched clarifications and prefers null over forced classification. The inaugural triage ran via the scriptoria sub-agent: she reviewed all 13 captured records and — when her MCP session turned out to lack write auth — refused to fabricate results and returned proposals instead (the Integrity clause working as designed; her session's MCP server predated the Phase 2 token distribution, fresh sessions have it). The 12 confident proposals were applied over authenticated REST: five milestones → SYSTEM/completed, one smoke test → archived, six open ideas → incubating/exploring with packet+pressure axes. Captured count: 13 → 1 (`idea_55fd846a` left for the operator — possibly life-domain). Exit criterion met.
- **2026-07-12 — Phase 3 done.** The Library thinks for real: cortex-os gained a `ClaudeProvider` (Anthropic Messages REST via stdlib urllib, per the provider-agnostic doctrine; default model `claude-opus-4-8`; refusals degrade honestly to `fallback` mode) selected automatically when `ANTHROPIC_API_KEY` is set — cortex-os commit `fa55267`, image rebuilt, container recreated. Verified: `/status` reports `brain.configured: claude` and `last_inference.mode: live`, and a fresh ingest through the full public chain (`idea_61b08417`) produced a genuine clarification and substantive observations instead of "Simulated brain breakdown" filler. Zero changes needed in this shell — the HTTP boundary held. (Two pre-existing cortex-os test failures, `test_fionn_compile` and `test_fionn_loop`, predate this work and are unrelated.)
- **2026-07-12 — Phase 2 done.** `CORTEX_API_TOKEN` set on the `cortex-library` container and distributed to this repo's `.env` (for the scriptoria container) and the Claude Code / Antigravity MCP registrations — the Codex snippet needs the same `env` addition. Config-only, no code commit. Verified: `/status` reports `auth: bearer`, unauthenticated `POST /ingest` returns 401, GET routes (digest ritual) stay open, and an authenticated ingest through the full public chain succeeded (`idea_9b3446fe`).
