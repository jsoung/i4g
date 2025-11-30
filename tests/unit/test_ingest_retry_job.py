"""Unit tests for the ingestion retry worker job."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from i4g.store.ingestion_retry_store import RetryItem
from i4g.worker.jobs import ingest_retry


def _settings(default_dataset: str = "demo", retry_delay: int = 30, max_retries: int = 3):
    ingestion = SimpleNamespace(
        retry_delay_seconds=retry_delay,
        max_retries=max_retries,
        default_dataset=default_dataset,
    )
    return SimpleNamespace(ingestion=ingestion)


def _make_item(backend: str, payload: dict) -> RetryItem:
    return RetryItem(
        retry_id=f"retry-{backend}",
        case_id=payload.get("case_id") or payload.get("record", {}).get("case_id") or "case-1",
        backend=backend,
        payload=payload,
        attempt_count=0,
        next_attempt_at=datetime.now(timezone.utc),
    )


def test_main_no_items_returns_success(monkeypatch):
    store = Mock()
    store.fetch_ready.return_value = []

    monkeypatch.setattr(ingest_retry, "build_ingestion_retry_store", lambda: store)
    monkeypatch.setattr(ingest_retry, "get_settings", lambda: _settings())

    exit_code = ingest_retry.main()

    assert exit_code == 0
    store.fetch_ready.assert_called_once()


def test_main_processes_firestore_retry_success(monkeypatch):
    payload = {
        "record": {
            "case_id": "case-firestore",
            "text": "scam text",
            "fraud_type": "scam",
            "fraud_confidence": 0.9,
            "dataset": "demo",
        },
        "context": {
            "sql_result": {
                "case_id": "case-firestore",
                "document_ids": ["doc-1"],
                "entity_ids": [],
                "indicator_ids": [],
            }
        },
    }
    item = _make_item("firestore", payload)

    class StubStore:
        def __init__(self):
            self.deleted = []

        def fetch_ready(self, limit):
            return [item]

        def delete(self, retry_id):
            self.deleted.append(retry_id)

        def schedule_retry(self, *args, **kwargs):  # pragma: no cover - not used
            raise AssertionError("schedule_retry should not be called on success")

    store = StubStore()
    firestore_writer = Mock()

    monkeypatch.setattr(ingest_retry, "build_ingestion_retry_store", lambda: store)
    monkeypatch.setattr(ingest_retry, "build_firestore_writer", lambda: firestore_writer)
    monkeypatch.setattr(ingest_retry, "build_vertex_writer", lambda: Mock())
    monkeypatch.setattr(ingest_retry, "get_settings", lambda: _settings())

    exit_code = ingest_retry.main()

    assert exit_code == 0
    firestore_writer.persist_case_bundle.assert_called_once()
    assert store.deleted == [item.retry_id]


def test_main_reschedules_and_drops_on_failure(monkeypatch):
    payload = {
        "record": {
            "case_id": "case-vertex",
            "text": "retry me",
        }
    }
    item = _make_item("vertex", payload)

    class StubStore:
        def __init__(self):
            self.deleted = []
            self.scheduled = []

        def fetch_ready(self, limit):
            return [item]

        def delete(self, retry_id):
            self.deleted.append(retry_id)

        def schedule_retry(self, retry_id, delay_seconds):
            self.scheduled.append(delay_seconds)
            return 1

    store = StubStore()
    vertex_writer = Mock()
    vertex_writer.upsert_record.side_effect = RuntimeError("Vertex down")

    monkeypatch.setattr(ingest_retry, "build_ingestion_retry_store", lambda: store)
    monkeypatch.setattr(ingest_retry, "build_vertex_writer", lambda: vertex_writer)
    monkeypatch.setattr(ingest_retry, "build_firestore_writer", lambda: Mock())
    monkeypatch.setattr(ingest_retry, "get_settings", lambda: _settings(retry_delay=15, max_retries=1))

    exit_code = ingest_retry.main()

    assert exit_code == 1
    vertex_writer.upsert_record.assert_called_once()
    assert store.scheduled == [15]
    assert store.deleted == [item.retry_id]


def test_main_drops_malformed_payload(monkeypatch):
    payload = {"record": {"case_id": "case-bad", "dataset": "demo"}}  # missing text
    item = _make_item("firestore", payload)

    class StubStore:
        def __init__(self):
            self.deleted = []
            self.scheduled = []

        def fetch_ready(self, limit):
            return [item]

        def delete(self, retry_id):
            self.deleted.append(retry_id)

        def schedule_retry(self, *args, **kwargs):
            self.scheduled.append(args)
            return 1

    store = StubStore()
    firestore_writer = Mock()

    monkeypatch.setattr(ingest_retry, "build_ingestion_retry_store", lambda: store)
    monkeypatch.setattr(ingest_retry, "build_firestore_writer", lambda: firestore_writer)
    monkeypatch.setattr(ingest_retry, "build_vertex_writer", lambda: Mock())
    monkeypatch.setattr(ingest_retry, "get_settings", lambda: _settings())

    exit_code = ingest_retry.main()

    assert exit_code == 1
    firestore_writer.persist_case_bundle.assert_not_called()
    assert store.deleted == [item.retry_id]
    assert store.scheduled == []
