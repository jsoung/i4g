"""Tests for FinancialEntityRetriever vector+structured merging."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from i4g.services.account_list.queries import IndicatorQuery
from i4g.services.account_list.retriever import FinancialEntityRetriever


class _FakeHybridRetriever:
    def __init__(self, results: List[Dict[str, Any]]) -> None:
        self._results = results

    def query(self, **_: Any) -> Dict[str, Any]:
        return {"results": self._results}


def _indicator_query() -> IndicatorQuery:
    return IndicatorQuery(
        slug="crypto",
        display_name="Crypto",
        indicator_type="wallet",
        query="crypto wallet",
        system_message="extract",
    )


def test_fetch_documents_includes_vector_entries() -> None:
    created_at = datetime(2025, 11, 28, tzinfo=timezone.utc).isoformat()
    hybrid = _FakeHybridRetriever(
        [
            {
                "score": 0.42,
                "vector": {
                    "case_id": "vector-case",
                    "text": "Send Bitcoin to 1FzWL...",
                    "classification": "crypto",
                    "metadata": {"dataset": "smoke", "created_at": created_at},
                    "score": 0.42,
                },
                "sources": ["vector"],
            }
        ]
    )
    retriever = FinancialEntityRetriever(hybrid=hybrid)

    docs = retriever.fetch_documents(
        indicator_query=_indicator_query(),
        top_k=10,
        start_time=None,
        end_time=None,
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.case_id == "vector-case"
    assert doc.content.startswith("Send Bitcoin")
    assert doc.classification == "crypto"
    assert doc.dataset == "smoke"
    assert doc.score == 0.42


def test_vector_entries_respect_time_window() -> None:
    created_at = datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat()
    hybrid = _FakeHybridRetriever(
        [
            {
                "score": 0.5,
                "vector": {
                    "case_id": "old-case",
                    "text": "Old crypto request",
                    "classification": "crypto",
                    "metadata": {"created_at": created_at},
                },
                "sources": ["vector"],
            }
        ]
    )
    retriever = FinancialEntityRetriever(hybrid=hybrid)

    start = datetime(2025, 2, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    docs = retriever.fetch_documents(
        indicator_query=_indicator_query(),
        top_k=5,
        start_time=start,
        end_time=end,
    )

    assert docs == []
