"""Scriptoria's REST API — the door for custom GPT actions.

Every route is bearer-gated by SCRIPTORIA_API_TOKEN except /health. The
OpenAPI spec at /openapi.json imports directly into a ChatGPT custom GPT
as actions; operation IDs are the librarian's tool names.

Run locally: uv run uvicorn scriptoria.api:app --port 8020
"""

from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from scriptoria import config
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
