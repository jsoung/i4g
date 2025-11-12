"""Cloud Run job entrypoint for ingestion pipelines."""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Iterator

from i4g.services.factories import build_structured_store, build_vector_store
from i4g.store.ingest import IngestPipeline

LOGGER = logging.getLogger("i4g.worker.jobs.ingest")


def _configure_logging() -> None:
    level_name = os.getenv("I4G_RUNTIME__LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


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


def main() -> int:
    """Entry point executed by the Cloud Run job container."""

    _configure_logging()

    dataset_path = Path(os.getenv("I4G_INGEST__JSONL_PATH", "/app/data/retrieval_poc/cases.jsonl"))
    batch_limit = int(os.getenv("I4G_INGEST__BATCH_LIMIT", "0") or 0)
    dry_run = os.getenv("I4G_INGEST__DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}
    reset_vector = os.getenv("I4G_INGEST__RESET_VECTOR", "false").lower() in {"1", "true", "yes", "on"}
    enable_vector = os.getenv("I4G_INGEST__ENABLE_VECTOR", "false").lower() in {"1", "true", "yes", "on"}

    LOGGER.info(
        "Starting ingestion job: dataset=%s batch_limit=%s dry_run=%s enable_vector=%s reset_vector=%s",
        dataset_path,
        batch_limit or "unbounded",
        dry_run,
        enable_vector,
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

    pipeline = IngestPipeline(structured_store=structured_store, vector_store=vector_store, enable_vector=enable_vector)

    processed = 0
    failures = 0

    try:
        for record in _load_jsonl(dataset_path):
            if batch_limit and processed >= batch_limit:
                break
            if dry_run:
                LOGGER.info("Dry run enabled; would ingest record %s", record.get("case_id"))
                processed += 1
                continue
            try:
                case_id = pipeline.ingest_classified_case(record)
                processed += 1
                LOGGER.info("Ingested record case_id=%s", case_id)
            except Exception:  # pragma: no cover - defensive logging around ingestion pipeline
                failures += 1
                LOGGER.exception("Failed to ingest record case_id=%s", record.get("case_id"))
    except Exception:  # pragma: no cover - unexpected reader failure
        LOGGER.exception("Ingestion batch aborted due to reader error")
        return 1

    LOGGER.info("Ingestion complete: processed=%s failures=%s", processed, failures)

    return 0 if failures == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
