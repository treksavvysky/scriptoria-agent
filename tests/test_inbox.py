"""The operator inbox at /inbox: token-gated HTML view of captured records.

The Library is stubbed out — these tests exercise only the shell's route.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import scriptoria.api as api
from scriptoria.api import app


class FakeLibrary:
    def __init__(self, records):
        self.records = records

    def search_records(self, **filters):
        assert filters.get("status") == "captured"
        return list(self.records)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SCRIPTORIA_API_TOKEN", "test-token")
    return TestClient(app)


def _shelve(monkeypatch, records):
    monkeypatch.setattr(api, "_library", lambda: FakeLibrary(records))


def _days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_inbox_without_token_is_401_json(client, monkeypatch):
    _shelve(monkeypatch, [])
    for response in (client.get("/inbox"), client.get("/inbox", params={"token": "wrong"})):
        assert response.status_code == 401
        assert "token" in response.json()["detail"].lower()


def test_inbox_with_token_is_200_html(client, monkeypatch):
    _shelve(monkeypatch, [])
    response = client.get("/inbox", params={"token": "test-token"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_captured_records_rendered_oldest_first_and_escaped(client, monkeypatch):
    _shelve(monkeypatch, [
        {
            "record_id": "idea_new",
            "timestamp": _days_ago(1),
            "origin_context": "custom-gpt",
            "raw_capture": "Fresh thought with <script>alert('markup')</script>",
        },
        {
            "record_id": "idea_old",
            "timestamp": _days_ago(10),
            "origin_context": "claude-session",
            "raw_capture": "Stale thought",
        },
    ])
    page = client.get("/inbox", params={"token": "test-token"}).text
    assert "idea_old" in page and "idea_new" in page
    assert page.index("idea_old") < page.index("idea_new")  # oldest first
    assert "custom-gpt" in page and "claude-session" in page
    assert "10 days old" in page and "1 day old" in page
    assert "Stale thought" in page
    assert "<script>alert" not in page  # raw_capture is escaped
    assert "&lt;script&gt;alert(&#x27;markup&#x27;)&lt;/script&gt;" in page


def test_empty_inbox_shows_fully_curated(client, monkeypatch):
    _shelve(monkeypatch, [])
    page = client.get("/inbox", params={"token": "test-token"}).text
    assert "Shelves fully curated" in page


def test_inbox_absent_from_openapi_spec(client):
    spec = client.get("/openapi.json").json()
    assert "/inbox" not in spec["paths"]
