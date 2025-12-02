"""Unified ingestion pipeline for structured + vector + SQL dual writes."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from i4g.services.factories import (
    build_firestore_writer,
    build_sql_writer,
    build_structured_store,
    build_vector_store,
    build_vertex_writer,
)
from i4g.settings import get_settings
from i4g.store.schema import ScamRecord
from i4g.store.sql_writer import (
    CaseBundle,
    CasePayload,
    EntityPayload,
    SourceDocumentPayload,
    SqlWriter,
    SqlWriterResult,
)

if TYPE_CHECKING:
    from i4g.services.firestore_writer import FirestoreWriter
    from i4g.services.vertex_writer import VertexDocumentWriter
    from i4g.store.structured import StructuredStore
    from i4g.store.vector import VectorStore


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestResult:
    """Structured output describing what the pipeline persisted."""

    case_id: str
    sql_result: SqlWriterResult | None = None
    vector_written: bool = False
    vertex_written: bool = False
    firestore_written: bool = False
    vertex_attempted: bool = False
    firestore_attempted: bool = False
    vertex_error: str | None = None
    firestore_error: str | None = None


@dataclass(slots=True)
class BackendWriteAttempt:
    """Represents the outcome of an optional backend write."""

    attempted: bool
    succeeded: bool
    error: str | None = None


def build_case_bundle(
    classification_result: Dict[str, Any],
    *,
    case_id: str,
    dataset: str,
    text: str,
) -> CaseBundle:
    """Construct a :class:`CaseBundle` from a classification payload."""

    metadata = classification_result.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    source_type = classification_result.get("source_type") or metadata.get("source_type") or "ingest_pipeline"

    case_metadata: Dict[str, Any] = {
        "explanation": classification_result.get("explanation"),
        "reasons": classification_result.get("reasons"),
    }
    if metadata:
        case_metadata["source_metadata"] = metadata
    case_payload = CasePayload(
        case_id=case_id,
        dataset=dataset,
        source_type=source_type,
        classification=classification_result.get("fraud_type", ""),
        confidence=float(classification_result.get("fraud_confidence", 0.0)),
        text=text,
        metadata={k: v for k, v in case_metadata.items() if v is not None},
    )

    document_alias = "primary"
    documents = [
        SourceDocumentPayload(
            alias=document_alias,
            document_id=classification_result.get("document_id"),
            title=classification_result.get("document_title"),
            source_url=classification_result.get("source_url") or metadata.get("source_url"),
            mime_type=classification_result.get("mime_type"),
            text=text,
            metadata={"case_id": case_id},
        )
    ]

    entities: List[EntityPayload] = []
    entity_map = classification_result.get("entities") or {}
    if isinstance(entity_map, dict):
        for entity_type, values in entity_map.items():
            if not isinstance(values, list):
                continue
            for index, raw_value in enumerate(values):
                canonical, confidence, original = _normalise_entity_value(raw_value)
                if not canonical:
                    continue
                entities.append(
                    EntityPayload(
                        alias=f"{entity_type}-{index}",
                        entity_type=entity_type,
                        canonical_value=canonical,
                        raw_value=original,
                        confidence=confidence,
                    )
                )

    return CaseBundle(case=case_payload, documents=documents, entities=entities)


def _normalise_entity_value(raw_value: Any) -> tuple[str | None, float, str | None]:
    if isinstance(raw_value, dict):
        canonical = raw_value.get("value") or raw_value.get("canonical")
        confidence = float(raw_value.get("confidence", 0.0) or 0.0)
        raw = raw_value.get("raw") or canonical
        return canonical, confidence, raw
    if isinstance(raw_value, str):
        return raw_value, 0.0, raw_value
    return None, 0.0, None


class IngestPipeline:
    """Unified ingestion pipeline from classification output to storage."""

    def __init__(
        self,
        structured_store: Optional["StructuredStore"] = None,
        vector_store: Optional["VectorStore"] = None,
        *,
        sql_writer: Optional[SqlWriter] = None,
        enable_vector: bool = True,
        enable_sql: Optional[bool] = None,
        enable_vertex: Optional[bool] = None,
        enable_firestore: Optional[bool] = None,
        default_dataset: Optional[str] = None,
        vertex_writer: Optional["VertexDocumentWriter"] = None,
        firestore_writer: Optional["FirestoreWriter"] = None,
    ) -> None:
        """Initialize pipeline with store instances.

        Args:
            structured_store: Optional pre-initialized StructuredStore.
            vector_store: Optional pre-initialized VectorStore.
            sql_writer: Optional SqlWriter instance for dual-write tables.
            enable_vector: When False, skip vector store initialisation and writes.
            enable_sql: Explicit toggle for SQL dual writes (defaults to settings).
            default_dataset: Dataset name recorded when payload omits one.
        """
        settings = get_settings()
        ingestion_settings = settings.ingestion

        self.structured_store = structured_store or build_structured_store()

        self.vector_store: Optional["VectorStore"]
        self._vector_enabled = enable_vector
        self._default_dataset = default_dataset or ingestion_settings.default_dataset
        self._sql_enabled = enable_sql if enable_sql is not None else ingestion_settings.enable_sql
        self._vertex_enabled = enable_vertex if enable_vertex is not None else ingestion_settings.enable_vertex
        self._firestore_enabled = (
            enable_firestore if enable_firestore is not None else ingestion_settings.enable_firestore
        )
        self.sql_writer: Optional[SqlWriter]
        self.vertex_writer: Optional["VertexDocumentWriter"] = None
        self.firestore_writer: Optional["FirestoreWriter"] = None

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

        if self._sql_enabled:
            if sql_writer is not None:
                self.sql_writer = sql_writer
            else:
                try:
                    self.sql_writer = build_sql_writer()
                except Exception:  # pragma: no cover - SQL backend issues should not block ingestion
                    LOGGER.exception("SQL writer initialisation failed; continuing without dual-write")
                    self.sql_writer = None
                    self._sql_enabled = False
        else:
            self.sql_writer = None

        if self._vertex_enabled:
            if vertex_writer is not None:
                self.vertex_writer = vertex_writer
            else:
                try:
                    self.vertex_writer = build_vertex_writer()
                except Exception:  # pragma: no cover - optional backend wiring
                    LOGGER.exception("Vertex writer initialisation failed; continuing without Vertex fan-out")
                    self.vertex_writer = None
                    self._vertex_enabled = False

        if self._firestore_enabled:
            if firestore_writer is not None:
                self.firestore_writer = firestore_writer
            else:
                try:
                    self.firestore_writer = build_firestore_writer()
                except Exception:  # pragma: no cover - optional backend wiring
                    LOGGER.exception("Firestore writer initialisation failed; continuing without Firestore fan-out")
                    self.firestore_writer = None
                    self._firestore_enabled = False

    def ingest_classified_case(
        self,
        classification_result: Dict[str, Any],
        *,
        ingestion_run_id: str | None = None,
    ) -> IngestResult:
        """Convert classification output into a ScamRecord and persist it.

        Args:
            classification_result: Dictionary from classifier output.
                Expected keys:
                    - fraud_type
                    - fraud_confidence
                    - entities
                    - explanation (optional)
                    - reasons (optional)

        Keyword Args:
            ingestion_run_id: When provided, stored alongside SQL dual-write rows.

        Returns:
            :class:`IngestResult` describing all persistence side-effects.
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

        need_case_bundle = (self._sql_enabled and self.sql_writer is not None) or (
            self._firestore_enabled and self.firestore_writer is not None
        )
        bundle: CaseBundle | None = None
        if need_case_bundle:
            text = classification_result.get("text") or record.text
            if not text:
                LOGGER.debug("Skipping SQL/Firestore fan-out for case_id=%s due to empty text", record.case_id)
            else:
                dataset = self._resolve_dataset(classification_result)
                try:
                    bundle = build_case_bundle(
                        classification_result,
                        case_id=record.case_id,
                        dataset=dataset,
                        text=text,
                    )
                except ValueError:
                    LOGGER.warning("Case bundle missing required fields for case_id=%s", record.case_id)

        sql_result = self._write_sql_case(bundle, ingestion_run_id)
        firestore_attempt = self._write_firestore_case(bundle, sql_result, ingestion_run_id)

        # 2️⃣ Vector storage
        vector_written = False
        if self._vector_enabled and self.vector_store is not None:
            try:
                self.vector_store.add_records([record])
                vector_written = True
            except Exception:  # pragma: no cover - embedding backend failures shouldn't abort ingestion
                LOGGER.exception("Vector store write failed for case_id=%s", case_id)
        vertex_attempt = self._write_vertex_document(classification_result)

        return IngestResult(
            case_id=case_id,
            sql_result=sql_result,
            vector_written=vector_written,
            vertex_written=vertex_attempt.succeeded,
            firestore_written=firestore_attempt.succeeded,
            vertex_attempted=vertex_attempt.attempted,
            firestore_attempted=firestore_attempt.attempted,
            vertex_error=vertex_attempt.error,
            firestore_error=firestore_attempt.error,
        )

    def query_similar_cases(self, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for semantically similar scam cases."""
        if self.vector_store is None:
            raise RuntimeError("Vector store disabled for this pipeline instance")
        return self.vector_store.query_similar(text, top_k=top_k)

    def _write_sql_case(
        self,
        bundle: CaseBundle | None,
        ingestion_run_id: str | None,
    ) -> SqlWriterResult | None:
        if not self._sql_enabled or self.sql_writer is None or bundle is None:
            return None
        try:
            return self.sql_writer.persist_case_bundle(bundle, ingestion_run_id=ingestion_run_id)
        except Exception:  # pragma: no cover - SQL dual-write failures shouldn't abort ingestion
            LOGGER.exception("SQL writer failed for case_id=%s", bundle.case.case_id or "unknown")
            return None

    def _write_firestore_case(
        self,
        bundle: CaseBundle | None,
        sql_result: SqlWriterResult | None,
        ingestion_run_id: str | None,
    ) -> BackendWriteAttempt:
        if not self._firestore_enabled or self.firestore_writer is None:
            return BackendWriteAttempt(attempted=False, succeeded=False)
        if bundle is None or sql_result is None:
            return BackendWriteAttempt(attempted=False, succeeded=False)
        try:
            self.firestore_writer.persist_case_bundle(bundle, sql_result, ingestion_run_id=ingestion_run_id)
            return BackendWriteAttempt(attempted=True, succeeded=True)
        except Exception as exc:  # pragma: no cover - Firestore backend failures shouldn't abort ingestion
            LOGGER.exception("Firestore writer failed for case_id=%s", sql_result.case_id)
            return BackendWriteAttempt(attempted=True, succeeded=False, error=str(exc))

    def _write_vertex_document(self, classification_result: Dict[str, Any]) -> BackendWriteAttempt:
        if not self._vertex_enabled or self.vertex_writer is None:
            return BackendWriteAttempt(attempted=False, succeeded=False)

        payload = dict(classification_result)
        payload.setdefault("dataset", payload.get("dataset") or self._default_dataset)
        try:
            self.vertex_writer.upsert_record(payload)
            return BackendWriteAttempt(attempted=True, succeeded=True)
        except Exception as exc:  # pragma: no cover - Vertex failures shouldn't abort ingestion
            LOGGER.exception("Vertex writer failed for case_id=%s", classification_result.get("case_id"))
            return BackendWriteAttempt(attempted=True, succeeded=False, error=str(exc))

    def _resolve_dataset(self, classification_result: Dict[str, Any]) -> str:
        metadata = classification_result.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        return classification_result.get("dataset") or metadata.get("dataset") or self._default_dataset
