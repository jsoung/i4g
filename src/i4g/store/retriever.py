"""Hybrid retrieval utilities for combining structured and semantic search."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

from i4g.services.factories import build_structured_store, build_vector_store
from i4g.store.schema import ScamRecord

if TYPE_CHECKING:
    from i4g.store.structured import StructuredStore
    from i4g.store.vector import VectorStore


class HybridRetriever:
    """Aggregate results from the structured store and vector store."""

    def __init__(
        self,
        structured_store: Optional["StructuredStore"] = None,
        vector_store: Optional["VectorStore"] = None,
    ) -> None:
        """Initialize the retriever with optional backend overrides."""

        self.structured_store = structured_store or build_structured_store()
        self.vector_store = vector_store or build_vector_store()

    def query(
        self,
        text: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        vector_top_k: int = 5,
        structured_top_k: int = 5,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Query semantic and structured stores and merge results.

        Args:
            text: Optional free-text query for semantic similarity search.
            filters: Optional dictionary of field → value filters for structured lookup.
            vector_top_k: Number of top semantic results to retrieve.
            structured_top_k: Number of structured matches to retrieve per filter.
            offset: Starting offset for the merged results list.
            limit: Optional maximum number of results to return.

        Returns:
            Dictionary containing merged results and hit counters for each backend.
        """
        aggregated: Dict[str, Dict[str, Any]] = {}
        vector_hits_total = 0
        structured_hits_total = 0

        if text:
            vector_results, vector_hits_total = self._semantic_results(text, vector_top_k)
            aggregated.update(vector_results)

        if filters:
            structured_hits_total += self._merge_structured_filters(aggregated, filters, structured_top_k)

        results = list(aggregated.values())
        for item in results:
            if isinstance(item.get("sources"), set):
                item["sources"] = sorted(item["sources"])
        results.sort(
            key=lambda item: (
                item["score"] is not None,
                item["score"] or 0.0,
            ),
            reverse=True,
        )

        total_before_slice = len(results)
        if offset:
            results = results[offset:]
        if limit is not None:
            results = results[:limit]

        return {
            "results": results,
            "total": total_before_slice,
            "vector_hits": vector_hits_total,
            "structured_hits": structured_hits_total,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _semantic_results(self, text: str, top_k: int) -> Tuple[Dict[str, Dict[str, Any]], int]:
        """Run semantic vector search and normalize results."""
        vector_hits = self.vector_store.query_similar(text, top_k=top_k)
        aggregated: Dict[str, Dict[str, Any]] = {}

        for idx, hit in enumerate(vector_hits):
            case_id = hit.get("case_id") or f"vector_{idx}"
            entry = aggregated.setdefault(
                case_id,
                {"case_id": case_id, "score": None, "sources": set()},
            )
            entry["sources"].add("vector")
            entry["vector"] = hit

            score = hit.get("score")
            if score is not None:
                try:
                    distance = float(score)
                except (TypeError, ValueError):
                    distance = None
                if distance is not None:
                    similarity = 1.0 / (1.0 + distance)
                    hit["distance"] = distance
                    hit.setdefault("similarity", similarity)
                    current = entry.get("score")
                    entry["score"] = (
                        max(float(similarity), float(current)) if current is not None else float(similarity)
                    )
                    existing_distance = entry.get("distance")
                    if existing_distance is None or distance < existing_distance:
                        entry["distance"] = distance

        return aggregated, len(vector_hits)

    def _merge_structured_filters(
        self,
        aggregated: Dict[str, Dict[str, Any]],
        filters: Dict[str, Any],
        top_k: int,
    ) -> int:
        """Merge structured results into the aggregated map."""
        total = 0
        for field, value in self._iter_filters(filters):
            records = self.structured_store.search_by_field(field, value, top_k=top_k)
            total += len(records)
            for record in records:
                self._add_structured_record(aggregated, record)
        return total

    @staticmethod
    def _iter_filters(filters: Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
        """Normalize filters input to an iterable of (field, value)."""
        if isinstance(filters, dict):
            return filters.items()
        # Fall back to treating filters as iterable of tuples
        return list(filters)

    @staticmethod
    def _add_structured_record(aggregated: Dict[str, Dict[str, Any]], record: ScamRecord) -> None:
        """Insert a structured record into the aggregated map."""
        entry = aggregated.setdefault(
            record.case_id,
            {"case_id": record.case_id, "score": None, "sources": set()},
        )
        entry["sources"].add("structured")
        entry["record"] = record.to_dict()

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single case by ID from the structured store."""
        record = self.structured_store.get_by_id(case_id)
        return record.to_dict() if record else None
