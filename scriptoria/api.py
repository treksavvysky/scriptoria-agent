"""Scriptoria's REST API — the door for custom GPT actions.

Every route is bearer-gated by SCRIPTORIA_API_TOKEN except /health. The
OpenAPI spec at /openapi.json imports directly into a ChatGPT custom GPT
as actions; operation IDs are the librarian's tool names.

Run locally: uv run uvicorn scriptoria.api:app --port 8020
"""

import html
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from scriptoria import accessions, config
from scriptoria.library_client import LibraryClient, LibraryError
from scriptoria.scriptorium import Scriptorium, ScriptoriumError

app = FastAPI(
    title="Scriptoria",
    version="1.0.0",
    description=(
        "The librarian of Cortex OS (The Library). Library routes search, "
        "shelve, and curate records in The Stack via the SMI card catalog; "
        "scriptorium routes draft files in sandboxed workspaces."
    ),
    servers=[{"url": "https://scriptoria.codejourney.com"}],
)

_bearer = HTTPBearer(auto_error=False)


def require_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> None:
    expected = config.scriptoria_api_token()
    if not expected:
        raise HTTPException(503, "SCRIPTORIA_API_TOKEN is not configured on the server.")
    if credentials is None or credentials.credentials != expected:
        raise HTTPException(401, "Provide 'Authorization: Bearer <SCRIPTORIA_API_TOKEN>'.")


def _library() -> LibraryClient:
    return LibraryClient()


def _scriptorium() -> Scriptorium:
    return Scriptorium()


@app.exception_handler(LibraryError)
async def library_error_handler(request, exc: LibraryError):
    return JSONResponse(status_code=502, content={"error": f"The Library: {exc}"})


@app.exception_handler(ScriptoriumError)
async def scriptorium_error_handler(request, exc: ScriptoriumError):
    return JSONResponse(status_code=400, content={"error": str(exc)})


# -- response models ---------------------------------------------------------
# The GPT actions importer rejects bare `object` response schemas, so every
# route declares an explicit model. Library models allow extra fields: the
# daemon's record shape can grow without breaking this shell.

class HealthStatus(BaseModel):
    status: str
    agent: str


class Record(BaseModel):
    """A catalog record (full or summary form) held in The Stack."""
    model_config = ConfigDict(extra="allow")

    record_id: Optional[str] = None
    timestamp: Optional[str] = None
    origin_context: Optional[str] = None
    raw_capture: Optional[str] = None
    type: Optional[str] = Field(None, description="IDEA, DOCTRINE, PROJECT, TELEMETRY, SYSTEM, MISSION")
    status: Optional[str] = None
    domain: Optional[str] = None
    packet: Optional[str] = None
    conversion_pressure: Optional[str] = None
    action_candidate: Optional[bool] = None


class SemanticMatches(BaseModel):
    model_config = ConfigDict(extra="allow")

    query: str
    matches: List[Record] = Field(
        default=[], description="Relevant records, best first; each carries 'relevance' (0-1) and 'why'."
    )


class Neighbor(BaseModel):
    """One edge of a record's link neighborhood."""
    model_config = ConfigDict(extra="allow")

    relation: Optional[str] = Field(None, description="Relation on an outgoing link.")
    relations: Optional[List[str]] = Field(None, description="Relations on an incoming link.")
    record: Optional[Record] = None


class Neighborhood(BaseModel):
    model_config = ConfigDict(extra="allow")

    record: Record
    outgoing: List[Neighbor] = []
    incoming: List[Neighbor] = []


class Digest(BaseModel):
    digest: str = Field(description="Markdown digest of the shelves, grouped by record type.")


class IngestReceipt(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = Field(None, description="'ingesting' — shelving is asynchronous.")
    record_id: Optional[str] = Field(None, description="ID the new record will be shelved under.")
    mission_id: Optional[str] = None


class CurateReceipt(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    record: Optional[Record] = None


class CheckoutEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    record: Record
    custody: Optional[str] = None
    checked_out_at: Optional[str] = None


class Workspace(BaseModel):
    name: str
    files: int


class WorkspaceCreated(BaseModel):
    name: str
    created: bool = Field(description="False if the workspace already existed.")


class FileEntry(BaseModel):
    path: str
    kind: str = Field(description="'file' or 'dir'")
    size: Optional[int] = None


class FileContent(BaseModel):
    workspace: str
    path: str
    content: str


class WriteReceipt(BaseModel):
    workspace: str
    path: str
    size: int
    appended: bool


class MoveReceipt(BaseModel):
    workspace: str
    moved: str
    to: str


class DeleteReceipt(BaseModel):
    workspace: str
    deleted: str


@app.get("/health", operation_id="health")
def health() -> HealthStatus:
    return HealthStatus(status="active", agent="scriptoria")


# -- library: the reading room ---------------------------------------------

@app.get("/library/records", operation_id="searchTheCatalog", dependencies=[Depends(require_token)])
def search_the_catalog(
    text: Optional[str] = Query(None, description="Full-text match on record content"),
    namespace: Optional[str] = None,
    type: Optional[str] = Query(None, description="IDEA, DOCTRINE, PROJECT, TELEMETRY, SYSTEM, MISSION"),
    status: Optional[str] = Query(None, description="captured, incubating, exploring, pre-planning, active, completed, archived, superseded, contradicted"),
    domain: Optional[str] = Query(None, description="life or development"),
    limit: int = 20,
) -> List[Record]:
    """Search the SMI card catalog for records held in The Stack."""
    return _library().search_records(
        text=text, namespace=namespace, record_type=type,
        status=status, domain=domain, limit=limit,
    )


@app.get("/library/search", operation_id="searchByMeaning", dependencies=[Depends(require_token)])
def search_by_meaning(
    query: str = Query(description="Natural-language query; matches records by meaning, not keywords."),
    limit: int = 10,
) -> SemanticMatches:
    """Semantic search: the Library's brain ranks records against the query.
    Slower than searchTheCatalog; use when exact phrasing is unknown."""
    return _library().semantic_search(query, limit=limit)


@app.get("/library/records/{record_id}", operation_id="pullRecord", dependencies=[Depends(require_token)])
def pull_record(record_id: str) -> Record:
    """Pull a single record: immutable core plus mutable shell."""
    record = _library().get_record(record_id)
    if record is None:
        raise HTTPException(404, f"Record '{record_id}' is not held in The Stack.")
    return record


@app.get("/library/records/{record_id}/related", operation_id="relatedRecords", dependencies=[Depends(require_token)])
def related_records(record_id: str) -> Neighborhood:
    """The record's link neighborhood (outgoing and incoming relations)."""
    neighborhood = _library().related(record_id)
    if neighborhood is None:
        raise HTTPException(404, f"Record '{record_id}' is not held in The Stack.")
    return neighborhood


@app.get("/library/digest", operation_id="shelfDigest", dependencies=[Depends(require_token)])
def shelf_digest(
    namespace: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> Digest:
    """Markdown digest of the shelves, grouped by record type."""
    return {"digest": _library().digest(namespace=namespace, status=status, limit=limit)}


class LogRequest(BaseModel):
    raw_capture: str = Field(description="The thought, decision, or learning to shelve — self-contained.")
    origin_context: str = Field("custom-gpt", description="Who/where this capture came from.")


@app.post("/library/log", operation_id="logToTheStack", dependencies=[Depends(require_token)])
def log_to_the_stack(body: LogRequest) -> IngestReceipt:
    """Shelve a new capture into The Stack (asynchronous; returns the record_id)."""
    return _library().ingest(body.raw_capture, body.origin_context)


class CurateRequest(BaseModel):
    status: Optional[str] = Field(None, description="Lifecycle status, e.g. incubating, active, archived.")
    type: Optional[str] = Field(None, description="IDEA, DOCTRINE, PROJECT, TELEMETRY, SYSTEM, MISSION.")
    domain: Optional[str] = Field(None, description="life, development, or 'none' to clear.")
    packet: Optional[str] = Field(None, description="idea, intent, or 'none' to clear.")
    conversion_pressure: Optional[str] = Field(None, description="low, medium, high, or 'none' to clear.")
    action_candidate: Optional[bool] = None


@app.post("/library/records/{record_id}/curate", operation_id="curateRecord", dependencies=[Depends(require_token)])
def curate_record(record_id: str, body: CurateRequest) -> CurateReceipt:
    """Move a record through the catalog lifecycle and/or classify it."""
    return _library().curate(
        record_id, status=body.status, record_type=body.type, domain=body.domain,
        packet=body.packet, conversion_pressure=body.conversion_pressure,
        action_candidate=body.action_candidate,
    )


@app.get("/library/records/{record_id}/checkout", operation_id="checkOut", dependencies=[Depends(require_token)])
def check_out(record_id: str) -> CheckoutEnvelope:
    """Retrieve a held record in a check-out envelope (non-destructive)."""
    envelope = _library().checkout(record_id)
    if envelope is None:
        raise HTTPException(404, f"Record '{record_id}' is not held in The Stack.")
    return envelope


# -- inbox: the returns cart -------------------------------------------------
# Operator-facing HTML view of records awaiting curation (status "captured").
# Browsers can't send Authorization headers on a plain page load, so the
# bearer token travels as ?token=. Excluded from the OpenAPI spec so it never
# appears in the GPT actions import.

_INBOX_STYLE = """
  body { font-family: Georgia, 'Times New Roman', serif; background: #f7f4ee;
         color: #2b2620; margin: 0; padding: 2rem 1rem; }
  main { max-width: 46rem; margin: 0 auto; }
  header { border-bottom: 3px double #b8a98c; padding-bottom: 1rem; margin-bottom: 1.5rem; }
  h1 { font-size: 1.5rem; margin: 0 0 0.4rem; }
  header p { margin: 0; color: #6b6155; font-size: 0.95rem; }
  article { background: #fffdf8; border: 1px solid #ddd2bd; border-radius: 4px;
            padding: 1rem 1.25rem; margin-bottom: 1rem; }
  .meta { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: baseline;
          font-size: 0.85rem; color: #6b6155; margin-bottom: 0.6rem;
          font-family: ui-monospace, 'SF Mono', Menlo, Consolas, monospace; }
  .meta .id { font-weight: bold; color: #2b2620; }
  .capture { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0;
             font-family: inherit; font-size: 1rem; line-height: 1.5; }
  .empty { text-align: center; padding: 3rem 1rem; color: #6b6155; font-style: italic; }
"""


def _age_in_days(timestamp: Optional[str]) -> Optional[int]:
    """Whole days since the record was captured; None if unparseable."""
    if not timestamp:
        return None
    try:
        captured = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - captured).days)


def _inbox_card(record: Dict[str, Any]) -> str:
    age = _age_in_days(record.get("timestamp"))
    age_label = "age unknown" if age is None else f"{age} day{'' if age == 1 else 's'} old"
    origin = record.get("origin_context") or "unknown origin"
    return (
        "<article>"
        '<div class="meta">'
        f'<span class="id">{html.escape(str(record.get("record_id") or "unidentified"))}</span>'
        f"<span>{html.escape(age_label)}</span>"
        f"<span>{html.escape(str(origin))}</span>"
        "</div>"
        f'<pre class="capture">{html.escape(str(record.get("raw_capture") or ""))}</pre>'
        "</article>"
    )


@app.get("/inbox", include_in_schema=False)
def inbox(token: Optional[str] = Query(None)) -> HTMLResponse:
    """Read-only inbox of captured records, oldest first."""
    expected = config.scriptoria_api_token()
    if not expected:
        raise HTTPException(503, "SCRIPTORIA_API_TOKEN is not configured on the server.")
    if token != expected:
        raise HTTPException(401, "Provide '?token=<SCRIPTORIA_API_TOKEN>'.")

    records = _library().search_records(status="captured", limit=500)
    records.sort(key=lambda r: r.get("timestamp") or "")

    if records:
        count = len(records)
        body = f"<p>{count} record{'' if count == 1 else 's'} on the returns cart.</p>"
        body += "".join(_inbox_card(record) for record in records)
    else:
        body = '<p class="empty">Shelves fully curated — nothing awaits the librarian.</p>'

    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>The Library — Inbox</title><style>{_INBOX_STYLE}</style></head>"
        "<body><main><header><h1>The Library — Inbox</h1>"
        "<p>Records captured but not yet curated. This page is read-only: "
        "curation happens via the scriptoria sub-agent or its MCP tools.</p>"
        f"</header>{body}</main></body></html>"
    )
    return HTMLResponse(page)


# -- scriptorium: the drafting room -----------------------------------------

@app.get("/workspaces", operation_id="listWorkspaces", dependencies=[Depends(require_token)])
def list_workspaces() -> List[Workspace]:
    """List drafting workspaces and their file counts."""
    return _scriptorium().list_workspaces()


class WorkspaceRequest(BaseModel):
    name: str = Field(description="Workspace slug: lowercase letters, digits, '.', '_', '-'.")


@app.post("/workspaces", operation_id="createWorkspace", dependencies=[Depends(require_token)])
def create_workspace(body: WorkspaceRequest) -> WorkspaceCreated:
    """Create a drafting workspace."""
    return _scriptorium().create_workspace(body.name)


@app.get("/workspaces/{workspace}/files", operation_id="listFiles", dependencies=[Depends(require_token)])
def list_files(workspace: str, subdir: str = "") -> List[FileEntry]:
    """List files in a workspace, optionally under a subdirectory."""
    return _scriptorium().list_files(workspace, subdir)


@app.get("/workspaces/{workspace}/file", operation_id="readFile", dependencies=[Depends(require_token)])
def read_file(workspace: str, path: str) -> FileContent:
    """Read a text file from a workspace."""
    return {"workspace": workspace, "path": path, "content": _scriptorium().read_file(workspace, path)}


class WriteFileRequest(BaseModel):
    path: str = Field(description="File path relative to the workspace root.")
    content: str
    append: bool = Field(False, description="Append instead of overwrite.")


@app.put("/workspaces/{workspace}/file", operation_id="writeFile", dependencies=[Depends(require_token)])
def write_file(workspace: str, body: WriteFileRequest) -> WriteReceipt:
    """Write (or append to) a text file in a workspace. Atomic; parents auto-created."""
    return _scriptorium().write_file(workspace, body.path, body.content, append=body.append)


class MoveFileRequest(BaseModel):
    source: str
    destination: str


@app.post("/workspaces/{workspace}/move", operation_id="moveFile", dependencies=[Depends(require_token)])
def move_file(workspace: str, body: MoveFileRequest) -> MoveReceipt:
    """Move or rename a file within a workspace."""
    return _scriptorium().move_file(workspace, body.source, body.destination)


@app.delete("/workspaces/{workspace}/file", operation_id="deleteFile", dependencies=[Depends(require_token)])
def delete_file(workspace: str, path: str) -> DeleteReceipt:
    """Delete a single file (never a directory) from a workspace."""
    return _scriptorium().delete_file(workspace, path)


# -- the accessions desk ------------------------------------------------------
# Where drafts become visible to the catalog (cards), cross the counter into
# The Stack (check-in), and come back out for revision (check-out copy).

class DraftDescriptor(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = Field(None, description="'<workspace>/<path>' — the card's external id.")
    workspace: Optional[str] = None
    path: Optional[str] = None
    title: Optional[str] = None
    excerpt: Optional[str] = None
    sha256: Optional[str] = None
    size: Optional[int] = None


class AccessionEntry(BaseModel):
    """One object's outcome in a card/check-in report."""
    model_config = ConfigDict(extra="allow")

    record_id: Optional[str] = None
    external_id: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    card_upgraded: Optional[bool] = None
    reason: Optional[str] = Field(None, description="Why the object was skipped.")
    object: Optional[str] = None
    error: Optional[str] = None


class CardReceipt(BaseModel):
    model_config = ConfigDict(extra="allow")

    card_id: Optional[str] = None
    descriptor: Optional[DraftDescriptor] = None
    status: Optional[str] = None
    source: Optional[str] = None
    cataloged: Optional[int] = None
    cards: List[str] = []
    errors: List[AccessionEntry] = []


class CheckinReport(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: Optional[str] = None
    source: Optional[str] = None
    held: Optional[int] = Field(None, description="How many drafts were accessioned.")
    checked_in: List[AccessionEntry] = []
    skipped: List[AccessionEntry] = []
    errors: List[AccessionEntry] = []


class CheckoutCopy(BaseModel):
    model_config = ConfigDict(extra="allow")

    record_id: Optional[str] = None
    workspace: Optional[str] = None
    path: Optional[str] = None
    size: Optional[int] = None
    custody: Optional[str] = Field(None, description="Always 'the-stack' — the copy is a working copy.")
    checked_out_at: Optional[str] = None


class CardDraftRequest(BaseModel):
    path: str = Field(description="Draft path relative to the workspace root.")


@app.post("/workspaces/{workspace}/card", operation_id="cardDraft", dependencies=[Depends(require_token)])
def card_draft(workspace: str, body: CardDraftRequest) -> CardReceipt:
    """File (or refresh) a catalog card for a draft: the Library learns the
    draft exists (title, excerpt, hash, size) without taking custody."""
    return accessions.card_draft(workspace, body.path, _scriptorium(), _library())


class CheckInDraftRequest(BaseModel):
    path: str = Field(description="Draft path relative to the workspace root.")
    supersedes: Optional[str] = Field(
        None, description="record_id this accession supersedes (a pointer record or a prior fossil being revised).")


@app.post("/workspaces/{workspace}/checkin", operation_id="checkInDraft", dependencies=[Depends(require_token)])
def check_in_draft(workspace: str, body: CheckInDraftRequest) -> CheckinReport:
    """Accession a reviewed draft into The Stack (operator-gated — only on the
    operator's instruction). Cards it, checks the full text in as an immutable
    record, and the Library enriches and links it afterward."""
    return accessions.check_in_draft(
        workspace, body.path, _scriptorium(), _library(), supersedes=body.supersedes)


class CheckOutCopyRequest(BaseModel):
    workspace: str = Field(description="Workspace to place the working copy in (created if needed).")
    path: Optional[str] = Field(None, description="Target file path; defaults to '<record_id>.md'.")


@app.post("/library/records/{record_id}/checkout-to-workspace", operation_id="checkOutToWorkspace",
          dependencies=[Depends(require_token)])
def check_out_to_workspace(record_id: str, body: CheckOutCopyRequest) -> CheckoutCopy:
    """Place an editable working copy of a held record into a workspace.
    Custody stays with The Stack; re-check-in with supersedes preserves history."""
    result = accessions.check_out_to_workspace(
        record_id, body.workspace, _scriptorium(), _library(), path=body.path)
    if result is None:
        raise HTTPException(404, f"Record '{record_id}' is not held in The Stack.")
    return result


# The GPT actions importer rejects bare-object schemas, and FastAPI's
# auto-generated 422 validation responses contain one (ValidationError.ctx).
# Actions never consume 422 bodies, so strip them from the published spec.
_default_openapi = app.openapi


def _openapi_for_actions():
    already_built = app.openapi_schema is not None
    spec = _default_openapi()
    if already_built:
        return spec
    for operations in spec["paths"].values():
        for operation in operations.values():
            operation.get("responses", {}).pop("422", None)
    for schema_name in ("HTTPValidationError", "ValidationError"):
        spec.get("components", {}).get("schemas", {}).pop(schema_name, None)
    return spec


app.openapi = _openapi_for_actions
