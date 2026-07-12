"""The accessions desk: card_draft, check_in_draft, check_out_to_workspace.

The Library is stubbed out — these tests exercise the shell's descriptor
building, desk orchestration, and REST routes. The daemon-side behavior
(card upsert, fossil, enrichment) is covered in cortex-os's own suite.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

import scriptoria.api as api
from scriptoria import accessions
from scriptoria.api import app
from scriptoria.scriptorium import Scriptorium

DRAFT = "# The Essay\n\nDraft text exactly as written.\n"


class FakeLibrary:
    def __init__(self, checkout_envelope=None):
        self.synced = []
        self.checked_in = []
        self.checkout_envelope = checkout_envelope

    def catalog_sync(self, objects, source="mnemos", limit=None):
        self.synced.append((source, objects))
        return {"status": "cataloged", "source": source,
                "cataloged": len(objects), "cards": [f"{source}:{o['id']}" for o in objects],
                "errors": []}

    def checkin(self, objects, source="mnemos"):
        self.checked_in.append((source, objects))
        return {"status": "checked_in", "source": source, "held": len(objects),
                "checked_in": [{"record_id": f"{source}_x", "external_id": o["id"],
                                "type": "IDEA", "status": "captured", "card_upgraded": True}
                               for o in objects],
                "skipped": [], "errors": []}

    def checkout(self, record_id):
        return self.checkout_envelope


@pytest.fixture
def scriptorium(tmp_path):
    s = Scriptorium(root=tmp_path)
    s.create_workspace("fable_5")
    s.write_file("fable_5", "essay.md", DRAFT)
    return s


def test_describe_draft_builds_the_card_descriptor(scriptorium):
    descriptor = scriptorium.describe_draft("fable_5", "essay.md")
    assert descriptor["id"] == "fable_5/essay.md"
    assert descriptor["title"] == "The Essay"
    assert descriptor["sha256"] == hashlib.sha256(DRAFT.encode()).hexdigest()
    assert descriptor["size"] == len(DRAFT.encode())
    assert "\n" not in descriptor["excerpt"]
    assert "content" not in descriptor, "carding must not take custody"
    with_content = scriptorium.describe_draft("fable_5", "essay.md", include_content=True)
    assert with_content["content"] == DRAFT


def test_describe_draft_title_falls_back_to_filename(scriptorium):
    scriptorium.write_file("fable_5", "no-heading.md", "just prose, no heading")
    assert scriptorium.describe_draft("fable_5", "no-heading.md")["title"] == "no-heading.md"


def test_card_draft_sends_metadata_only(scriptorium):
    library = FakeLibrary()
    receipt = accessions.card_draft("fable_5", "essay.md", scriptorium, library)
    assert receipt["card_id"] == "scriptorium:fable_5/essay.md"
    [(source, objects)] = library.synced
    assert source == "scriptorium" and objects[0]["id"] == "fable_5/essay.md"
    assert "content" not in objects[0]
    assert library.checked_in == [], "carding must not check anything in"


def test_check_in_draft_cards_then_ships_content(scriptorium):
    library = FakeLibrary()
    report = accessions.check_in_draft("fable_5", "essay.md", scriptorium, library,
                                       supersedes="idea_pointer1")
    assert report["held"] == 1
    [(_, card_objects)] = library.synced
    assert "content" not in card_objects[0] and "supersedes" not in card_objects[0]
    [(source, objects)] = library.checked_in
    assert source == "scriptorium"
    assert objects[0]["content"] == DRAFT
    assert objects[0]["supersedes"] == "idea_pointer1"


def test_check_out_to_workspace_places_a_working_copy(scriptorium):
    envelope = {"record": {"record_id": "scriptorium_x", "raw_capture": DRAFT},
                "custody": "the-stack", "checked_out_at": "2026-07-12T13:00:00Z"}
    library = FakeLibrary(checkout_envelope=envelope)
    copy = accessions.check_out_to_workspace("scriptorium_x", "revisions", scriptorium, library)
    assert copy["path"] == "scriptorium_x.md" and copy["custody"] == "the-stack"
    assert scriptorium.read_file("revisions", "scriptorium_x.md") == DRAFT
    # unknown record: None, nothing written
    assert accessions.check_out_to_workspace("nope", "revisions", scriptorium, FakeLibrary()) is None


# -- REST door ---------------------------------------------------------------

@pytest.fixture
def client(monkeypatch, scriptorium):
    monkeypatch.setenv("SCRIPTORIA_API_TOKEN", "test-token")
    monkeypatch.setattr(api, "_scriptorium", lambda: scriptorium)
    return TestClient(app)


AUTH = {"Authorization": "Bearer test-token"}


def test_routes_require_bearer(client):
    assert client.post("/workspaces/fable_5/card", json={"path": "essay.md"}).status_code == 401
    assert client.post("/workspaces/fable_5/checkin", json={"path": "essay.md"}).status_code == 401
    assert client.post("/library/records/x/checkout-to-workspace",
                       json={"workspace": "w"}).status_code == 401


def test_card_and_checkin_routes(client, monkeypatch):
    library = FakeLibrary()
    monkeypatch.setattr(api, "_library", lambda: library)
    response = client.post("/workspaces/fable_5/card", json={"path": "essay.md"}, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["card_id"] == "scriptorium:fable_5/essay.md"

    response = client.post("/workspaces/fable_5/checkin",
                           json={"path": "essay.md", "supersedes": "idea_p1"}, headers=AUTH)
    assert response.status_code == 200
    body = response.json()
    assert body["held"] == 1 and body["checked_in"][0]["card_upgraded"] is True
    assert library.checked_in[0][1][0]["supersedes"] == "idea_p1"


def test_checkout_to_workspace_route(client, monkeypatch, scriptorium):
    envelope = {"record": {"record_id": "scriptorium_x", "raw_capture": DRAFT},
                "custody": "the-stack", "checked_out_at": "2026-07-12T13:00:00Z"}
    monkeypatch.setattr(api, "_library", lambda: FakeLibrary(checkout_envelope=envelope))
    response = client.post("/library/records/scriptorium_x/checkout-to-workspace",
                           json={"workspace": "revisions", "path": "essay-v2.md"}, headers=AUTH)
    assert response.status_code == 200
    assert response.json()["path"] == "essay-v2.md"
    assert scriptorium.read_file("revisions", "essay-v2.md") == DRAFT

    monkeypatch.setattr(api, "_library", lambda: FakeLibrary())
    assert client.post("/library/records/nope/checkout-to-workspace",
                       json={"workspace": "revisions"}, headers=AUTH).status_code == 404
