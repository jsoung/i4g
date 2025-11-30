"""Helper that persists ingestion payloads into the dual-write SQL schema."""

from __future__ import annotations

import hashlib
import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterator, List, Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from i4g.store import sql as sql_schema
from i4g.store.sql import session_factory as default_session_factory

LOGGER = logging.getLogger(__name__)


def _generate_uuid(value: str | None = None) -> str:
    """Return a UUID suitable for primary keys.

    Args:
        value: Pre-existing identifier to reuse when present.

    Returns:
        A UUID formatted string.
    """

    return value or str(uuid.uuid4())


def _hash_text(text: str | None) -> str:
    """Compute the SHA-256 digest for the provided text.

    Args:
        text: Text to hash.

    Returns:
        Hex digest string.

    Raises:
        ValueError: If ``text`` is missing.
    """

    if not text:
        raise ValueError("Case payload must include non-empty text or raw_text_sha256")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _quantize_decimal(value: float | Decimal | None, places: str = "0.0001") -> Decimal:
    """Convert ``value`` into a Decimal with the requested precision.

    Args:
        value: Numeric input to coerce.
        places: Decimal quantization granularity.

    Returns:
        ``Decimal`` rounded to the requested precision.
    """

    if value is None:
        value = 0.0
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    return decimal_value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _utcnow() -> datetime:
    """Return a UTC timestamp.

    Returns:
        ``datetime`` instance representing utcnow.
    """

    return datetime.utcnow()


@dataclass(slots=True)
class CasePayload:
    """Canonical representation of a case row."""

    dataset: str
    source_type: str
    classification: str
    confidence: float
    text: str | None = None
    case_id: str | None = None
    raw_text_sha256: str | None = None
    detected_at: datetime | None = None
    reported_at: datetime | None = None
    status: str = "open"
    metadata: Dict[str, Any] | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None


@dataclass(slots=True)
class SourceDocumentPayload:
    """Source document (and chunk) persisted alongside the case."""

    alias: str | None = None
    document_id: str | None = None
    title: str | None = None
    source_url: str | None = None
    mime_type: str | None = None
    text: str | None = None
    text_sha256: str | None = None
    excerpt: str | None = None
    chunk_index: int = 0
    chunk_count: int = 1
    score: float | None = None
    captured_at: datetime | None = None
    metadata: Dict[str, Any] | None = None


@dataclass(slots=True)
class EntityMentionPayload:
    """Reference pointing from an entity to a supporting document."""

    document_id: str | None = None
    document_alias: str | None = None
    span_start: int | None = None
    span_end: int | None = None
    sentence: str | None = None
    metadata: Dict[str, Any] | None = None


@dataclass(slots=True)
class EntityPayload:
    """Entity extracted from the case text."""

    entity_type: str
    canonical_value: str
    confidence: float
    alias: str | None = None
    entity_id: str | None = None
    raw_value: str | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    metadata: Dict[str, Any] | None = None
    mentions: List[EntityMentionPayload] = field(default_factory=list)


@dataclass(slots=True)
class IndicatorSourcePayload:
    """Document/entity evidence for an indicator."""

    document_id: str | None = None
    document_alias: str | None = None
    entity_id: str | None = None
    entity_alias: str | None = None
    evidence_score: float | None = None
    explanation: str | None = None
    metadata: Dict[str, Any] | None = None


@dataclass(slots=True)
class IndicatorPayload:
    """Structured indicator tied to the ingested case."""

    category: str
    type: str
    number: str
    dataset: str | None = None
    item: str | None = None
    indicator_id: str | None = None
    status: str = "active"
    confidence: float = 0.0
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    metadata: Dict[str, Any] | None = None
    sources: List[IndicatorSourcePayload] = field(default_factory=list)


@dataclass(slots=True)
class CaseBundle:
    """Complete payload passed into :class:`SqlWriter`."""

    case: CasePayload
    documents: List[SourceDocumentPayload] = field(default_factory=list)
    entities: List[EntityPayload] = field(default_factory=list)
    indicators: List[IndicatorPayload] = field(default_factory=list)


@dataclass(slots=True)
class SqlWriterResult:
    """Return value emitted after persisting a bundle."""

    case_id: str
    document_ids: List[str]
    entity_ids: List[str]
    indicator_ids: List[str]


class SqlWriter:
    """Persist structured ingestion payloads into the SQL tables."""

    def __init__(self, *, session_factory: sessionmaker | None = None) -> None:
        self._session_factory = session_factory or default_session_factory()

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def persist_case_bundle(self, bundle: CaseBundle, *, ingestion_run_id: str | None = None) -> SqlWriterResult:
        """Persist the provided case bundle transactionally.

        Args:
            bundle: Case plus child artifacts to upsert.
            ingestion_run_id: Optional ingestion run foreign key.

        Returns:
            :class:`SqlWriterResult` summarizing written identifiers.
        """

        case_payload = bundle.case
        case_id = _generate_uuid(case_payload.case_id)
        raw_text_hash = case_payload.raw_text_sha256 or _hash_text(case_payload.text)
        now = _utcnow()

        with self._session_scope() as session:
            self._upsert_case(session, case_id, case_payload, raw_text_hash, ingestion_run_id, now)
            doc_ids, doc_alias_map = self._persist_documents(session, case_id, bundle.documents, now)
            entity_ids, entity_alias_map = self._persist_entities(session, case_id, bundle.entities, doc_alias_map, now)
            indicator_ids = self._persist_indicators(
                session,
                case_id,
                bundle.indicators,
                doc_alias_map,
                entity_alias_map,
                case_payload.dataset,
                now,
            )

        return SqlWriterResult(case_id=case_id, document_ids=doc_ids, entity_ids=entity_ids, indicator_ids=indicator_ids)

    def _upsert_case(
        self,
        session: Session,
        case_id: str,
        payload: CasePayload,
        raw_hash: str,
        ingestion_run_id: str | None,
        timestamp: datetime,
    ) -> None:
        values = {
            "ingestion_run_id": ingestion_run_id,
            "dataset": payload.dataset,
            "source_type": payload.source_type,
            "classification": payload.classification,
            "confidence": _quantize_decimal(payload.confidence),
            "detected_at": payload.detected_at,
            "reported_at": payload.reported_at,
            "raw_text_sha256": raw_hash,
            "status": payload.status,
            "metadata": payload.metadata,
            "is_deleted": payload.is_deleted,
            "deleted_at": payload.deleted_at,
            "updated_at": timestamp,
        }
        result = session.execute(
            sa.update(sql_schema.cases).where(sql_schema.cases.c.case_id == case_id).values(**values)
        )
        if result.rowcount == 0:
            insert_values = {"case_id": case_id, **values, "created_at": timestamp}
            session.execute(sa.insert(sql_schema.cases).values(**insert_values))

    def _persist_documents(
        self,
        session: Session,
        case_id: str,
        documents: Sequence[SourceDocumentPayload],
        timestamp: datetime,
    ) -> tuple[List[str], Dict[str, str]]:
        ids: List[str] = []
        alias_map: Dict[str, str] = {}
        for doc in documents:
            document_id = _generate_uuid(doc.document_id)
            ids.append(document_id)
            if doc.alias:
                alias_map[doc.alias] = document_id
            text_hash = doc.text_sha256 or (
                hashlib.sha256(doc.text.encode("utf-8")).hexdigest() if doc.text else None
            )
            values = {
                "document_id": document_id,
                "case_id": case_id,
                "title": doc.title,
                "source_url": doc.source_url,
                "mime_type": doc.mime_type,
                "text": doc.text,
                "text_sha256": text_hash,
                "excerpt": doc.excerpt,
                "chunk_index": doc.chunk_index,
                "chunk_count": doc.chunk_count,
                "score": _quantize_decimal(doc.score, "0.001") if doc.score is not None else None,
                "captured_at": doc.captured_at,
                "metadata": doc.metadata,
                "updated_at": timestamp,
            }
            result = session.execute(
                sa.update(sql_schema.source_documents)
                .where(sql_schema.source_documents.c.document_id == document_id)
                .values(**values)
            )
            if result.rowcount == 0:
                insert_values = {**values, "created_at": timestamp}
                session.execute(sa.insert(sql_schema.source_documents).values(**insert_values))
        return ids, alias_map

    def _persist_entities(
        self,
        session: Session,
        case_id: str,
        entities: Sequence[EntityPayload],
        doc_alias_map: Dict[str, str],
        timestamp: datetime,
    ) -> tuple[List[str], Dict[str, str]]:
        ids: List[str] = []
        alias_map: Dict[str, str] = {}
        for entity in entities:
            entity_id = entity.entity_id or self._lookup_entity_id(session, case_id, entity) or _generate_uuid(None)
            ids.append(entity_id)
            if entity.alias:
                alias_map[entity.alias] = entity_id
            values = {
                "entity_id": entity_id,
                "case_id": case_id,
                "entity_type": entity.entity_type,
                "canonical_value": entity.canonical_value,
                "raw_value": entity.raw_value,
                "confidence": _quantize_decimal(entity.confidence),
                "first_seen_at": entity.first_seen_at,
                "last_seen_at": entity.last_seen_at,
                "metadata": entity.metadata,
                "updated_at": timestamp,
            }
            result = session.execute(
                sa.update(sql_schema.entities).where(sql_schema.entities.c.entity_id == entity_id).values(**values)
            )
            if result.rowcount == 0:
                insert_values = {**values, "created_at": timestamp}
                session.execute(sa.insert(sql_schema.entities).values(**insert_values))
            self._replace_entity_mentions(session, entity_id, entity.mentions, doc_alias_map, timestamp)
        return ids, alias_map

    def _lookup_entity_id(self, session: Session, case_id: str, entity: EntityPayload) -> str | None:
        stmt = sa.select(sql_schema.entities.c.entity_id).where(
            sql_schema.entities.c.case_id == case_id,
            sql_schema.entities.c.entity_type == entity.entity_type,
            sql_schema.entities.c.canonical_value == entity.canonical_value,
        )
        return session.execute(stmt).scalar_one_or_none()

    def _replace_entity_mentions(
        self,
        session: Session,
        entity_id: str,
        mentions: Sequence[EntityMentionPayload],
        doc_alias_map: Dict[str, str],
        timestamp: datetime,
    ) -> None:
        session.execute(
            sa.delete(sql_schema.entity_mentions).where(sql_schema.entity_mentions.c.entity_id == entity_id)
        )
        fallback_counter = -1
        for mention in mentions:
            document_id = self._resolve_document_id(mention.document_id, mention.document_alias, doc_alias_map)
            span_start = mention.span_start
            if span_start is None:
                span_start = fallback_counter
                fallback_counter -= 1
            values = {
                "entity_id": entity_id,
                "document_id": document_id,
                "span_start": span_start,
                "span_end": mention.span_end,
                "sentence": mention.sentence,
                "metadata": mention.metadata,
                "created_at": timestamp,
            }
            session.execute(sa.insert(sql_schema.entity_mentions).values(**values))

    def _persist_indicators(
        self,
        session: Session,
        case_id: str,
        indicators: Sequence[IndicatorPayload],
        doc_alias_map: Dict[str, str],
        entity_alias_map: Dict[str, str],
        default_dataset: str,
        timestamp: datetime,
    ) -> List[str]:
        ids: List[str] = []
        for indicator in indicators:
            dataset = indicator.dataset or default_dataset
            if not dataset:
                raise ValueError("Indicator dataset is required")
            indicator_id = indicator.indicator_id or self._lookup_indicator_id(session, dataset, indicator)
            if indicator_id is None:
                indicator_id = _generate_uuid(None)
            ids.append(indicator_id)
            values = {
                "indicator_id": indicator_id,
                "case_id": case_id,
                "category": indicator.category,
                "item": indicator.item,
                "type": indicator.type,
                "number": indicator.number,
                "status": indicator.status,
                "confidence": _quantize_decimal(indicator.confidence),
                "first_seen_at": indicator.first_seen_at,
                "last_seen_at": indicator.last_seen_at,
                "dataset": dataset,
                "metadata": indicator.metadata,
                "updated_at": timestamp,
            }
            result = session.execute(
                sa.update(sql_schema.indicators)
                .where(sql_schema.indicators.c.indicator_id == indicator_id)
                .values(**values)
            )
            if result.rowcount == 0:
                insert_values = {**values, "created_at": timestamp}
                session.execute(sa.insert(sql_schema.indicators).values(**insert_values))
            self._replace_indicator_sources(
                session,
                indicator_id,
                indicator.sources,
                doc_alias_map,
                entity_alias_map,
                timestamp,
            )
        return ids

    def _lookup_indicator_id(
        self,
        session: Session,
        dataset: str,
        indicator: IndicatorPayload,
    ) -> str | None:
        stmt = sa.select(sql_schema.indicators.c.indicator_id).where(
            sql_schema.indicators.c.dataset == dataset,
            sql_schema.indicators.c.category == indicator.category,
            sql_schema.indicators.c.number == indicator.number,
        )
        return session.execute(stmt).scalar_one_or_none()

    def _replace_indicator_sources(
        self,
        session: Session,
        indicator_id: str,
        sources: Sequence[IndicatorSourcePayload],
        doc_alias_map: Dict[str, str],
        entity_alias_map: Dict[str, str],
        timestamp: datetime,
    ) -> None:
        session.execute(
            sa.delete(sql_schema.indicator_sources).where(sql_schema.indicator_sources.c.indicator_id == indicator_id)
        )
        for source in sources:
            document_id = self._resolve_document_id(source.document_id, source.document_alias, doc_alias_map)
            entity_id = self._resolve_entity_id(source.entity_id, source.entity_alias, entity_alias_map)
            values = {
                "indicator_id": indicator_id,
                "document_id": document_id,
                "entity_id": entity_id,
                "evidence_score": None
                if source.evidence_score is None
                else _quantize_decimal(source.evidence_score),
                "explanation": source.explanation,
                "metadata": source.metadata,
                "created_at": timestamp,
            }
            session.execute(sa.insert(sql_schema.indicator_sources).values(**values))

    def _resolve_document_id(
        self,
        document_id: str | None,
        document_alias: str | None,
        doc_alias_map: Dict[str, str],
    ) -> str:
        resolved = document_id or (doc_alias_map.get(document_alias) if document_alias else None)
        if not resolved:
            raise ValueError("Indicator/entity reference missing document_id and document_alias")
        return resolved

    def _resolve_entity_id(
        self,
        entity_id: str | None,
        entity_alias: str | None,
        entity_alias_map: Dict[str, str],
    ) -> str | None:
        if entity_id:
            return entity_id
        if entity_alias:
            resolved = entity_alias_map.get(entity_alias)
            if not resolved:
                raise ValueError(f"Unknown entity alias '{entity_alias}'")
            return resolved
        return None


__all__ = [
    "CasePayload",
    "SourceDocumentPayload",
    "EntityMentionPayload",
    "EntityPayload",
    "IndicatorSourcePayload",
    "IndicatorPayload",
    "CaseBundle",
    "SqlWriter",
    "SqlWriterResult",
]
