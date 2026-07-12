import pathlib

import pytest
from fastapi.testclient import TestClient

from scriptoria.api import app


@pytest.fixture
def client(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setenv("SCRIPTORIA_API_TOKEN", "test-token")
    monkeypatch.setenv("SCRIPTORIA_WORKSPACES_ROOT", str(tmp_path))
    return TestClient(app)


AUTH = {"Authorization": "Bearer test-token"}


def test_health_is_open(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["agent"] == "scriptoria"


def test_requests_without_token_rejected(client):
    assert client.get("/workspaces").status_code == 401
    assert client.get("/workspaces", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_workspace_file_lifecycle(client):
    assert client.post("/workspaces", json={"name": "gpt-drafts"}, headers=AUTH).json()["created"] is True
    put = client.put(
        "/workspaces/gpt-drafts/file",
        json={"path": "draft.md", "content": "# Draft\n"},
        headers=AUTH,
    )
    assert put.status_code == 200
    read = client.get("/workspaces/gpt-drafts/file", params={"path": "draft.md"}, headers=AUTH)
    assert read.json()["content"] == "# Draft\n"
    assert client.delete(
        "/workspaces/gpt-drafts/file", params={"path": "draft.md"}, headers=AUTH
    ).status_code == 200


def test_path_escape_is_400(client):
    client.post("/workspaces", json={"name": "gpt-drafts"}, headers=AUTH)
    response = client.get(
        "/workspaces/gpt-drafts/file", params={"path": "../../etc/passwd"}, headers=AUTH
    )
    assert response.status_code == 400
