"""End-to-end tests for IngestPipeline dual-write behaviour."""

from __future__ import annotations

import sqlalchemy as sa

from i4g.services.firestore_writer import FirestoreWriteResult
from i4g.services.ingest_payloads import prepare_ingest_payload
from i4g.settings.config import get_settings, reload_settings
from i4g.store import sql as sql_schema
from i4g.store.ingest import IngestPipeline
from i4g.store.structured import StructuredStore


def test_ingest_pipeline_persists_sql_bundle(tmp_path, monkeypatch):
    """Ensure the pipeline writes structured+SQL rows when dual-write is enabled."""

    db_path = tmp_path / "dual_write.db"
    monkeypatch.setenv("I4G_STORAGE__SQLITE_PATH", str(db_path))
    monkeypatch.setenv("I4G_INGESTION__ENABLE_SQL", "true")
    monkeypatch.setenv("I4G_INGESTION__DEFAULT_DATASET", "dual_demo")

    try:
        # Refresh settings so builders pick up the temporary database path.
        reload_settings(env="local")

        engine = sa.create_engine(f"sqlite:///{db_path}", future=True)
        sql_schema.METADATA.create_all(engine)
        engine.dispose()

        structured_store = StructuredStore(str(db_path))
        pipeline = IngestPipeline(
            structured_store=structured_store,
            vector_store=None,
            enable_vector=False,
            default_dataset="dual_demo",
        )

        classification_result = {
            "text": "TrustWallet verification fee",
            "fraud_type": "crypto_investment",
            "fraud_confidence": 0.91,
            "entities": {"organizations": [{"value": "TrustWallet"}]},
        }

        result = pipeline.ingest_classified_case(classification_result, ingestion_run_id="run-dual")
        assert result.sql_result is not None
        assert result.firestore_written is False
        case_id = result.case_id

        with sa.create_engine(f"sqlite:///{db_path}", future=True).connect() as conn:
            case_row = conn.execute(sa.select(sql_schema.cases).where(sql_schema.cases.c.case_id == case_id)).one()
            assert case_row.dataset == "dual_demo"
            assert case_row.ingestion_run_id == "run-dual"

            documents = conn.execute(
                sa.select(sql_schema.source_documents).where(sql_schema.source_documents.c.case_id == case_id)
            ).fetchall()
            assert len(documents) == 1

            entities = conn.execute(
                sa.select(sql_schema.entities).where(sql_schema.entities.c.case_id == case_id)
            ).fetchall()
            assert len(entities) == 1
    finally:
        get_settings.cache_clear()


class _DummyFirestoreWriter:
    def __init__(self) -> None:
        self.calls = 0
        self.last_args = None

    def persist_case_bundle(self, bundle, sql_result, *, ingestion_run_id=None):
        self.calls += 1
        self.last_args = (bundle, sql_result, ingestion_run_id)
        return FirestoreWriteResult(case_path=f"cases/{sql_result.case_id}")


def test_ingest_pipeline_writes_firestore_when_enabled(tmp_path, monkeypatch):
    db_path = tmp_path / "dual_write_firestore.db"
    monkeypatch.setenv("I4G_STORAGE__SQLITE_PATH", str(db_path))
    monkeypatch.setenv("I4G_INGESTION__ENABLE_SQL", "true")
    monkeypatch.setenv("I4G_INGESTION__DEFAULT_DATASET", "dual_demo")

    dummy_writer = _DummyFirestoreWriter()

    try:
        reload_settings(env="local")

        engine = sa.create_engine(f"sqlite:///{db_path}", future=True)
        sql_schema.METADATA.create_all(engine)
        engine.dispose()

        structured_store = StructuredStore(str(db_path))
        pipeline = IngestPipeline(
            structured_store=structured_store,
            vector_store=None,
            enable_vector=False,
            enable_firestore=True,
            firestore_writer=dummy_writer,
            default_dataset="dual_demo",
        )

        classification_result = {
            "text": "TrustWallet verification fee",
            "fraud_type": "crypto_investment",
            "fraud_confidence": 0.91,
            "entities": {"organizations": [{"value": "TrustWallet"}]},
        }

        result = pipeline.ingest_classified_case(classification_result, ingestion_run_id="run-firestore")
        assert result.firestore_written is True
        assert dummy_writer.calls == 1
        assert dummy_writer.last_args[2] == "run-firestore"
    finally:
        get_settings.cache_clear()


def test_ingest_pipeline_persists_network_entities(tmp_path, monkeypatch):
    db_path = tmp_path / "network_entities.db"
    monkeypatch.setenv("I4G_STORAGE__SQLITE_PATH", str(db_path))
    monkeypatch.setenv("I4G_INGESTION__ENABLE_SQL", "true")
    monkeypatch.setenv("I4G_INGESTION__DEFAULT_DATASET", "network_demo")

    try:
        reload_settings(env="local")

        engine = sa.create_engine(f"sqlite:///{db_path}", future=True)
        sql_schema.METADATA.create_all(engine)
        engine.dispose()

        structured_store = StructuredStore(str(db_path))
        pipeline = IngestPipeline(
            structured_store=structured_store,
            vector_store=None,
            enable_vector=False,
            default_dataset="network_demo",
        )

        record = {
            "text": "Session contained browser and ASN details",
            "fraud_type": "tech_support",
            "fraud_confidence": 0.88,
            "structured_fields": {
                "network": {
                    "browser_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "ip_address": ["203.0.113.25", "198.51.100.18"],
                },
                "asn": 15169,
            },
        }
        payload, _ = prepare_ingest_payload(record, default_dataset="network_demo")

        result = pipeline.ingest_classified_case(payload, ingestion_run_id="run-network")
        assert result.sql_result is not None

        with sa.create_engine(f"sqlite:///{db_path}", future=True).connect() as conn:
            rows = conn.execute(
                sa.select(sql_schema.entities.c.entity_type, sql_schema.entities.c.canonical_value)
                .where(sql_schema.entities.c.case_id == result.case_id)
                .where(sql_schema.entities.c.entity_type.in_(["browser_agent", "ip_address", "asn"]))
            ).fetchall()
        assert {(row.entity_type, row.canonical_value) for row in rows} == {
            ("browser_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
            ("ip_address", "203.0.113.25"),
            ("ip_address", "198.51.100.18"),
            ("asn", "15169"),
        }
    finally:
        get_settings.cache_clear()
