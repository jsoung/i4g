"""Cloud Run job entrypoint for ingestion retry queue processing."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict, Tuple

from i4g.services.factories import build_firestore_writer, build_ingestion_retry_store, build_vertex_writer
from i4g.settings import get_settings
from i4g.store.ingest import build_case_bundle
from i4g.store.ingestion_retry_store import IngestionRetryStore, RetryItem
from i4g.store.sql_writer import SqlWriterResult

LOGGER = logging.getLogger("i4g.worker.jobs.ingest_retry")


class RetryPayloadError(RuntimeError):
    """Raised when a retry payload is irrecoverably malformed."""


def _configure_logging() -> None:
    level_name = os.getenv("I4G_RUNTIME__LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _extract_retry_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    record = payload.get("record") if isinstance(payload, dict) else None
    context = payload.get("context") if isinstance(payload, dict) else None
    if not isinstance(record, dict):
        record = payload if isinstance(payload, dict) else {}
    if not isinstance(context, dict):
        context = {}
    return record, context


def _deserialize_sql_result(data: Dict[str, Any] | None, fallback_case_id: str | None) -> SqlWriterResult:
    if not data:
        raise RetryPayloadError("retry payload missing sql_result context")
    case_id = data.get("case_id") or fallback_case_id
    if not case_id:
        raise RetryPayloadError("retry payload missing case_id for sql_result")
    return SqlWriterResult(
        case_id=case_id,
        document_ids=list(data.get("document_ids") or []),
        entity_ids=list(data.get("entity_ids") or []),
        indicator_ids=list(data.get("indicator_ids") or []),
    )


def _process_firestore_retry(
    item: RetryItem,
    record: Dict[str, Any],
    context: Dict[str, Any],
    *,
    firestore_writer,
    default_dataset: str,
) -> None:
    text = record.get("text")
    if not text:
        raise RetryPayloadError("retry payload missing text for Firestore fan-out")
    dataset = record.get("dataset") or default_dataset
    if not dataset:
        raise RetryPayloadError("retry payload missing dataset for Firestore fan-out")

    sql_result = _deserialize_sql_result(context.get("sql_result"), record.get("case_id") or item.case_id)
    bundle = build_case_bundle(
        record,
        case_id=sql_result.case_id,
        dataset=dataset,
        text=text,
    )
    firestore_writer.persist_case_bundle(bundle, sql_result, ingestion_run_id=record.get("ingestion_run_id"))


def _process_vertex_retry(
    item: RetryItem,
    record: Dict[str, Any],
    *,
    vertex_writer,
    default_dataset: str,
) -> None:
    payload = dict(record)
    payload.setdefault("case_id", item.case_id)
    payload.setdefault("dataset", payload.get("dataset") or default_dataset)
    text = payload.get("text")
    if not text:
        raise RetryPayloadError("retry payload missing text for Vertex fan-out")
    vertex_writer.upsert_record(payload)


def _handle_retry_failure(
    store: IngestionRetryStore,
    item: RetryItem,
    *,
    retry_delay: int,
    max_retries: int,
) -> str:
    if max_retries <= 0:
        store.delete(item.retry_id)
        LOGGER.error(
            "Dropping %s retry for case_id=%s because max_retries=%s",
            item.backend,
            item.case_id,
            max_retries,
        )
        return "dropped"
    next_count = store.schedule_retry(item.retry_id, delay_seconds=retry_delay)
    if next_count is None:
        LOGGER.warning("Retry entry disappeared while scheduling retry_id=%s", item.retry_id)
        return "missing"
    if next_count >= max_retries:
        store.delete(item.retry_id)
        LOGGER.error(
            "Dropping %s retry for case_id=%s after %s attempt(s)",
            item.backend,
            item.case_id,
            next_count,
        )
        return "dropped"
    LOGGER.info(
        "Rescheduled %s retry for case_id=%s next_attempt=%s attempts=%s/%s",
        item.backend,
        item.case_id,
        item.next_attempt_at,
        next_count,
        max_retries,
    )
    return "rescheduled"


def main() -> int:
    """Entry point executed by the Cloud Run job container."""

    _configure_logging()
    settings = get_settings()

    batch_limit = int(os.getenv("I4G_INGEST_RETRY__BATCH_LIMIT", "25") or 25)
    dry_run = os.getenv("I4G_INGEST_RETRY__DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}

    try:
        retry_store = build_ingestion_retry_store()
    except Exception:
        LOGGER.exception("Failed to initialise ingestion retry store")
        return 1

    ready_items = retry_store.fetch_ready(limit=batch_limit)
    if not ready_items:
        LOGGER.info("No ingestion retry entries ready; exiting")
        return 0

    LOGGER.info("Processing %s ingestion retry item(s) dry_run=%s", len(ready_items), dry_run)

    if dry_run:
        for item in ready_items:
            LOGGER.info(
                "Dry run: would replay backend=%s case_id=%s attempts=%s",
                item.backend,
                item.case_id,
                item.attempt_count,
            )
        return 0

    retry_delay = settings.ingestion.retry_delay_seconds
    max_retries = settings.ingestion.max_retries
    default_dataset = settings.ingestion.default_dataset

    successes = 0
    failures = 0
    rescheduled = 0
    dropped = 0

    firestore_writer = None
    vertex_writer = None

    for item in ready_items:
        record, context = _extract_retry_payload(item.payload or {})
        try:
            if item.backend == "firestore":
                if firestore_writer is None:
                    firestore_writer = build_firestore_writer()
                _process_firestore_retry(
                    item,
                    record,
                    context,
                    firestore_writer=firestore_writer,
                    default_dataset=default_dataset,
                )
            elif item.backend == "vertex":
                if vertex_writer is None:
                    vertex_writer = build_vertex_writer()
                _process_vertex_retry(
                    item,
                    record,
                    vertex_writer=vertex_writer,
                    default_dataset=default_dataset,
                )
            else:
                raise RetryPayloadError(f"Unsupported backend '{item.backend}'")
            retry_store.delete(item.retry_id)
            successes += 1
            LOGGER.info("Replayed %s backend for case_id=%s", item.backend, item.case_id)
        except RetryPayloadError:
            failures += 1
            dropped += 1
            retry_store.delete(item.retry_id)
            LOGGER.exception(
                "Dropping retry_id=%s backend=%s due to malformed payload",
                item.retry_id,
                item.backend,
            )
        except Exception:
            failures += 1
            outcome = _handle_retry_failure(
                retry_store,
                item,
                retry_delay=retry_delay,
                max_retries=max_retries,
            )
            if outcome == "rescheduled":
                rescheduled += 1
            elif outcome == "dropped":
                dropped += 1
            else:
                LOGGER.warning(
                    "Failed to schedule retry for retry_id=%s backend=%s",
                    item.retry_id,
                    item.backend,
                )
            LOGGER.exception(
                "Backend replay failed for retry_id=%s backend=%s",
                item.retry_id,
                item.backend,
            )

    LOGGER.info(
        ("Ingestion retry batch complete: successes=%s failures=%s rescheduled=%s dropped=%s"),
        successes,
        failures,
        rescheduled,
        dropped,
    )

    return 0 if failures == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
