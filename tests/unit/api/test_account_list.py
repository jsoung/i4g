"""Tests for the account list API router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from i4g.api.account_list import get_account_list_service, get_review_store
from i4g.api.app import create_app
from i4g.services.account_list import AccountListRequest, AccountListResult, FinancialIndicator


class _StubAccountListService:
    def __init__(self, result: AccountListResult) -> None:
        self.result = result
        self.seen_request: AccountListRequest | None = None

    def run(self, request: AccountListRequest) -> AccountListResult:
        self.seen_request = request
        return self.result


def test_extract_accounts_success(monkeypatch):
    result = AccountListResult(
        request_id="acc-test-1",
        generated_at=datetime.now(tz=timezone.utc),
        indicators=[
            FinancialIndicator(
                category="bank",
                item="Community Credit Union",
                type="bank_account",
                number="****1234",
                source_case_id="case-1",
                metadata={},
            )
        ],
        sources=[],
        warnings=[],
        metadata={"indicator_count": 1},
    )
    service = _StubAccountListService(result)
    app = create_app()
    app.dependency_overrides[get_account_list_service] = lambda: service
    client = TestClient(app)

    log_calls: list[dict[str, object]] = []

    def _capture_log(**kwargs):
        log_calls.append(kwargs)

    monkeypatch.setattr("i4g.api.account_list.log_account_list_run", _capture_log)

    payload = {
        "start_time": "2025-11-01T00:00:00Z",
        "end_time": "2025-11-15T23:59:59Z",
        "categories": ["bank"],
        "top_k": 25,
        "include_sources": False,
    }

    response = client.post(
        "/accounts/extract",
        json=payload,
        headers={"X-API-KEY": "dev-analyst-token"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "acc-test-1"
    assert body["metadata"]["indicator_count"] == 1
    assert "artifacts" in body
    assert service.seen_request is not None
    assert service.seen_request.top_k == 25
    assert log_calls
    assert log_calls[0]["actor"].startswith("accounts_api")
    assert log_calls[0]["result"].request_id == "acc-test-1"

    app.dependency_overrides.clear()


def test_extract_accounts_rejects_large_top_k():
    app = create_app()
    app.dependency_overrides[get_account_list_service] = lambda: _StubAccountListService(
        AccountListResult(
            request_id="unused",
            generated_at=datetime.now(tz=timezone.utc),
            indicators=[],
            sources=[],
            warnings=[],
            metadata={},
        )
    )
    client = TestClient(app)

    payload = {
        "categories": ["bank"],
        "top_k": 300,
    }

    response = client.post(
        "/accounts/extract",
        json=payload,
        headers={"X-API-KEY": "dev-analyst-token"},
    )
    assert response.status_code == 400
    assert "top_k" in response.json()["detail"]

    app.dependency_overrides.clear()


def test_extract_accounts_requires_api_key():
    app = create_app()
    app.dependency_overrides[get_account_list_service] = lambda: _StubAccountListService(
        AccountListResult(
            request_id="unused",
            generated_at=datetime.now(tz=timezone.utc),
            indicators=[],
            sources=[],
            warnings=[],
            metadata={},
        )
    )
    client = TestClient(app)

    payload = {"categories": ["bank"], "top_k": 5}
    response = client.post("/accounts/extract", json=payload)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid account list API key"

    app.dependency_overrides.clear()


def test_list_account_runs_returns_audit_entries(monkeypatch):
    generated_at = datetime.now(tz=timezone.utc).isoformat()
    store_calls: list[dict[str, object]] = []

    class _StubStore:
        def get_recent_actions(self, action: str, limit: int):
            store_calls.append({"action": action, "limit": limit})
            return [
                {
                    "review_id": "account-run-1234",
                    "actor": "accounts_api:analyst",
                    "action": "account_list_run",
                    "payload": {
                        "source": "api",
                        "actor": "accounts_api:analyst",
                        "indicator_count": 3,
                        "source_count": 2,
                        "artifacts": {"pdf": "gs://bucket/report.pdf"},
                        "warnings": ["warning"],
                        "generated_at": generated_at,
                        "categories": ["bank"],
                        "metadata": {"requested_top_k": 10},
                    },
                    "created_at": generated_at,
                }
            ]

    app = create_app()
    app.dependency_overrides[get_review_store] = lambda: _StubStore()
    client = TestClient(app)

    response = client.get("/accounts/runs", headers={"X-API-KEY": "dev-analyst-token"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["runs"][0]["request_id"] == "account-run-1234"
    assert payload["runs"][0]["artifacts"]["pdf"].endswith("report.pdf")
    assert store_calls == [{"action": "account_list_run", "limit": 20}]

    app.dependency_overrides.clear()
