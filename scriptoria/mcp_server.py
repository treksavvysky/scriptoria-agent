"""Scriptoria's MCP server — the librarian's counter for local CLI agents.

Runs over stdio for Claude Code, Codex, and Antigravity. Library tools are
thin wrappers over the Cortex OS daemon (The Library); scriptorium tools
work the sandboxed drafting workspaces.

Run: `uv run scriptoria-mcp` (or `python -m scriptoria.mcp_server`).
"""

import json
from typing import Optional

from mcp.server.fastmcp import FastMCP

from scriptoria.library_client import LibraryClient, LibraryError
from scriptoria.scriptorium import Scriptorium, ScriptoriumError

mcp = FastMCP(
    "scriptoria",
    instructions=(
        "Scriptoria is the librarian of Cortex OS (The Library): The Stack is "
        "durable storage, the SMI (System Memory Index) is the card catalog, "
        "and Scriptoria works the counter. Use the library tools to search, "
        "shelve, and curate records; use the scriptorium tools to draft files "
        "in sandboxed workspaces. Record vocabulary — types: IDEA, DOCTRINE, "
        "PROJECT, TELEMETRY, SYSTEM, MISSION; statuses: captured, incubating, "
        "exploring, pre-planning, active, completed, archived, superseded, "
        "contradicted; domains: life, development; packets: idea, intent; "
        "conversion pressure: low, medium, high."
    ),
)


def _library() -> LibraryClient:
    return LibraryClient()


def _scriptorium() -> Scriptorium:
    return Scriptorium()


def _dumps(payload) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False)


# -- library tools -------------------------------------------------------

@mcp.tool()
def search_the_catalog(
    text: Optional[str] = None,
    namespace: Optional[str] = None,
    record_type: Optional[str] = None,
    status: Optional[str] = None,
    domain: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Search the SMI card catalog for records in The Stack. All filters are
    optional and combine; `text` matches record content. Returns record
    summaries with IDs usable in pull_record/related_records/curate_record."""
    try:
        records = _library().search_records(
            text=text, namespace=namespace, record_type=record_type,
            status=status, domain=domain, limit=limit,
        )
    except LibraryError as e:
        return f"Library error: {e}"
    if not records:
        return "The catalog has no records matching that scope."
    return _dumps(records)


@mcp.tool()
def pull_record(record_id: str) -> str:
    """Pull a single record from The Stack by its record_id, including its
    immutable core (raw_capture, origin, timestamp) and mutable shell
    (clarification, status, type, links, classification axes)."""
    try:
        record = _library().get_record(record_id)
    except LibraryError as e:
        return f"Library error: {e}"
    if record is None:
        return f"Record '{record_id}' is not held in The Stack."
    return _dumps(record)


@mcp.tool()
def related_records(record_id: str) -> str:
    """A record's link neighborhood: records it links to (outgoing, with
    relation) and records that link to it (incoming)."""
    try:
        neighborhood = _library().related(record_id)
    except LibraryError as e:
        return f"Library error: {e}"
    if neighborhood is None:
        return f"Record '{record_id}' is not held in The Stack."
    return _dumps(neighborhood)


@mcp.tool()
def shelf_digest(
    namespace: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> str:
    """A markdown digest of the shelves: records grouped by type with
    lifecycle status, capture, clarification state, and link counts."""
    try:
        return _library().digest(namespace=namespace, status=status, limit=limit)
    except LibraryError as e:
        return f"Library error: {e}"


@mcp.tool()
def log_to_the_stack(raw_capture: str, origin_context: str = "scriptoria.mcp") -> str:
    """Shelve a new capture into The Stack — a thought, decision, learning,
    or observation worth remembering across agents and sessions. Set
    origin_context to identify the capturing agent/session (e.g.
    'claude-code.myproject')."""
    try:
        result = _library().ingest(raw_capture, origin_context)
    except LibraryError as e:
        return f"Library error: {e}"
    return _dumps(result)


@mcp.tool()
def curate_record(
    record_id: str,
    status: Optional[str] = None,
    record_type: Optional[str] = None,
    domain: Optional[str] = None,
    packet: Optional[str] = None,
    conversion_pressure: Optional[str] = None,
    action_candidate: Optional[bool] = None,
) -> str:
    """Move a record through the catalog lifecycle and/or classify it.
    Statuses: captured, incubating, exploring, pre-planning, active,
    completed, archived, superseded, contradicted. Types: IDEA, DOCTRINE,
    PROJECT, TELEMETRY, SYSTEM, MISSION. Pass the string 'none' on
    domain/packet/conversion_pressure to clear the axis."""
    try:
        result = _library().curate(
            record_id, status=status, record_type=record_type, domain=domain,
            packet=packet, conversion_pressure=conversion_pressure,
            action_candidate=action_candidate,
        )
    except LibraryError as e:
        return f"Library error: {e}"
    return _dumps(result)


@mcp.tool()
def card_catalog(
    text: Optional[str] = None,
    source: Optional[str] = None,
    held: Optional[bool] = None,
    limit: int = 20,
) -> str:
    """Browse the card drawer for EXTERNAL artifacts the SMI points at
    (e.g. Mnemos objects). held=false shows cards for artifacts The Stack
    does not yet hold; held=true shows accessioned ones."""
    try:
        result = _library().catalog(text=text, source=source, held=held, limit=limit)
    except LibraryError as e:
        return f"Library error: {e}"
    return _dumps(result)


@mcp.tool()
def check_out(record_id: str) -> str:
    """Retrieve a held record in a check-out envelope. Non-destructive:
    custody stays with The Stack. Accessioned records include the original
    external object re-exported from the fossil."""
    try:
        envelope = _library().checkout(record_id)
    except LibraryError as e:
        return f"Library error: {e}"
    if envelope is None:
        return f"Record '{record_id}' is not held in The Stack."
    return _dumps(envelope)


@mcp.tool()
def library_status() -> str:
    """The Library daemon's health: brain provider mode and auth posture."""
    try:
        return _dumps(_library().status())
    except LibraryError as e:
        return f"Library error: {e}"


# -- scriptorium tools ----------------------------------------------------

@mcp.tool()
def list_workspaces() -> str:
    """List the scriptorium's drafting workspaces and their file counts."""
    try:
        return _dumps(_scriptorium().list_workspaces())
    except ScriptoriumError as e:
        return f"Scriptorium error: {e}"


@mcp.tool()
def create_workspace(name: str) -> str:
    """Create a drafting workspace (lowercase slug name)."""
    try:
        return _dumps(_scriptorium().create_workspace(name))
    except ScriptoriumError as e:
        return f"Scriptorium error: {e}"


@mcp.tool()
def list_files(workspace: str, subdir: str = "") -> str:
    """List files in a scriptorium workspace (optionally under a subdir)."""
    try:
        return _dumps(_scriptorium().list_files(workspace, subdir))
    except ScriptoriumError as e:
        return f"Scriptorium error: {e}"


@mcp.tool()
def read_workspace_file(workspace: str, path: str) -> str:
    """Read a text file from a scriptorium workspace."""
    try:
        return _scriptorium().read_file(workspace, path)
    except ScriptoriumError as e:
        return f"Scriptorium error: {e}"


@mcp.tool()
def write_workspace_file(workspace: str, path: str, content: str, append: bool = False) -> str:
    """Write (or append to) a text file in a scriptorium workspace. Parent
    directories are created automatically; writes are atomic."""
    try:
        return _dumps(_scriptorium().write_file(workspace, path, content, append=append))
    except ScriptoriumError as e:
        return f"Scriptorium error: {e}"


@mcp.tool()
def move_workspace_file(workspace: str, source: str, destination: str) -> str:
    """Move or rename a file within a scriptorium workspace."""
    try:
        return _dumps(_scriptorium().move_file(workspace, source, destination))
    except ScriptoriumError as e:
        return f"Scriptorium error: {e}"


@mcp.tool()
def delete_workspace_file(workspace: str, path: str) -> str:
    """Delete a single file from a scriptorium workspace (never directories)."""
    try:
        return _dumps(_scriptorium().delete_file(workspace, path))
    except ScriptoriumError as e:
        return f"Scriptorium error: {e}"


# -- resources ------------------------------------------------------------

@mcp.resource("library://digest")
def digest_resource() -> str:
    """Live markdown digest of the Library's shelves."""
    try:
        return _library().digest()
    except LibraryError as e:
        return f"Library error: {e}"


@mcp.resource("library://record/{record_id}")
def record_resource(record_id: str) -> str:
    """A single record from The Stack."""
    try:
        record = _library().get_record(record_id)
    except LibraryError as e:
        return f"Library error: {e}"
    return _dumps(record) if record else f"Record '{record_id}' not held."


# -- prompts ---------------------------------------------------------------

@mcp.prompt()
def shelve_this_session() -> str:
    """End-of-session ritual: distill what this session learned or decided
    and shelve it into The Stack."""
    return (
        "Review this session and distill what is worth remembering beyond it: "
        "decisions made (and why), non-obvious things learned, and open threads. "
        "For each, call log_to_the_stack with a self-contained raw_capture "
        "(readable without this session's context) and an origin_context naming "
        "this agent and project. Then report what you shelved, with record IDs."
    )


@mcp.prompt()
def curation_triage() -> str:
    """Walk the unclassified shelves with the operator and curate records."""
    return (
        "Search the catalog for records with status 'captured', oldest first. "
        "Pull each record and read its clarification and observations (genuinely "
        "brain-enriched since 2026-07-12; treat older '[brain:simulation]' shells "
        "as unenriched). For each record, propose a type, status, and "
        "classification axes (domain, packet, conversion_pressure, "
        "action_candidate), explaining your reasoning in one line. Ask the "
        "operator to confirm or adjust in batches, then apply the confirmed "
        "curations with curate_record. Prefer null over forced classification -- "
        "unclassified is a legitimate state."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
