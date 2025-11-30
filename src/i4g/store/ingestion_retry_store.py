"""Persistence helpers for the ingestion retry queue."""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from i4g.store import sql as sql_schema
from i4g.store.sql import session_factory as default_session_factory

LOGGER = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class RetryItem:
    """Domain object describing a queued retry record."""

    retry_id: str
    case_id: str
    backend: str
    payload: Dict[str, Any]
    attempt_count: int
    next_attempt_at: datetime


class IngestionRetryStore:
    """CRUD helpers around the ``ingestion_retry_queue`` table."""

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

    def enqueue(
        self,
        *,
        case_id: str,
        backend: str,
        payload: Dict[str, Any],
        delay_seconds: int = 0,
    ) -> str:
        """Insert or update a retry entry for ``case_id``/``backend``."""

        timestamp = _utcnow()
        next_attempt = timestamp + timedelta(seconds=max(delay_seconds, 0))
        retry_id = str(uuid.uuid4())

        with self._session_scope() as session:
            existing = session.execute(
                sa.select(sql_schema.ingestion_retry_queue).where(
                    sql_schema.ingestion_retry_queue.c.case_id == case_id,
                    sql_schema.ingestion_retry_queue.c.backend == backend,
                )
            ).first()

            if existing:
                retry_id = existing.retry_id
                session.execute(
                    sa.update(sql_schema.ingestion_retry_queue)
                    .where(sql_schema.ingestion_retry_queue.c.retry_id == retry_id)
                    .values(
                        payload_json=payload,
                        next_attempt_at=next_attempt,
                        updated_at=timestamp,
                    )
                )
                LOGGER.info(
                    "Updated retry queue entry retry_id=%s backend=%s case_id=%s",
                    retry_id,
                    backend,
                    case_id,
                )
                return retry_id

            session.execute(
                sa.insert(sql_schema.ingestion_retry_queue).values(
                    retry_id=retry_id,
                    case_id=case_id,
                    backend=backend,
                    payload_json=payload,
                    attempt_count=0,
                    next_attempt_at=next_attempt,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
            LOGGER.info("Queued retry retry_id=%s backend=%s case_id=%s", retry_id, backend, case_id)
        return retry_id

    def fetch_ready(self, *, limit: int = 25) -> List[RetryItem]:
        """Return retry entries whose ``next_attempt_at`` has elapsed."""

        now = _utcnow()
        with self._session_scope() as session:
            rows = session.execute(
                sa.select(sql_schema.ingestion_retry_queue)
                .where(sql_schema.ingestion_retry_queue.c.next_attempt_at <= now)
                .order_by(sql_schema.ingestion_retry_queue.c.next_attempt_at.asc())
                .limit(limit)
            ).fetchall()

        items: List[RetryItem] = []
        for row in rows:
            items.append(
                RetryItem(
                    retry_id=row.retry_id,
                    case_id=row.case_id,
                    backend=row.backend,
                    payload=row.payload_json or {},
                    attempt_count=row.attempt_count,
                    next_attempt_at=row.next_attempt_at,
                )
            )
        return items

    def delete(self, retry_id: str) -> None:
        """Remove a retry entry after successful processing."""

        with self._session_scope() as session:
            session.execute(
                sa.delete(sql_schema.ingestion_retry_queue).where(
                    sql_schema.ingestion_retry_queue.c.retry_id == retry_id
                )
            )

    def schedule_retry(
        self,
        retry_id: str,
        *,
        delay_seconds: int,
    ) -> Optional[int]:
        """Increment ``attempt_count`` and push ``next_attempt_at`` into the future."""

        with self._session_scope() as session:
            row = session.execute(
                sa.select(sql_schema.ingestion_retry_queue.c.attempt_count).where(
                    sql_schema.ingestion_retry_queue.c.retry_id == retry_id
                )
            ).one_or_none()
            if row is None:
                return None
            next_count = row.attempt_count + 1
            timestamp = _utcnow()
            session.execute(
                sa.update(sql_schema.ingestion_retry_queue)
                .where(sql_schema.ingestion_retry_queue.c.retry_id == retry_id)
                .values(
                    attempt_count=next_count,
                    next_attempt_at=timestamp + timedelta(seconds=max(delay_seconds, 0)),
                    updated_at=timestamp,
                )
            )
            return next_count


__all__ = ["IngestionRetryStore", "RetryItem"]
