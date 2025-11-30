"""Unit tests for the HybridSearchService orchestration layer."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from i4g.services.hybrid_search import HybridSearchQuery, HybridSearchService, QueryEntityFilter, QueryTimeRange
from i4g.settings import reload_settings


class _StubRetriever:
    """Test double that captures query arguments."""

    def __init__(self, payload: dict[str, object]):
        self.payload = payload
        self.last_filters = None

    def query(self, **kwargs):  # type: ignore[override]
        self.last_filters = kwargs.get("filters")
        return self.payload


class _SpyObservability:
    """Captures observability interactions for assertions."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []
        self.counters: list[tuple[str, float, dict[str, str] | None]] = []
        self.timings: list[tuple[str, float, dict[str, str] | None]] = []

    def emit_event(self, event: str, **fields: object) -> None:
        self.events.append((event, dict(fields)))

    def increment(self, metric: str, *, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
        self.counters.append((metric, value, tags))

    def record_timing(self, metric: str, value_ms: float, *, tags: dict[str, str] | None = None) -> None:
        self.timings.append((metric, value_ms, tags))


@pytest.fixture(name="retriever_payload")
def _retriever_payload() -> dict[str, object]:
    return {
        "results": [
            {
                "case_id": "case-001",
                "sources": ["vector", "structured"],
                "vector": {"similarity": 0.9},
                "record": {
                    "case_id": "case-001",
                    "confidence": 0.8,
                    "created_at": datetime.utcnow().isoformat(),
                    "classification": "romance",
                    "metadata": {"dataset": "retrieval_poc_dev"},
                },
            },
            {
                "case_id": "case-002",
                "sources": ["structured"],
                "record": {
                    "case_id": "case-002",
                    "confidence": 0.6,
                    "created_at": (datetime.utcnow() - timedelta(days=10)).isoformat(),
                    "classification": "pig_butcher",
                    "metadata": {},
                },
            },
        ],
        "vector_hits": 1,
        "structured_hits": 2,
        "total": 2,
    }


def test_search_merges_scores_and_applies_time_range(retriever_payload):
    retriever = _StubRetriever(retriever_payload)
    start = datetime.utcnow() - timedelta(days=1)
    end = datetime.utcnow() + timedelta(days=1)
    query = HybridSearchQuery(
        text="romance scam",
        time_range=QueryTimeRange(start=start, end=end),
        limit=5,
    )
    service = HybridSearchService(retriever=retriever)

    response = service.search(query)

    assert response["count"] == 1  # second record filtered out by time window
    item = response["results"][0]
    assert item["case_id"] == "case-001"
    assert item["merged_score"] is not None
    assert item["scores"]["winner"] == "semantic"
    semantic_weighted = item["scores"]["semantic_weighted"]
    structured_weighted = item["scores"].get("structured_weighted", 0)
    assert semantic_weighted > structured_weighted
    assert response["vector_hits"] == 1
    assert response["structured_hits"] == 2
    diagnostics = response.get("diagnostics")
    assert diagnostics["score_policy"]["strategy"] == "max_weighted"
    assert diagnostics["counts"]["returned_results"] == 1


def test_entity_filters_pass_through_to_retriever(retriever_payload):
    retriever = _StubRetriever(retriever_payload)
    query = HybridSearchQuery(
        entities=[QueryEntityFilter(type="bank_account", value="123", match_mode="exact")],
        classifications=["romance"],
        datasets=["retrieval_poc_dev"],
        loss_buckets=[">50k"],
        case_ids=["case-xyz"],
    )
    service = HybridSearchService(retriever=retriever)

    service.search(query)

    assert retriever.last_filters == [
        ("classification", "romance"),
        ("dataset", "retrieval_poc_dev"),
        ("case_id", "case-xyz"),
        (
            "bank_account",
            {
                "filter_type": "entity",
                "entity_type": "bank_account",
                "value": "123",
                "match_mode": "exact",
                "datasets": ["retrieval_poc_dev"],
                "loss_buckets": [">50k"],
            },
        ),
    ]


def test_search_emits_observability_signals(retriever_payload):
    retriever = _StubRetriever(retriever_payload)
    spy = _SpyObservability()
    query = HybridSearchQuery(text="romance scam", limit=5)
    service = HybridSearchService(retriever=retriever, observability=spy)

    service.search(query)

    counter_names = {entry[0] for entry in spy.counters}
    assert "hybrid_search.query.total" in counter_names
    assert any(metric == "hybrid_search.query.duration_ms" for metric, _, _ in spy.timings)
    assert spy.events and spy.events[-1][0] == "hybrid_search.query"


def test_schema_reflects_search_settings_and_caches():
    settings = reload_settings()
    custom_search = settings.search.model_copy(
        update={
            "indicator_types": ["ip_address"],
            "dataset_presets": ["retrieval_poc_dev"],
            "classification_presets": ["romance"],
            "loss_buckets": [">50k"],
            "time_presets": ["30d"],
            "schema_cache_ttl_seconds": 60,
        }
    )
    settings = settings.model_copy(update={"search": custom_search})
    retriever = _StubRetriever({"results": [], "vector_hits": 0, "structured_hits": 0, "total": 0})
    service = HybridSearchService(retriever=retriever, settings=settings)

    schema = service.schema()
    assert schema == {
        "indicator_types": ["ip_address"],
        "datasets": ["retrieval_poc_dev"],
        "classifications": ["romance"],
        "loss_buckets": [">50k"],
        "time_presets": ["30d"],
    }
    # Access again to ensure cache path is exercised (no assertion, but should not raise)
    assert service.schema() == schema
