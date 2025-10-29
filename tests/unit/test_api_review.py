"""Unit tests for the review API router.

These tests use FastAPI's TestClient and a mocked ReviewStore to verify
API behavior without touching the filesystem.
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from i4g.api.app import app
from i4g.api.review import get_store

client = TestClient(app)


def make_mock_store():
    ms = MagicMock()
    ms.enqueue_case.return_value = "rev-1"
    ms.get_queue.return_value = [{"review_id": "rev-1", "case_id": "CASE-A", "status": "queued"}]
    ms.get_review.return_value = {"review_id": "rev-1", "case_id": "CASE-A", "status": "queued"}
    ms.update_status.return_value = None
    ms.log_action.return_value = "action-1"
    ms.get_actions.return_value = [{"action_id": "action-1", "actor": "analyst"}]
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
