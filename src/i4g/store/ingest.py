"""Unified ingestion pipeline for i4g.

Takes processed classification results (from M3) and persists them into:
1. StructuredStore (SQLite-backed metadata)
2. VectorStore (Chroma-based embeddings)

This ensures every scam case is both searchable by attributes and retrievable
semantically for related-case detection.
"""

from __future__ import annotations

import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

from i4g.store.schema import ScamRecord
from i4g.store.structured import StructuredStore
from i4g.store.vector import VectorStore


class IngestPipeline:
    """Unified ingestion pipeline from classification output to storage."""

    def __init__(
        self,
        structured_store: Optional[StructuredStore] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        """Initialize pipeline with store instances.

        Args:
            structured_store: Optional pre-initialized StructuredStore.
            vector_store: Optional pre-initialized VectorStore.
        """
        self.structured_store = structured_store or StructuredStore()
        self.vector_store = vector_store or VectorStore()

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
        self.vector_store.add_records([record])

        return case_id

    def query_similar_cases(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for semantically similar scam cases."""
        return self.vector_store.query_similar(text, top_k=top_k)
