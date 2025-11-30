"""Unit tests for the ingestion retry store helper."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from i4g.store import sql as sql_schema
from i4g.store.ingestion_retry_store import IngestionRetryStore


def _build_store(tmp_path):
    db_path = tmp_path / "retry.db"
    engine = sa.create_engine(f"sqlite:///{db_path}", future=True)
    sql_schema.METADATA.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    return IngestionRetryStore(session_factory=factory), engine


def test_enqueue_updates_existing_and_fetch_ready(tmp_path):
    store, engine = _build_store(tmp_path)
    try:
        retry_id = store.enqueue(case_id="case-1", backend="firestore", payload={"case_id": "case-1"})
        assert retry_id

        ready = store.fetch_ready(limit=10)
        assert len(ready) == 1
        assert ready[0].case_id == "case-1"
        assert ready[0].backend == "firestore"

        updated = store.enqueue(case_id="case-1", backend="firestore", payload={"case_id": "case-1", "n": 2})
        assert updated == retry_id

        ready = store.fetch_ready(limit=10)
        assert ready[0].payload["n"] == 2
    finally:
        engine.dispose()


def test_schedule_retry_increments_attempt(tmp_path):
    store, engine = _build_store(tmp_path)
    try:
        retry_id = store.enqueue(case_id="case-2", backend="vertex", payload={})
        count = store.schedule_retry(retry_id, delay_seconds=30)
        assert count == 1

        ready = store.fetch_ready(limit=10)
        assert ready == []  # next_attempt moved into the future
    finally:
        engine.dispose()
