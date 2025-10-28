"""Unit tests for the review API router.

These tests use FastAPI's TestClient and a mocked ReviewStore to verify
API behavior without touching the filesystem.
"""

from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from i4g.api.app import app
from i4g.api.review import get_store


client = TestClient(app)


def make_mock_store():
    ms = MagicMock()
    actions = []

    def log_action_impl(review_id, actor, action, payload=None):
        action_id = f"action-{len(actions) + 1}"
        actions.append({"action_id": action_id, "actor": actor, "action": action, "review_id": review_id})
        return action_id

    def get_actions_impl(review_id):
        return [a for a in actions if a["review_id"] == review_id]

    ms.enqueue_case.return_value = "rev-1"
    ms.get_queue.return_value = [{"review_id": "rev-1", "case_id": "CASE-A", "status": "queued"}]
    ms.get_review.return_value = {"review_id": "rev-1", "case_id": "CASE-A", "status": "queued"}
    ms.update_status.return_value = None
    ms.log_action.side_effect = log_action_impl
    ms.get_actions.side_effect = get_actions_impl
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
    app.dependency_overrides.clear()


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
    assert len(r3.json()["actions"]) == 2
    app.dependency_overrides.clear()