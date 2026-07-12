"""The accessions desk — where scriptorium drafts cross the Library counter.

Composition layer over the two engines (docs/DESIGN-DIRECTION-ACCESSIONS-DESK.md):
the scriptorium describes a draft, the Library cards it, checks it in, or
re-exports a held record back into a workspace. The Library never reads the
shell's filesystem — descriptors and content travel over HTTP only.
"""

from typing import Any, Dict, Optional

from scriptoria.library_client import LibraryClient
from scriptoria.scriptorium import Scriptorium


def card_draft(workspace: str, path: str,
               scriptorium: Scriptorium, library: LibraryClient) -> Dict[str, Any]:
    """Files (or refreshes) a catalog card for a draft: cheap metadata only —
    id, title, excerpt, sha256, size. No content leaves the scriptorium and
    no enrichment runs; the draft merely becomes visible to the catalog."""
    descriptor = scriptorium.describe_draft(workspace, path)
    report = library.catalog_sync([descriptor], source="scriptorium")
    return {"card_id": f"scriptorium:{descriptor['id']}", "descriptor": descriptor, **report}


def check_in_draft(workspace: str, path: str,
                   scriptorium: Scriptorium, library: LibraryClient,
                   supersedes: Optional[str] = None) -> Dict[str, Any]:
    """Accessions a draft into The Stack on the operator's instruction: cards
    it (so the card flips to held), then checks the full text in as an
    immutable record. The daemon enriches and proposes links afterward —
    enrichment is what accession buys. Pass supersedes to link the new
    record over a pointer or a prior fossil."""
    descriptor = scriptorium.describe_draft(workspace, path, include_content=True)
    card = {k: v for k, v in descriptor.items() if k != "content"}
    library.catalog_sync([card], source="scriptorium")
    if supersedes:
        descriptor["supersedes"] = supersedes
    return library.checkin([descriptor], source="scriptorium")


def check_out_to_workspace(record_id: str, workspace: str,
                           scriptorium: Scriptorium, library: LibraryClient,
                           path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Places an editable working copy of a held record into a workspace.
    Custody stays with The Stack; a later re-check-in with
    supersedes=<record_id> shelves the revision as a new fossil."""
    envelope = library.checkout(record_id)
    if envelope is None:
        return None
    record = envelope.get("record") or {}
    target = path or f"{record_id}.md"
    scriptorium.create_workspace(workspace)
    receipt = scriptorium.write_file(workspace, target, record.get("raw_capture") or "")
    return {
        "record_id": record_id,
        "workspace": workspace,
        "path": target,
        "size": receipt["size"],
        "custody": "the-stack",
        "checked_out_at": envelope.get("checked_out_at"),
    }
