"""Helpers to persist ingestion_run rows and update counters."""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Literal, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from i4g.store import sql as sql_schema
from i4g.store.sql import session_factory as default_session_factory
from i4g.store.sql_writer import SqlWriterResult

LOGGER = logging.getLogger(__name__)

RunStatus = Literal["running", "succeeded", "failed", "partial"]


def _utcnow() -> datetime:
    return datetime.utcnow()


class IngestionRunTracker:
    """Persist ingestion run metadata and counters in SQL."""

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

    def start_run(self, *, dataset: str, source_bundle: str | None, vector_enabled: bool) -> str:
        """Create an ingestion_runs row and return its identifier."""

        run_id = str(uuid.uuid4())
        timestamp = _utcnow()
        with self._session_scope() as session:
            session.execute(
                sa.insert(sql_schema.ingestion_runs).values(
                    run_id=run_id,
                    dataset=dataset,
                    source_bundle=source_bundle,
                    status="running",
                    vector_enabled=vector_enabled,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
            )
        LOGGER.info("Started ingestion run run_id=%s dataset=%s", run_id, dataset)
        return run_id

    def record_case(
        self,
        run_id: str,
        sql_result: SqlWriterResult | None,
        *,
        firestore_writes: int = 0,
        vertex_writes: int = 0,
    ) -> None:
        """Increment counters for a successfully processed case."""

        entity_count = len(sql_result.entity_ids) if sql_result else 0
        indicator_count = len(sql_result.indicator_ids) if sql_result else 0
        sql_writes = 1 if sql_result else 0
        timestamp = _utcnow()
        with self._session_scope() as session:
            session.execute(
                sa.update(sql_schema.ingestion_runs)
                .where(sql_schema.ingestion_runs.c.run_id == run_id)
                .values(
                    case_count=sql_schema.ingestion_runs.c.case_count + 1,
                    entity_count=sql_schema.ingestion_runs.c.entity_count + entity_count,
                    indicator_count=sql_schema.ingestion_runs.c.indicator_count + indicator_count,
                    sql_writes=sql_schema.ingestion_runs.c.sql_writes + sql_writes,
                    firestore_writes=sql_schema.ingestion_runs.c.firestore_writes + firestore_writes,
                    vertex_writes=sql_schema.ingestion_runs.c.vertex_writes + vertex_writes,
                    updated_at=timestamp,
                )
            )

    def complete_run(
        self,
        run_id: str,
        *,
        status: RunStatus,
        last_error: Optional[str] = None,
        retry_increment: int = 0,
    ) -> None:
        """Mark a run as completed with the supplied status."""

        timestamp = _utcnow()
        values = {
            "status": status,
            "last_error": last_error,
            "completed_at": timestamp,
            "updated_at": timestamp,
        }
        if retry_increment:
            values["retry_count"] = sql_schema.ingestion_runs.c.retry_count + retry_increment
        with self._session_scope() as session:
            session.execute(
                sa.update(sql_schema.ingestion_runs)
                .where(sql_schema.ingestion_runs.c.run_id == run_id)
                .values(**values)
            )
        LOGGER.info("Completed ingestion run run_id=%s status=%s", run_id, status)


__all__ = ["IngestionRunTracker", "RunStatus"]
