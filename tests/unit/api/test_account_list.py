"""Tests for the account list API router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from i4g.api.account_list import get_account_list_service, require_account_list_key
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
    app.dependency_overrides[require_account_list_key] = lambda: None
    client = TestClient(app)

    payload = {
        "start_time": "2025-11-01T00:00:00Z",
        "end_time": "2025-11-15T23:59:59Z",
        "categories": ["bank"],
        "top_k": 25,
        "include_sources": False,
    }

    response = client.post("/accounts/extract", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "acc-test-1"
    assert body["metadata"]["indicator_count"] == 1
    assert "artifacts" in body
    assert service.seen_request is not None
    assert service.seen_request.top_k == 25

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
    app.dependency_overrides[require_account_list_key] = lambda: None
    client = TestClient(app)

    payload = {
        "categories": ["bank"],
        "top_k": 300,
    }

    response = client.post("/accounts/extract", json=payload)
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
