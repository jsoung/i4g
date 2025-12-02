#!/usr/bin/env python3
"""Ingest JSONL scam cases into a Vertex AI Search (Discovery) data store.

Example usage:

    python scripts/ingest_vertex_search.py \
        --project i4g-dev \
        --location global \
        --data-store-id retrieval-poc \
        --jsonl data/retrieval_poc/cases.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

import google.api_core.exceptions
from google.cloud import discoveryengine_v1beta as discoveryengine
from google.protobuf import json_format

from i4g.services.ingest_payloads import prepare_ingest_payload
from i4g.services.vertex_documents import build_vertex_document

LOGGER = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        required=True,
        help="Google Cloud project that owns the Discovery data store.",
    )
    parser.add_argument(
        "--location",
        default="global",
        help="Discovery location (default: global).",
    )
    parser.add_argument(
        "--branch-id",
        default="default_branch",
        help="Branch to import documents into (default: default_branch).",
    )
    parser.add_argument(
        "--data-store-id",
        required=True,
        help="Discovery data store identifier.",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        required=True,
        help="Path to JSON Lines file containing synthetic scam cases.",
    )
    parser.add_argument(
        "--dataset",
        help="Dataset identifier injected into each document when the JSONL record omits one.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of documents to submit per import batch (default: 50).",
    )
    parser.add_argument(
        "--reconcile-mode",
        choices=[
            "UNSPECIFIED",
            "INCREMENTAL",
            "FULL",
        ],
        default="INCREMENTAL",
        help="Import reconciliation mode (default: INCREMENTAL).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and preview the first record without calling the API.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


def load_records(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
                msg = f"Failed to decode JSON on line {line_no}: {exc}"
                raise ValueError(msg) from exc


def _enrich_record(record: dict, default_dataset: str | None = None) -> dict:
    """Merge normalized ingest metadata back into the raw record."""

    payload, _ = prepare_ingest_payload(record, default_dataset=default_dataset)
    enriched = dict(record)
    for key in (
        "case_id",
        "dataset",
        "categories",
        "indicator_ids",
        "fraud_type",
        "fraud_confidence",
        "tags",
        "summary",
        "channel",
        "timestamp",
        "structured_fields",
        "metadata",
    ):
        value = payload.get(key)
        if value is not None:
            enriched[key] = value
    return enriched


def chunked(iterable: Iterable[discoveryengine.Document], size: int) -> Iterator[List[discoveryengine.Document]]:
    chunk: List[discoveryengine.Document] = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    LOGGER.info("Loading records from %s", args.jsonl)
    records = list(load_records(args.jsonl))
    if not records:
        LOGGER.warning("No records found; nothing to ingest.")
        return 0

    enriched_records = [_enrich_record(record, args.dataset) for record in records]
    documents = [build_vertex_document(record, default_dataset=args.dataset) for record in enriched_records]

    if args.dry_run:
        preview = documents[0]
        LOGGER.info("Dry run: first document payload (id=%s)", preview.id)
        # Use the underlying protobuf message for JSON dump; proto-plus wrapper lacks DESCRIPTOR.
        LOGGER.info(json.dumps(json_format.MessageToDict(preview._pb), indent=2))
        LOGGER.info("Total documents parsed: %s", len(documents))
        return 0

    client = discoveryengine.DocumentServiceClient()
    parent = client.branch_path(
        project=args.project,
        location=args.location,
        data_store=args.data_store_id,
        branch=args.branch_id,
    )

    reconcile_lookup = {
        "UNSPECIFIED": discoveryengine.ImportDocumentsRequest.ReconciliationMode.RECONCILIATION_MODE_UNSPECIFIED,
        "INCREMENTAL": discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL,
        "FULL": discoveryengine.ImportDocumentsRequest.ReconciliationMode.FULL,
    }
    reconcile_mode = reconcile_lookup[args.reconcile_mode]

    total_success = 0
    total_fail = 0

    for batch_no, chunk in enumerate(chunked(documents, args.batch_size), start=1):
        LOGGER.info("Submitting batch %d with %d documents", batch_no, len(chunk))
        request = discoveryengine.ImportDocumentsRequest(
            parent=parent,
            inline_source=discoveryengine.ImportDocumentsRequest.InlineSource(documents=chunk),
            reconciliation_mode=reconcile_mode,
        )

        try:
            operation = client.import_documents(request=request)
            response = operation.result()
        except google.api_core.exceptions.GoogleAPIError as exc:
            LOGGER.error("Batch %d failed: %s", batch_no, exc)
            total_fail += len(chunk)
            continue

        error_samples = list(getattr(response, "error_samples", []))
        batch_errors = len(error_samples)
        batch_success = max(len(chunk) - batch_errors, 0)
        total_success += batch_success
        total_fail += batch_errors

        if error_samples:
            LOGGER.warning("Batch %d reported %d sample errors", batch_no, len(error_samples))
            for sample in error_samples[:3]:
                LOGGER.warning(json_format.MessageToJson(sample))

        LOGGER.info(
            "Batch %d completed: success=%d failure=%d",
            batch_no,
            batch_success,
            batch_errors,
        )

    LOGGER.info(
        "Ingestion complete: %d succeeded, %d failed, total input %d",
        total_success,
        total_fail,
        len(documents),
    )

    return 0 if total_fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
