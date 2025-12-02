"""Unit tests for ingestion job retry helpers."""

from __future__ import annotations

from typing import Any, Dict
from unittest.mock import Mock

from i4g.store.sql_writer import SqlWriterResult
from i4g.worker.jobs import ingest


class _ExplodingStr:
    """Helper object whose ``str()`` raises to exercise clone fallback."""

    def __str__(self) -> str:
        raise ValueError("boom")


def test_clone_payload_round_trips_without_shared_state() -> None:
    """Ensure JSON branch returns a deep copy that does not share nested references."""

    payload: Dict[str, Any] = {"case_id": "case-1", "metadata": {"source": "unit"}}
    clone = ingest._clone_payload(payload)
    assert clone == payload
    assert clone is not payload
    clone["metadata"]["source"] = "mutated"
    assert payload["metadata"]["source"] == "unit"


def test_clone_payload_falls_back_when_serialization_fails() -> None:
    """Verify we still return a dict when JSON serialization raises."""

    payload: Dict[str, Any] = {"case_id": "case-fallback", "bad": _ExplodingStr()}
    clone = ingest._clone_payload(payload)
    assert clone["bad"] is payload["bad"]
    assert clone is not payload


def test_maybe_enqueue_retry_skips_when_not_attempted() -> None:
    """Retries should only be scheduled when a backend attempt actually ran and failed."""

    store = Mock()
    result = ingest._maybe_enqueue_retry(
        store,
        backend="firestore",
        attempted=False,
        succeeded=False,
        payload={"case_id": "case-skip"},
        retry_delay=30,
        max_retries=3,
    )
    assert result == 0
    store.enqueue.assert_not_called()


def test_maybe_enqueue_retry_enqueues_failed_attempt() -> None:
    """Failed backend writes should enqueue a cloned payload for retry processing."""

    store = Mock()
    payload = {"case_id": "case-retry", "nested": {"value": 1}}
    sql_result = SqlWriterResult(case_id="case-retry", document_ids=["doc-1"], entity_ids=[], indicator_ids=[])
    result = ingest._maybe_enqueue_retry(
        store,
        backend="vertex",
        attempted=True,
        succeeded=False,
        payload=payload,
        retry_delay=45,
        max_retries=5,
        error="boom",
        sql_result=sql_result,
    )
    assert result == 1
    store.enqueue.assert_called_once()
    kwargs = store.enqueue.call_args.kwargs
    assert kwargs["case_id"] == "case-retry"
    assert kwargs["backend"] == "vertex"
    assert kwargs["delay_seconds"] == 45
    queue_payload = kwargs["payload"]
    assert queue_payload["record"] == payload
    assert queue_payload["record"] is not payload
    queue_payload["record"]["nested"]["value"] = 5
    assert payload["nested"]["value"] == 1
    assert queue_payload["context"]["error"] == "boom"
    assert queue_payload["context"]["sql_result"] == {
        "case_id": "case-retry",
        "document_ids": ["doc-1"],
        "entity_ids": [],
        "indicator_ids": [],
    }


def test_maybe_enqueue_retry_handles_enqueue_failures() -> None:
    """Retry scheduling should swallow enqueue errors and continue the job loop."""

    store = Mock()
    store.enqueue.side_effect = RuntimeError("db down")
    result = ingest._maybe_enqueue_retry(
        store,
        backend="vertex",
        attempted=True,
        succeeded=False,
        payload={"case_id": "case-error"},
        retry_delay=15,
        max_retries=2,
    )
    assert result == 0
    store.enqueue.assert_called_once()


def test_maybe_enqueue_retry_respects_max_retries() -> None:
    """Retries should be skipped entirely when max_retries is zero or negative."""

    store = Mock()
    payload = {"case_id": "case-skip"}
    result = ingest._maybe_enqueue_retry(
        store,
        backend="firestore",
        attempted=True,
        succeeded=False,
        payload=payload,
        retry_delay=10,
        max_retries=0,
    )
    assert result == 0
    store.enqueue.assert_not_called()
