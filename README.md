# Scriptoria — the Librarian of Cortex OS

> *"Every idea deserves to be written well. Scriptoria ensures it is."*

Scriptoria is the librarian of **The Library** (the [cortex-os](https://github.com/treksavvysky/cortex-os) service): **The Stack** is durable storage, the **SMI** (System Memory Index) is the card catalog, and Scriptoria works the counter — finding, shelving, curating, and presenting what's already there.

This repo is Scriptoria's **agent shell**. It holds no records itself and never imports cortex-os code: the Library is reached only over HTTP (`LIBRARY_URL`), so the Library's canonical home can move without touching this repo. The shell opens three doors to the same librarian:

| Door | For | Entry point |
| --- | --- | --- |
| **MCP server** (stdio) | Claude Code, Codex, Antigravity CLI | `uv run scriptoria-mcp` |
| **REST API** (bearer-gated) | ChatGPT custom GPT actions | `uv run uvicorn scriptoria.api:app` |
| **Claude Code sub-agent** | "ask the librarian" in any session | `~/.claude/agents/scriptoria.md` |

## The scriptorium

Alongside the library tools, Scriptoria keeps a **scriptorium** — sandboxed drafting workspaces (successor to `ai-file-manager`) where agents draft and save files without copy-paste and the operator gets visibility into each agent's working files. Every operation is jailed inside its workspace by `scriptoria/file_manager.py` (rejects absolute paths and `..`, resolves symlinks, verifies containment).

## Layout

```
scriptoria/
├── config.py          # env: LIBRARY_URL, CORTEX_API_TOKEN, SCRIPTORIA_API_TOKEN, SCRIPTORIA_WORKSPACES_ROOT
├── library_client.py  # the ONE module that talks to the Library daemon
├── file_manager.py    # sandboxed file engine (salvaged from the IntelliSwarm era, tested)
├── scriptorium.py     # named drafting workspaces over the file engine
├── mcp_server.py      # FastMCP stdio server: tools + resources + prompts
└── api.py             # FastAPI REST for GPT actions (OpenAPI at /openapi.json)
```

## Configuration

| Variable | Meaning | Default |
| --- | --- | --- |
| `LIBRARY_URL` | Cortex OS daemon base URL | `http://localhost:8000` |
| `CORTEX_API_TOKEN` | Bearer the Library expects on mutations | *(empty)* |
| `SCRIPTORIA_API_TOKEN` | Bearer required by Scriptoria's own REST API | *(required for REST)* |
| `SCRIPTORIA_WORKSPACES_ROOT` | Scriptorium root directory | `~/agents/workspaces` |

## Develop

```bash
uv sync
uv run pytest            # sandbox + API auth + salvaged engine suites
uv run scriptoria-mcp    # stdio MCP server (used by CLI agent configs)
uv run uvicorn scriptoria.api:app --port 8020
```

## Deploy

`docker compose up` (via `orca`) serves the REST API; the public door is `https://scriptoria.codejourney.com` through the codejourney proxy. The compose file joins two external networks: `codejourney-proxy` (the public proxy) and `cortex` (where the `cortex-library` daemon container lives, its host port at `127.0.0.1:8021` for the stdio MCP servers).

## Custom GPT setup

In the GPT editor, add an Action and import the schema from
`https://scriptoria.codejourney.com/openapi.json`. Authentication: **API Key**,
auth type **Bearer**, key = the `SCRIPTORIA_API_TOKEN` value from this repo's
`.env`. The GPT then has the full librarian surface: search/pull/curate/log
records in The Library plus draft files in the scriptorium workspaces.
