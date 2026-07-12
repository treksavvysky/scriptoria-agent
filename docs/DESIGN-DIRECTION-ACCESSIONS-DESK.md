# Design Direction: The Accessions Desk

**Status:** adopted by operator, 2026-07-12
**Scope:** making scriptorium drafts visible to the card catalog and giving them a governed path into The Stack — check-in — and back out for revision — check-out.
**Predecessor:** `docs/DESIGN-DIRECTION.md` ("The Working Librarian", completed 2026-07-12).
**Proposal:** keryx artifact `scriptoria-draft-accession-design` (operator-approved).

## Where this starts

The Working Librarian left one measured gap: the scriptorium is invisible to the SMI. A draft can sit on a desk indefinitely while `searchByMeaning`, the digest, and the link graph all report it doesn't exist. The workaround is manual: on 2026-07-12 the operator promoted the first GPT-authored draft (`fable_5/claude-fable-5-cognitive-operator.md`) by hand — pointer record, review, content ingest, supersede-link, two curations. It worked cleanly and took an operator plus a coordinating session about a dozen steps. This direction turns that ritual into one call.

The reference trace of that manual run: pointer `idea_971c26d3` (now superseded) → content record `idea_658d5c16` (active), linked `supersedes → idea_971c26d3`.

## Doctrine carried forward

- **HTTP-only boundary.** Cards live in the SMI (cortex-os); the shell pushes metadata and, at check-in, content — over HTTP only. The Library never touches the shell's filesystem.
- **The shell holds no records.** Drafts remain working material in the scriptorium; durable knowledge lives in The Stack. Cards make drafts *visible*, not *held*.
- **Raw capture stays immutable.** Check-in creates a fossil; revision creates a new fossil linked `supersedes`. History is never rewritten.
- **Cards are cheap until check-in.** No brain enrichment on carding — enrichment is what accession buys. Keeps carding fast and free.
- **Review is human.** Check-in is triggered by (or on the instruction of) the operator; agents propose, the operator adjudicates — the same posture keryx takes ("agents don't approve").

## Lifecycle

```
draft written in scriptorium
        │  card_draft (shell registers metadata over HTTP)
        ▼
CARDED  held=false · source=scriptorium · workspace/path · size · content hash
        │  operator reviews for accuracy / truthfulness
        ▼
CHECK-IN  check_in_draft: content POSTed → immutable record in The Stack
        │  card → held=true · record enriched, linked, searchable
        ▼
CHECK-OUT  fossil re-exported into a workspace as an editable working copy
        │  custody stays with The Stack
        ▼
RE-CHECK-IN  new fossil, link: supersedes → prior record
```

## Phases

### Phase 1 — Cards for scriptorium drafts (cortex-os)

Extend the card catalog (built for Mnemos objects) with a `scriptorium` card source carrying workspace/path, byte size, and a content hash. Bearer-gated mutation routes to register and update cards; cards visible through the existing `card_catalog` surface with `held=false`. Exit criterion: a card registered over HTTP appears in `card_catalog` filtered by `source=scriptorium, held=false`.

### Phase 2 — The desk opens (shell, all three doors)

`card_draft` and `check_in_draft` in `library_client.py`, exposed as MCP tools, GPT actions (schema re-import), and sub-agent duties. `check_in_draft` reads the draft, ingests its full text (provenance preamble included) as a new record, flips the card to `held=true`, and records the `supersedes`/`references` linkage to any prior pointer or superseded fossil. Exit criterion: the dozen-step manual ritual of 2026-07-12 is a single call from any door.

### Phase 3 — Check-out for revision (shell-side compose)

Check-out places a working copy of a held record into a named workspace (compose of the existing `check_out` envelope + `write_workspace_file`); a later re-check-in produces a new record linked `supersedes` to the old one. Exit criterion: a full revision round-trip with history intact.

### Phase 4 — The sweep (ritual)

The nightly digest gains scriptorium drift signals: files in cardable workspaces with no card, and carded drafts whose hash no longer matches. Exit criterion: drift is visible daily without anyone asking.

## Operator rulings

Defaults adopted from the proposal; each is confirmed or overridden at the phase that implements it.

1. **Staleness** — flag "draft drifted since carding" in the digest; never silently re-card. *(Phase 4)*
2. **Scope** — carding is per-workspace opt-in; scratch workspaces (e.g. `gpt-drafts`) stay uncarded by default. *(Phase 1)*
3. **Deletion** — a carded draft deleted before check-in archives its card at the next sweep. *(Phase 4)*
4. **Enrichment** — cards stay cheap metadata; enrichment happens at check-in only. *(Phase 1, doctrine above)*
5. **Review gate** — check-in requires operator instruction; there is no auto-promote. *(Phase 2)*

## Sequencing

Phase 1 is cortex-os work and the only schema change; per the boundary doctrine the shell needs nothing until Phase 2. Phases 2–3 are thin shell wrappers over existing machinery. Phase 4 extends an existing script. The `fable_5` essay is the pilot fixture throughout: Phase 1 cards it retroactively, Phase 3 checks it out, and its manual promotion trace is the behavior every phase must reproduce mechanically.

## Progress

- **2026-07-12 — Direction adopted.** Keryx proposal approved by the operator; this document written; doctrine record shelved in The Library. Predecessor direction ("The Working Librarian") closed complete.
