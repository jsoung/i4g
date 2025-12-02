"""Tests for the ingestion run tracker helper."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from i4g.store import sql as sql_schema
from i4g.store.ingestion_run_tracker import IngestionRunTracker
from i4g.store.sql_writer import SqlWriterResult


def test_tracker_start_record_complete(tmp_path):
    db_path = tmp_path / "runs.db"
    engine = sa.create_engine(f"sqlite:///{db_path}", future=True)
    sql_schema.METADATA.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)

    tracker = IngestionRunTracker(session_factory=factory)

    run_id = tracker.start_run(dataset="account_list", source_bundle="bundle.jsonl", vector_enabled=False)
    assert run_id

    sql_result = SqlWriterResult(case_id="case-1", document_ids=["doc-1"], entity_ids=["ent-1"], indicator_ids=[])
    tracker.record_case(run_id, sql_result)

    tracker.complete_run(run_id, status="succeeded")

    with engine.connect() as conn:
        row = conn.execute(
            sa.select(sql_schema.ingestion_runs).where(sql_schema.ingestion_runs.c.run_id == run_id)
        ).one()
        assert row.status == "succeeded"
        assert row.case_count == 1
        assert row.entity_count == 1
        assert row.indicator_count == 0
        assert row.sql_writes == 1
        assert row.completed_at is not None

    engine.dispose()
