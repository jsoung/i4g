"""Hybrid retrieval utilities for combining structured and semantic search."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence, Tuple

from i4g.services.factories import build_entity_store, build_structured_store, build_vector_store
from i4g.store.schema import ScamRecord

LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from i4g.store.entity_store import EntityStore
    from i4g.store.structured import StructuredStore
    from i4g.store.vector import VectorStore


class HybridRetriever:
    """Aggregate results from the structured store and vector store."""

    def __init__(
        self,
        structured_store: Optional["StructuredStore"] = None,
        vector_store: Optional["VectorStore"] = None,
        entity_store: Optional["EntityStore"] = None,
        *,
        enable_vector: bool = True,
    ) -> None:
        """Initialize the retriever with optional backend overrides."""

        self.structured_store = structured_store or build_structured_store()
        self.entity_store = entity_store or build_entity_store()
        self._vector_error = False

        if vector_store is not None:
            self.vector_store = vector_store
            return

        if not enable_vector:
            self.vector_store = None
            self._vector_error = True
            LOGGER.info("Vector search disabled via configuration; using structured/text retrieval only")
            return

        try:
            self.vector_store = build_vector_store()
        except Exception as exc:  # pragma: no cover - defensive fallback
            LOGGER.warning("Vector store unavailable; falling back to structured-only search: %s", exc, exc_info=True)
            self.vector_store = None
            self._vector_error = True

    def query(
        self,
        text: Optional[str] = None,
        filters: Optional[Iterable[Tuple[str, Any]] | Dict[str, Any]] = None,
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
            fallback_top_k = max(vector_top_k, structured_top_k)
            if (self.vector_store is None or self._vector_error) and not vector_results:
                structured_hits_total += self._merge_text_fallback(
                    aggregated,
                    text,
                    top_k=fallback_top_k,
                )

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
        if not self.vector_store:
            return {}, 0

        try:
            vector_hits = self.vector_store.query_similar(text, top_k=top_k)
            self._vector_error = False
        except Exception as exc:  # pragma: no cover - depends on backend availability
            LOGGER.warning("Vector similarity search failed; falling back to text search: %s", exc, exc_info=True)
            self._vector_error = True
            return {}, 0
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
            if self._is_entity_filter(field, value):
                total += self._merge_entity_filter(aggregated, field, value, top_k)
                continue
            records = self.structured_store.search_by_field(field, value, top_k=top_k)
            total += len(records)
            for record in records:
                self._add_structured_record(aggregated, record)
        return total

    def _merge_text_fallback(
        self,
        aggregated: Dict[str, Dict[str, Any]],
        query: str,
        top_k: int,
    ) -> int:
        """Populate aggregated map using structured text search when vectors are unavailable."""

        limit = max(top_k, 1)
        records = self.structured_store.search_text(query, top_k=limit)
        for record in records:
            entry = aggregated.setdefault(
                record.case_id,
                {"case_id": record.case_id, "score": None, "sources": set()},
            )
            entry["sources"].add("text")
            entry["record"] = record.to_dict()
            entry["score"] = entry["score"] if entry["score"] is not None else 0.0
        return len(records)

    @staticmethod
    def _iter_filters(filters: Iterable[Tuple[str, Any]] | Dict[str, Any]) -> Iterable[Tuple[str, Any]]:
        """Normalize filters input to an iterable of ``(field, value)`` tuples."""
        if isinstance(filters, dict):
            return filters.items()
        return list(filters)

    @staticmethod
    def _is_entity_filter(field: str, value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        if value.get("filter_type") == "entity":
            return True
        expected_type = value.get("entity_type") or value.get("type")
        return bool(expected_type and str(expected_type).lower() == field.lower())

    def _merge_entity_filter(
        self,
        aggregated: Dict[str, Dict[str, Any]],
        field: str,
        value: Any,
        top_k: int,
    ) -> int:
        descriptor = self._normalize_entity_descriptor(field, value)
        if not descriptor:
            return 0
        if not self.entity_store:
            LOGGER.debug("Entity filters requested but EntityStore is unavailable")
            return 0

        matches = self.entity_store.search_cases_by_indicator(
            indicator_type=descriptor["entity_type"],
            value=descriptor["value"],
            match_mode=descriptor["match_mode"],
            datasets=descriptor.get("datasets"),
            loss_buckets=descriptor.get("loss_buckets"),
            limit=top_k,
        )
        hits = 0
        for match in matches:
            case_id = match.get("case_id")
            if not case_id:
                continue
            record = self.structured_store.get_by_id(case_id)
            if not record:
                continue
            self._add_structured_record(aggregated, record)
            hits += 1
        return hits

    @staticmethod
    def _normalize_entity_descriptor(field: str, payload: Any) -> Dict[str, Any] | None:
        if isinstance(payload, dict):
            entity_value = payload.get("value")
            entity_type = payload.get("entity_type") or payload.get("type") or field
            match_mode = payload.get("match_mode", "exact")
            datasets = HybridRetriever._normalize_string_sequence(payload.get("datasets"))
            loss_buckets = HybridRetriever._normalize_string_sequence(payload.get("loss_buckets"))
        else:
            entity_value = payload
            entity_type = field
            match_mode = "exact"
            datasets = None
            loss_buckets = None

        if not entity_type or entity_value in (None, ""):
            return None

        return {
            "entity_type": str(entity_type),
            "value": str(entity_value),
            "match_mode": match_mode,
            "datasets": datasets,
            "loss_buckets": loss_buckets,
        }

    @staticmethod
    def _normalize_string_sequence(value: Any) -> List[str] | None:
        if not value:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else None
        if isinstance(value, Sequence):
            entries = [str(item).strip() for item in value if item not in (None, "")]
            return entries or None
        return None

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
