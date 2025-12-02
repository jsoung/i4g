"""Tests for the account list audit helper."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from i4g.services.account_list.audit import log_account_list_run
from i4g.services.account_list.models import AccountListResult, FinancialIndicator, SourceDocument


class _StubStore:
    def __init__(self) -> None:
        self.placeholders: list[tuple[str, str]] = []
        self.actions: list[dict[str, object]] = []

    def ensure_placeholder_review(self, review_id: str, case_id: str) -> None:
        self.placeholders.append((review_id, case_id))

    def log_action(self, review_id: str, *, actor: str, action: str, payload: dict[str, object]) -> None:
        self.actions.append(
            {
                "review_id": review_id,
                "actor": actor,
                "action": action,
                "payload": payload,
            }
        )


def _build_result() -> AccountListResult:
    now = datetime(2025, 11, 28, tzinfo=timezone.utc)
    return AccountListResult(
        request_id="acct-1",
        generated_at=now,
        indicators=[
            FinancialIndicator(
                category="bank",
                item="Example Bank",
                type="bank_account",
                number="1111",
                source_case_id="case-1",
            ),
            FinancialIndicator(
                category="crypto",
                item="Example Chain",
                type="wallet",
                number="abcd",
                source_case_id="case-2",
            ),
        ],
        sources=[
            SourceDocument(case_id="case-1", content="doc 1", dataset="structured"),
            SourceDocument(case_id="case-2", content="doc 2", dataset="vector"),
        ],
        warnings=["Drive upload failed"],
        metadata={"indicator_count": 2},
        artifacts={"csv": "gs://bucket/acct-1.csv"},
    )


def test_log_account_list_run_records_action():
    store = _StubStore()
    result = _build_result()

    log_account_list_run(actor="api", source="api", result=result, store=store)

    assert store.placeholders == [("acct-1", "account-list:acct-1")]
    assert len(store.actions) == 1
    entry = store.actions[0]
    assert entry["review_id"] == "acct-1"
    assert entry["actor"] == "api"
    payload = entry["payload"]
    assert payload["indicator_count"] == 2
    assert payload["source_count"] == 2
    assert payload["categories"] == ["bank", "crypto"]
    assert payload["artifacts"] == {"csv": "gs://bucket/acct-1.csv"}
    assert payload["warnings"] == ["Drive upload failed"]
    assert payload["metadata"] == {"indicator_count": 2}


class _FailPlaceholderStore(_StubStore):
    def ensure_placeholder_review(self, review_id: str, case_id: str) -> None:  # type: ignore[override]
        raise RuntimeError("boom")


def test_log_account_list_run_aborts_when_placeholder_fails(caplog: pytest.LogCaptureFixture):
    store = _FailPlaceholderStore()
    result = _build_result()

    with caplog.at_level("ERROR"):
        log_account_list_run(actor="api", source="worker", result=result, store=store)

    assert not store.actions
    assert any("account list" in record.message for record in caplog.records)
