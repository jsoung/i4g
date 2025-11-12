"""Unified ingestion pipeline for i4g.

Takes processed classification results (from M3) and persists them into:
1. StructuredStore (SQLite-backed metadata)
2. VectorStore (Chroma-based embeddings)

This ensures every scam case is both searchable by attributes and retrievable
semantically for related-case detection.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from i4g.services.factories import build_structured_store, build_vector_store
from i4g.store.schema import ScamRecord

if TYPE_CHECKING:
    from i4g.store.structured import StructuredStore
    from i4g.store.vector import VectorStore


LOGGER = logging.getLogger(__name__)


class IngestPipeline:
    """Unified ingestion pipeline from classification output to storage."""

    def __init__(
        self,
        structured_store: Optional["StructuredStore"] = None,
        vector_store: Optional["VectorStore"] = None,
        *,
        enable_vector: bool = True,
    ) -> None:
        """Initialize pipeline with store instances.

        Args:
            structured_store: Optional pre-initialized StructuredStore.
            vector_store: Optional pre-initialized VectorStore.
            enable_vector: When False, skip vector store initialisation and writes.
        """
        self.structured_store = structured_store or build_structured_store()

        self.vector_store: Optional["VectorStore"]
        self._vector_enabled = enable_vector

        if vector_store is not None:
            self.vector_store = vector_store
        elif enable_vector:
            try:
                self.vector_store = build_vector_store()
            except Exception:  # pragma: no cover - defensive logging during init
                LOGGER.exception("Vector store initialisation failed; continuing without embeddings")
                self.vector_store = None
                self._vector_enabled = False
        else:
            self.vector_store = None

    def ingest_classified_case(self, classification_result: Dict[str, Any]) -> str:
        """Convert classification output into a ScamRecord and persist it.

        Args:
            classification_result: Dictionary from classifier output.
                Expected keys:
                    - fraud_type
                    - fraud_confidence
                    - entities
                    - explanation (optional)
                    - reasons (optional)

        Returns:
            case_id (string) of the ingested record.
        """
        case_id = classification_result.get("case_id") or str(uuid.uuid4())

        record = ScamRecord(
            case_id=case_id,
            text=classification_result.get("text", ""),
            entities={
                k: [v["value"] if isinstance(v, dict) else v for v in vs]
                for k, vs in classification_result.get("entities", {}).items()
                if isinstance(vs, list)
            },
            classification=classification_result.get("fraud_type", ""),
            confidence=float(classification_result.get("fraud_confidence", 0.0)),
            created_at=datetime.utcnow(),
            metadata={
                "explanation": classification_result.get("explanation"),
                "reasons": classification_result.get("reasons"),
            },
        )

        # 1️⃣ Structured storage
        self.structured_store.upsert_record(record)

        # 2️⃣ Vector storage
        if self._vector_enabled and self.vector_store is not None:
            try:
                self.vector_store.add_records([record])
            except Exception:  # pragma: no cover - embedding backend failures shouldn't abort ingestion
                LOGGER.exception("Vector store write failed for case_id=%s", case_id)

        return case_id

    def query_similar_cases(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for semantically similar scam cases."""
        if self.vector_store is None:
            raise RuntimeError("Vector store disabled for this pipeline instance")
        return self.vector_store.query_similar(text, top_k=top_k)
