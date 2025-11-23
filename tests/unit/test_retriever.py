"""Unit tests for the hybrid retriever module."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from i4g.store.retriever import HybridRetriever
from i4g.store.schema import ScamRecord


def make_record(case_id: str = "case-1", classification: str = "crypto_investment") -> ScamRecord:
    return ScamRecord(
        case_id=case_id,
        text="Sample text",
        entities={"wallet_addresses": ["0x123"]},
        classification=classification,
        confidence=0.9,
        created_at=datetime.utcnow(),
    )


def test_query_semantic_only():
    structured_store = MagicMock()
    vector_store = MagicMock()
    vector_store.query_similar.return_value = [{"case_id": "case-1", "score": 0.75, "text": "sample"}]

    retriever = HybridRetriever(structured_store=structured_store, vector_store=vector_store)
    response = retriever.query(text="sample", vector_top_k=3)
    results = response["results"]

    assert len(results) == 1
    entry = results[0]
    assert entry["case_id"] == "case-1"
    assert entry["score"] == pytest.approx(1.0 / (1.0 + 0.75))
    assert entry["distance"] == pytest.approx(0.75)
    assert entry["sources"] == ["vector"]
    assert entry["vector"]["text"] == "sample"
    assert entry["vector"]["distance"] == pytest.approx(0.75)
    structured_store.search_by_field.assert_not_called()
    vector_store.query_similar.assert_called_once_with("sample", top_k=3)
    assert response["vector_hits"] == 1
    assert response["structured_hits"] == 0
    assert response["total"] == 1


def test_query_structured_filters():
    record = make_record(case_id="case-2", classification="romance_scam")
    structured_store = MagicMock()
    structured_store.search_by_field.return_value = [record]
    vector_store = MagicMock()
    vector_store.query_similar.return_value = []

    retriever = HybridRetriever(structured_store=structured_store, vector_store=vector_store)
    filters = {"classification": "romance_scam"}
    response = retriever.query(filters=filters, structured_top_k=7)
    results = response["results"]

    assert len(results) == 1
    entry = results[0]
    assert entry["sources"] == ["structured"]
    assert entry["record"]["classification"] == "romance_scam"
    structured_store.search_by_field.assert_called_once_with("classification", "romance_scam", top_k=7)
    vector_store.query_similar.assert_not_called()
    assert response["vector_hits"] == 0
    assert response["structured_hits"] == 1
    assert response["total"] == 1


def test_combines_structured_and_vector_hits():
    record = make_record(case_id="case-3", classification="phishing")
    structured_store = MagicMock()
    structured_store.search_by_field.return_value = [record]

    vector_store = MagicMock()
    vector_store.query_similar.return_value = [{"case_id": "case-3", "score": 0.82, "text": "login account suspended"}]

    retriever = HybridRetriever(structured_store=structured_store, vector_store=vector_store)
    response = retriever.query(
        text="account suspended",
        filters={"classification": "phishing"},
        vector_top_k=4,
        structured_top_k=6,
    )

    results = response["results"]
    assert len(results) == 1
    entry = results[0]
    assert entry["case_id"] == "case-3"
    assert entry["distance"] == pytest.approx(0.82)
    assert entry["score"] == pytest.approx(1.0 / (1.0 + 0.82))
    assert set(entry["sources"]) == {"structured", "vector"}
    assert entry["record"]["classification"] == "phishing"
    assert entry["vector"]["text"] == "login account suspended"
    assert entry["vector"]["distance"] == pytest.approx(0.82)
    vector_store.query_similar.assert_called_once_with("account suspended", top_k=4)
    structured_store.search_by_field.assert_called_once_with("classification", "phishing", top_k=6)
    assert response["vector_hits"] == 1
    assert response["structured_hits"] == 1
    assert response["total"] == 1


def test_pagination_slice_returns_expected_segment():
    structured_store = MagicMock()
    structured_store.search_by_field.return_value = []
    vector_store = MagicMock()
    vector_store.query_similar.return_value = [
        {"case_id": "case-1", "score": 0.95, "text": "A"},
        {"case_id": "case-2", "score": 0.85, "text": "B"},
        {"case_id": "case-3", "score": 0.75, "text": "C"},
    ]

    retriever = HybridRetriever(structured_store=structured_store, vector_store=vector_store)
    page = retriever.query(text="query", vector_top_k=3, offset=1, limit=1)

    assert len(page["results"]) == 1
    assert page["results"][0]["case_id"] == "case-2"
    assert page["results"][0]["distance"] == pytest.approx(0.85)
    assert page["total"] == 3
    assert page["vector_hits"] == 3
    assert page["structured_hits"] == 0


def test_text_fallback_when_vector_unavailable():
    record = make_record(case_id="case-text")
    structured_store = MagicMock()
    structured_store.search_by_field.return_value = []
    structured_store.search_text.return_value = [record]

    vector_store = MagicMock()
    vector_store.query_similar.side_effect = RuntimeError("vector backend down")

    retriever = HybridRetriever(structured_store=structured_store, vector_store=vector_store)
    response = retriever.query(text="wallet", vector_top_k=2)

    assert response["vector_hits"] == 0
    assert response["structured_hits"] == 1
    assert response["results"][0]["case_id"] == "case-text"
    assert response["results"][0]["sources"] == ["text"]
    vector_store.query_similar.assert_called_once_with("wallet", top_k=2)
    structured_store.search_text.assert_called_once_with("wallet", top_k=5)
