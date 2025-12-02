"""Adapters around :class:`HybridRetriever` for financial indicator searches."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from i4g.settings import get_settings
from i4g.store.retriever import HybridRetriever

from .models import SourceDocument
from .queries import IndicatorQuery

LOGGER = logging.getLogger(__name__)
_VECTOR_ENV_KEYS: Tuple[str, ...] = (
    "I4G_ACCOUNT_LIST__ENABLE_VECTOR",
    "ACCOUNT_LIST__ENABLE_VECTOR",
    "I4G_ACCOUNT_LIST_ENABLE_VECTOR",
    "ACCOUNT_LIST_ENABLE_VECTOR",
)


def _coerce_metadata(value: object) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            return {}
    return {}


def _to_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    return None


def _normalize_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _within_range(timestamp: datetime | None, start: datetime | None, end: datetime | None) -> bool:
    normalized_timestamp = _normalize_timestamp(timestamp)
    normalized_start = _normalize_timestamp(start)
    normalized_end = _normalize_timestamp(end)

    if normalized_timestamp is None:
        return True
    if normalized_start and normalized_timestamp < normalized_start:
        return False
    if normalized_end and normalized_timestamp > normalized_end:
        return False
    return True


def _vector_override_from_env() -> Optional[bool]:
    for key in _VECTOR_ENV_KEYS:
        raw = os.getenv(key)
        if raw is None:
            continue
        normalized = raw.strip().lower()
        if normalized in {"", "1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return None


class FinancialEntityRetriever:
    """Wraps :class:`HybridRetriever` with category-aware defaults."""

    def __init__(self, *, hybrid: HybridRetriever | None = None) -> None:
        self.settings = get_settings()
        if hybrid is not None:
            self.hybrid = hybrid
            return

        override = _vector_override_from_env()
        enable_vector = override if override is not None else self.settings.account_list.enable_vector
        if override is not None:
            LOGGER.info("Account list vector retrieval override via env; enable_vector=%s", enable_vector)
        self.hybrid = HybridRetriever(enable_vector=enable_vector)

    def fetch_documents(
        self,
        *,
        indicator_query: IndicatorQuery,
        top_k: int,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> List[SourceDocument]:
        """Fetch candidate documents for a particular indicator category."""

        response = self.hybrid.query(
            text=indicator_query.query,
            vector_top_k=top_k,
            structured_top_k=top_k,
        )
        documents: List[SourceDocument] = []
        for entry in response.get("results", []):
            record = entry.get("record") or {}
            vector_entry = entry.get("vector") or {}
            content = record.get("text") or record.get("summary") or vector_entry.get("text") or ""
            if not content:
                continue
            metadata = _coerce_metadata(record.get("metadata"))
            vector_metadata = _coerce_metadata(vector_entry.get("metadata"))
            combined_metadata = metadata or vector_metadata
            created_at = _to_datetime(
                record.get("created_at") or combined_metadata.get("created_at") or vector_entry.get("created_at")
            )
            if not _within_range(created_at, start_time, end_time):
                continue
            document = SourceDocument(
                case_id=(record.get("case_id") or vector_entry.get("case_id") or entry.get("case_id") or "unknown"),
                content=content,
                dataset=(
                    combined_metadata.get("dataset") or combined_metadata.get("source") or vector_entry.get("dataset")
                ),
                title=record.get("title") or combined_metadata.get("title"),
                classification=record.get("classification") or vector_entry.get("classification"),
                created_at=created_at,
                score=entry.get("score") or vector_entry.get("score"),
                excerpt=combined_metadata.get("excerpt"),
            )
            documents.append(document)
            if len(documents) >= indicator_query.max_documents:
                break
        return documents

    def fetch_bulk(
        self,
        *,
        queries: Iterable[IndicatorQuery],
        top_k: int,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> dict[str, List[SourceDocument]]:
        """Fetch documents for each indicator in ``queries``."""

        results: dict[str, List[SourceDocument]] = {}
        for query in queries:
            results[query.slug] = self.fetch_documents(
                indicator_query=query,
                top_k=top_k,
                start_time=start_time,
                end_time=end_time,
            )
        return results
