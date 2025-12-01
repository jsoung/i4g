"""Cloud Run job entrypoint for ingestion pipelines."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from i4g.services.factories import (
    build_ingestion_retry_store,
    build_ingestion_run_tracker,
    build_structured_store,
    build_vector_store,
)
from i4g.services.ingest_payloads import prepare_ingest_payload
from i4g.settings import get_settings
from i4g.store.ingest import IngestPipeline
from i4g.store.sql_writer import SqlWriterResult

LOGGER = logging.getLogger("i4g.worker.jobs.ingest")


def _configure_logging() -> None:
    level_name = os.getenv("I4G_RUNTIME__LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _env_flag(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _load_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"failed to parse JSON on line {line_no}: {exc}") from exc


def _clone_payload(payload: dict) -> dict:
    try:
        return json.loads(json.dumps(payload, default=str))
    except Exception:
        return dict(payload)


def _serialise_sql_result(result: Optional[SqlWriterResult]) -> Dict[str, Any] | None:
    if result is None:
        return None
    return {
        "case_id": result.case_id,
        "document_ids": list(result.document_ids),
        "entity_ids": list(result.entity_ids),
        "indicator_ids": list(result.indicator_ids),
    }


def _maybe_enqueue_retry(
    retry_store,
    *,
    backend: str,
    attempted: bool,
    succeeded: bool,
    payload: dict,
    retry_delay: int,
    max_retries: int,
    error: Optional[str] = None,
    sql_result: Optional[SqlWriterResult] = None,
) -> int:
    if not retry_store or not attempted or succeeded:
        return 0
    if max_retries <= 0:
        LOGGER.info(
            "Skipping %s retry for case_id=%s because max_retries=%s",
            backend,
            payload.get("case_id") or "unknown",
            max_retries,
        )
        return 0
    case_id = payload.get("case_id") or "unknown"
    try:
        cloned = _clone_payload(payload)
        queue_payload: Dict[str, Any] = {"record": cloned}
        context: Dict[str, Any] = {}
        serialised_sql = _serialise_sql_result(sql_result)
        if serialised_sql:
            context["sql_result"] = serialised_sql
        if error:
            context["error"] = error
        if context:
            queue_payload["context"] = context
        retry_store.enqueue(case_id=case_id, backend=backend, payload=queue_payload, delay_seconds=retry_delay)
        LOGGER.warning(
            "Scheduled %s retry for case_id=%s (max_attempts=%s) error=%s",
            backend,
            case_id,
            max_retries,
            error,
        )
        return 1
    except Exception:
        LOGGER.exception("Failed to enqueue %s retry for case_id=%s", backend, case_id)
        return 0


def main() -> int:
    """Entry point executed by the Cloud Run job container."""

    _configure_logging()

    settings = get_settings()

    dataset_override = os.getenv("I4G_INGEST__JSONL_PATH")
    dataset_path = Path(dataset_override) if dataset_override else Path(settings.ingestion.dataset_path)

    batch_limit_override = os.getenv("I4G_INGEST__BATCH_LIMIT")
    try:
        batch_limit = int(batch_limit_override) if batch_limit_override else settings.ingestion.batch_limit
    except ValueError:
        LOGGER.warning("Invalid batch limit override: %s", batch_limit_override)
        batch_limit = settings.ingestion.batch_limit

    dry_run_override = _env_flag("I4G_INGEST__DRY_RUN")
    dry_run = dry_run_override if dry_run_override is not None else settings.ingestion.dry_run

    reset_override = _env_flag("I4G_INGEST__RESET_VECTOR")
    reset_vector = reset_override if reset_override is not None else settings.ingestion.reset_vector
    vector_override = _env_flag("I4G_INGEST__ENABLE_VECTOR")
    enable_vector = vector_override if vector_override is not None else settings.ingestion.enable_vector_store
    vertex_override = _env_flag("I4G_INGEST__ENABLE_VERTEX")
    enable_vertex = vertex_override if vertex_override is not None else settings.ingestion.enable_vertex
    firestore_override = _env_flag("I4G_INGEST__ENABLE_FIRESTORE")
    enable_firestore = firestore_override if firestore_override is not None else settings.ingestion.enable_firestore
    dataset_name = os.getenv("I4G_INGEST__DATASET_NAME") or dataset_path.stem or settings.ingestion.default_dataset

    LOGGER.info(
        (
            "Starting ingestion job: dataset=%s batch_limit=%s dry_run=%s "
            "enable_vector=%s enable_vertex=%s enable_firestore=%s reset_vector=%s"
        ),
        dataset_name,
        batch_limit or "unbounded",
        dry_run,
        enable_vector,
        enable_vertex,
        enable_firestore,
        reset_vector,
    )

    if not dataset_path.exists():
        LOGGER.warning("JSONL dataset not found; nothing to ingest: %s", dataset_path)
        return 0

    structured_store = build_structured_store()
    vector_store = None
    if enable_vector:
        try:
            vector_store = build_vector_store(reset=reset_vector)
        except Exception:  # pragma: no cover - vector init is optional for jobs
            LOGGER.exception("Vector store initialisation failed; continuing without embeddings")
            enable_vector = False

    if not enable_vector:
        LOGGER.info("Vector ingestion disabled; skipping embedding writes")

    pipeline = IngestPipeline(
        structured_store=structured_store,
        vector_store=vector_store,
        enable_vector=enable_vector,
        enable_vertex=enable_vertex,
        enable_firestore=enable_firestore,
        default_dataset=dataset_name,
    )

    run_tracker = None
    run_id = None
    retry_store = None
    retry_delay = settings.ingestion.retry_delay_seconds
    max_retries = settings.ingestion.max_retries
    if not dry_run:
        try:
            run_tracker = build_ingestion_run_tracker()
            run_id = run_tracker.start_run(
                dataset=dataset_name,
                source_bundle=str(dataset_path),
                vector_enabled=enable_vector,
            )
        except Exception:
            LOGGER.exception("Failed to initialise ingestion run tracker; continuing without DB run row")
            run_tracker = None
            run_id = None

        try:
            retry_store = build_ingestion_retry_store()
        except Exception:
            LOGGER.exception("Failed to initialise ingestion retry store; retries disabled for this run")
            retry_store = None

    processed = 0
    failures = 0
    scheduled_retries = 0

    try:
        for record in _load_jsonl(dataset_path):
            if batch_limit and processed >= batch_limit:
                break
            payload, diagnostics = prepare_ingest_payload(record, default_dataset=dataset_name)
            if dry_run:
                LOGGER.info(
                    "Dry run enabled; would ingest case_id=%s classification=%s confidence=%.2f text_source=%s",
                    payload.get("case_id") or "generated",
                    diagnostics["classification"],
                    diagnostics["confidence"],
                    diagnostics["text_source"],
                )
                processed += 1
                continue
            try:
                result = pipeline.ingest_classified_case(payload, ingestion_run_id=run_id)
                case_id = result.case_id
                payload["case_id"] = case_id
                if run_id:
                    payload.setdefault("ingestion_run_id", run_id)
                if run_tracker and run_id:
                    try:
                        run_tracker.record_case(
                            run_id,
                            result.sql_result,
                            firestore_writes=1 if result.firestore_written else 0,
                            vertex_writes=1 if result.vertex_written else 0,
                        )
                    except Exception:
                        LOGGER.exception("Failed to update ingestion run counters run_id=%s", run_id)

                if retry_store:
                    scheduled_retries += _maybe_enqueue_retry(
                        retry_store,
                        backend="firestore",
                        attempted=result.firestore_attempted,
                        succeeded=result.firestore_written,
                        payload=payload,
                        retry_delay=retry_delay,
                        max_retries=max_retries,
                        error=result.firestore_error,
                        sql_result=result.sql_result,
                    )
                    scheduled_retries += _maybe_enqueue_retry(
                        retry_store,
                        backend="vertex",
                        attempted=result.vertex_attempted,
                        succeeded=result.vertex_written,
                        payload=payload,
                        retry_delay=retry_delay,
                        max_retries=max_retries,
                        error=result.vertex_error,
                    )
                processed += 1
                LOGGER.info(
                    "Ingested record case_id=%s classification=%s confidence=%.2f text_source=%s",
                    case_id,
                    diagnostics["classification"],
                    diagnostics["confidence"],
                    diagnostics["text_source"],
                )
            except Exception:  # pragma: no cover - defensive logging around ingestion pipeline
                failures += 1
                LOGGER.exception("Failed to ingest record case_id=%s", payload.get("case_id"))
    except Exception as exc:  # pragma: no cover - unexpected reader failure
        LOGGER.exception("Ingestion batch aborted due to reader error")
        if run_tracker and run_id:
            try:
                run_tracker.complete_run(run_id, status="failed", last_error=str(exc))
            except Exception:
                LOGGER.exception("Failed to mark ingestion run as failed run_id=%s", run_id)
        return 1

    if run_tracker and run_id:
        run_status = "succeeded" if failures == 0 else "partial"
        last_error = None if failures == 0 else f"Encountered {failures} ingestion failure(s)"
        try:
            run_tracker.complete_run(
                run_id,
                status=run_status,
                last_error=last_error,
                retry_increment=scheduled_retries,
            )
        except Exception:
            LOGGER.exception("Failed to complete ingestion run metadata run_id=%s", run_id)

    LOGGER.info("Ingestion complete: processed=%s failures=%s", processed, failures)

    return 0 if failures == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
