"""Unit tests for the review API router.

These tests use FastAPI's TestClient and a mocked ReviewStore to verify
API behavior without touching the filesystem.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from i4g.api.app import app
from i4g.api.review import get_retriever, get_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_rate_limit():
    from i4g.api import app as app_module

    app_module.REQUEST_LOG.clear()
    yield
    app_module.REQUEST_LOG.clear()


def make_mock_store():
    ms = MagicMock()
    ms.enqueue_case.return_value = "rev-1"
    ms.get_queue.return_value = [{"review_id": "rev-1", "case_id": "CASE-A", "status": "queued"}]
    ms.get_review.return_value = {
        "review_id": "rev-1",
        "case_id": "CASE-A",
        "status": "queued",
    }
    ms.update_status.return_value = None
    ms.log_action.return_value = "action-1"
    ms.get_actions.return_value = [{"action_id": "action-1", "actor": "analyst"}]
    ms.get_reviews_by_case.return_value = []
    ms.get_recent_actions.return_value = [
        {
            "action_id": "search-1",
            "review_id": "search",
            "actor": "analyst_1",
            "action": "search",
            "payload": {"search_id": "search:abc", "text": "wallet"},
            "created_at": "2024-01-01T00:00:00Z",
        }
    ]
    ms.bulk_update_tags.return_value = 1
    ms.clone_saved_search.return_value = "saved:shared"
    return ms


def test_enqueue_and_list_queue():
    mock_store = make_mock_store()
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    payload = {"case_id": "CASE-A", "priority": "high"}
    r = client.post("/reviews/", json=payload, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["review_id"] == "rev-1"

    r2 = client.get("/reviews/queue", headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert data["count"] == 1

    app.dependency_overrides = {}


def test_claim_and_decision_and_actions():
    mock_store = make_mock_store()
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.post("/reviews/rev-1/claim", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "in_review"

    dec = {"decision": "accepted", "notes": "Looks valid"}
    r2 = client.post("/reviews/rev-1/decision", json=dec, headers=headers)
    assert r2.status_code == 200
    assert r2.json()["status"] == "accepted"

    r3 = client.get("/reviews/rev-1/actions", headers=headers)
    assert r3.status_code == 200
    assert len(r3.json()["actions"]) == 1

    app.dependency_overrides = {}


def test_search_cases_returns_combined_results():
    mock_retriever = MagicMock()
    mock_retriever.query.return_value = {
        "results": [
            {"case_id": "CASE-A", "score": 0.8, "sources": ["vector"]},
            {"case_id": "CASE-B", "score": None, "sources": ["structured"]},
        ],
        "total": 10,
        "vector_hits": 6,
        "structured_hits": 7,
    }
    mock_store = make_mock_store()
    app.dependency_overrides[get_retriever] = lambda: mock_retriever
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.get(
        "/reviews/search",
        params={
            "text": "wallet",
            "classification": "crypto_investment",
            "limit": 5,
            "vector_limit": 7,
            "structured_limit": 3,
            "offset": 2,
            "page_size": 4,
        },
        headers=headers,
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] == 2
    assert payload["offset"] == 2
    assert payload["limit"] == 4
    assert payload["total"] == mock_retriever.query.return_value["total"]
    assert payload["vector_hits"] == mock_retriever.query.return_value["vector_hits"]
    assert payload["structured_hits"] == mock_retriever.query.return_value["structured_hits"]
    assert payload["search_id"].startswith("search:")
    assert payload["results"][0]["case_id"] == "CASE-A"
    mock_retriever.query.assert_called_once_with(
        text="wallet",
        filters={"classification": "crypto_investment"},
        vector_top_k=7,
        structured_top_k=3,
        offset=2,
        limit=4,
    )

    mock_store.log_action.assert_called_once()

    app.dependency_overrides = {}


def test_reviews_by_case_endpoint():
    mock_store = make_mock_store()
    mock_store.get_reviews_by_case.return_value = [
        {"review_id": "rev-1", "case_id": "CASE-A", "status": "queued"},
        {"review_id": "rev-2", "case_id": "CASE-A", "status": "accepted"},
    ]
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.get("/reviews/case/CASE-A", params={"limit": 2}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert body["case_id"] == "CASE-A"
    mock_store.get_reviews_by_case.assert_called_once_with(case_id="CASE-A", limit=2)

    app.dependency_overrides = {}


def test_search_history_returns_recent_events():
    mock_store = make_mock_store()
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.get("/reviews/search/history", params={"limit": 5}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["events"][0]["payload"]["search_id"] == "search:abc"
    mock_store.get_recent_actions.assert_called_once_with(action="search", limit=5)

    app.dependency_overrides = {}


def test_saved_search_crud():
    mock_store = make_mock_store()
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    payload = {
        "name": "Wallet scam",
        "params": {"text": "wallet", "classification": "crypto"},
        "tags": ["wallet", "urgent"],
    }
    mock_store.upsert_saved_search.return_value = "saved:123"
    r = client.post("/reviews/search/saved", json=payload, headers=headers)
    assert r.status_code == 200
    mock_store.upsert_saved_search.assert_called_once_with(
        payload["name"],
        payload["params"],
        owner="analyst_1",
        search_id=None,
        favorite=False,
        tags=payload["tags"],
    )

    r_json = r.json()
    assert "search_id" in r_json

    mock_store.list_saved_searches.return_value = [
        {
            "search_id": "saved:123",
            "name": "Wallet scam",
            "params": payload["params"],
            "owner": "analyst_1",
        }
    ]
    r2 = client.get(
        "/reviews/search/saved",
        params={"limit": 10, "owner_only": True},
        headers=headers,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["count"] == 1
    mock_store.list_saved_searches.assert_called_once_with(owner="analyst_1", limit=10)

    mock_store.update_saved_search.return_value = True
    patch_payload = {"name": "Wallet scam v2", "favorite": True}
    r_patch = client.patch("/reviews/search/saved/saved:123", json=patch_payload, headers=headers)
    assert r_patch.status_code == 200
    mock_store.update_saved_search.assert_called_once_with(
        "saved:123", name="Wallet scam v2", params=None, favorite=True, tags=None
    )

    mock_store.delete_saved_search.return_value = True
    r3 = client.delete("/reviews/search/saved/saved:123", headers=headers)
    assert r3.status_code == 200
    mock_store.delete_saved_search.assert_called_once_with("saved:123")

    app.dependency_overrides = {}


def test_saved_search_duplicate_handling_returns_409():
    mock_store = make_mock_store()
    mock_store.upsert_saved_search.side_effect = ValueError("duplicate_saved_search:analyst_1")
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    payload = {"name": "Wallet scam", "params": {}}
    r = client.post("/reviews/search/saved", json=payload, headers=headers)
    assert r.status_code == 409
    assert r.json()["detail"] == "Saved search name already exists (owner=analyst_1)"

    app.dependency_overrides = {}


def test_share_saved_search_endpoint():
    mock_store = make_mock_store()
    mock_store.clone_saved_search.return_value = "saved:shared"
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.post("/reviews/search/saved/saved:123/share", headers=headers)
    assert r.status_code == 200
    assert r.json()["search_id"] == "saved:shared"
    mock_store.clone_saved_search.assert_called_once_with("saved:123", target_owner=None)

    app.dependency_overrides = {}


def test_share_saved_search_duplicate_returns_409():
    mock_store = make_mock_store()
    mock_store.clone_saved_search.side_effect = ValueError("duplicate_saved_search:")
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.post("/reviews/search/saved/saved:123/share", headers=headers)
    assert r.status_code == 409
    assert r.json()["detail"] == "Shared search name already exists (owner=shared)"

    app.dependency_overrides = {}


def test_share_saved_search_not_found_returns_404():
    mock_store = make_mock_store()
    mock_store.clone_saved_search.side_effect = ValueError("saved_search_not_found")
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.post("/reviews/search/saved/missing/share", headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "Saved search not found"

    app.dependency_overrides = {}


def test_tag_presets_endpoint():
    mock_store = make_mock_store()
    mock_store.list_tag_presets.return_value = [
        {"search_id": "saved:123", "owner": "analyst_1", "tags": ["wallet", "urgent"]}
    ]
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.get(
        "/reviews/search/tag-presets",
        params={"limit": 10, "owner_only": True},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["presets"][0]["tags"] == ["wallet", "urgent"]
    mock_store.list_tag_presets.assert_called_once_with(owner="analyst_1", limit=10)

    app.dependency_overrides = {}


def test_bulk_update_tags_endpoint():
    mock_store = make_mock_store()
    mock_store.bulk_update_tags.return_value = 2
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    payload = {
        "search_ids": ["saved:1", "saved:2"],
        "add": ["wallet"],
        "remove": ["old"],
    }
    r = client.post("/reviews/search/saved/bulk-tags", json=payload, headers=headers)
    assert r.status_code == 200
    assert r.json()["updated"] == 2
    mock_store.bulk_update_tags.assert_called_once()

    app.dependency_overrides = {}


def test_export_saved_search_endpoint():
    mock_store = make_mock_store()
    mock_store.get_saved_search.return_value = {
        "search_id": "saved:123",
        "name": "Wallet",
        "params": {"text": "wallet"},
        "favorite": True,
        "owner": "analyst_1",
    }
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    r = client.get("/reviews/search/saved/saved:123/export", headers=headers)
    assert r.status_code == 200
    payload = r.json()
    assert payload["favorite"] is True
    mock_store.get_saved_search.assert_called_once_with("saved:123")

    app.dependency_overrides = {}


def test_import_saved_search_endpoint_handles_duplicates():
    mock_store = make_mock_store()
    mock_store.import_saved_search.side_effect = ValueError("duplicate_saved_search:")
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    payload = {"name": "Wallet", "params": {"text": "wallet"}}
    r = client.post("/reviews/search/saved/import", json=payload, headers=headers)
    assert r.status_code == 409
    assert "Saved search name already exists" in r.json()["detail"]

    app.dependency_overrides = {}


@patch("i4g.api.review.generate_report_for_case")
def test_decision_triggers_background_report(mock_generate_report):
    """Ensure that when an analyst accepts a case with auto_generate_report=True,
    the API schedules the generate_report_for_case background task.
    """
    mock_store = make_mock_store()
    app.dependency_overrides[get_store] = lambda: mock_store

    headers = {"X-API-KEY": "dev-analyst-token"}
    # include the auto_generate_report flag in the request
    dec = {"decision": "accepted", "notes": "Auto report", "auto_generate_report": True}
    r = client.post("/reviews/rev-1/decision", json=dec, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # BackgroundTasks runs synchronously in TestClient, so the patched function should have been called
    assert mock_generate_report.called
    mock_generate_report.assert_called_with("rev-1", mock_store)

    app.dependency_overrides = {}
