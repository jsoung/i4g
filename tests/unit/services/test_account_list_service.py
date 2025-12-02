"""Tests for the AccountListService orchestration logic."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from i4g.services.account_list.models import AccountListRequest, FinancialIndicator, SourceDocument
from i4g.services.account_list.queries import IndicatorQuery
from i4g.services.account_list.service import AccountListService


class _StubRetriever:
    def __init__(self) -> None:
        self.calls: List[str] = []

    def fetch_documents(self, *, indicator_query: IndicatorQuery, **_: object) -> List[SourceDocument]:
        self.calls.append(indicator_query.slug)
        return [
            SourceDocument(
                case_id="case-1",
                content="Wire transfer to Example Bank",
                dataset="test",
            )
        ]


class _StubExtractor:
    def extract_indicators(self, *, query: IndicatorQuery, **_: object) -> List[FinancialIndicator]:
        return [
            FinancialIndicator(
                category=query.slug,
                item="Example Bank",
                type="bank_account",
                number="****1111",
                source_case_id="case-1",
            )
        ]


class _StubExporter:
    def __init__(self) -> None:
        self.invocations: int = 0

    def export(self, result: object, formats: List[str]):
        self.invocations += 1
        assert "csv" in formats
        return {"csv": "/tmp/account_list.csv"}, []


def test_service_generates_artifacts():
    service = AccountListService(
        retriever=_StubRetriever(),
        extractor=_StubExtractor(),
        exporter=_StubExporter(),
    )

    request = AccountListRequest(
        categories=["bank"],
        output_formats=["csv"],
        start_time=datetime(2025, 11, 1, tzinfo=timezone.utc),
        end_time=datetime(2025, 11, 25, tzinfo=timezone.utc),
    )

    result = service.run(request)

    assert result.indicators
    assert result.artifacts["csv"] == "/tmp/account_list.csv"
    assert not result.warnings


def test_service_merges_exporter_warnings():
    class _WarnExporter(_StubExporter):
        def export(self, result: object, formats: List[str]):
            payload, _ = super().export(result, formats)
            return payload, ["Drive upload failed"]

    service = AccountListService(
        retriever=_StubRetriever(),
        extractor=_StubExtractor(),
        exporter=_WarnExporter(),
    )

    request = AccountListRequest(categories=["bank"], output_formats=["csv"])

    result = service.run(request)

    assert "Drive upload failed" in result.warnings
