#!/usr/bin/env python3
"""Import Vertex-ready JSONL documents into Discovery Engine data stores.

This script wraps the Discovery Engine `ImportDocuments` API so we can load
transformed Azure Search exports without relying on `gcloud` alpha commands.

Example usage:

    python scripts/migration/import_vertex_documents.py \
        --project i4g-dev \
        --location global \
        --data-store-id retrieval-poc \
        --uris \
          gs://i4g-migration-artifacts-dev/search/20251114/vertex/groupsio-search_vertex.jsonl \
          gs://i4g-migration-artifacts-dev/search/20251114/vertex/intake-form-search_vertex.jsonl
"""

from __future__ import annotations

import argparse
import logging
from concurrent import futures
from typing import Iterable

from google.cloud import discoveryengine_v1beta as discoveryengine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import Vertex-ready JSONL files into Discovery Engine")
    parser.add_argument("--project", required=True, help="GCP project ID (e.g. i4g-dev)")
    parser.add_argument("--location", default="global", help="Discovery Engine location (default: global)")
    parser.add_argument("--collection-id", default="default_collection", help="Discovery Engine collection ID")
    parser.add_argument("--data-store-id", required=True, help="Discovery Engine data store ID")
    parser.add_argument(
        "--branch-id", default="default_branch", help="Discovery Engine branch ID (default: default_branch)"
    )
    parser.add_argument("--uris", nargs="+", required=True, help="GCS URIs of JSONL files to import")
    parser.add_argument(
        "--reconciliation-mode",
        default="INCREMENTAL",
        choices=["INCREMENTAL", "FULL"],
        help="Reconciliation mode for import (default: INCREMENTAL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate arguments and print intended request without calling the ImportDocuments API.",
    )
    parser.add_argument(
        "--error-prefix",
        help="Optional GCS prefix (gs://bucket/path) for per-document error logs",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=900.0,
        help=(
            "Maximum seconds to wait for the import operation to finish. "
            "Pass 0 or a negative value to wait indefinitely. (default: 900)"
        ),
    )
    return parser.parse_args()


def build_parent(project: str, location: str, collection_id: str, data_store_id: str, branch_id: str) -> str:
    return (
        f"projects/{project}/locations/{location}/collections/{collection_id}/"
        f"dataStores/{data_store_id}/branches/{branch_id}"
    )


def build_request(
    parent: str,
    uris: Iterable[str],
    reconciliation_mode: str,
    error_prefix: str | None,
) -> discoveryengine.ImportDocumentsRequest:
    gcs_source = discoveryengine.GcsSource(input_uris=list(uris))

    error_config = None
    if error_prefix:
        error_config = discoveryengine.ImportErrorConfig(gcs_prefix=error_prefix)

    request = discoveryengine.ImportDocumentsRequest(
        parent=parent,
        gcs_source=gcs_source,
        reconciliation_mode=getattr(
            discoveryengine.ImportDocumentsRequest.ReconciliationMode,
            reconciliation_mode,
        ),
        error_config=error_config,
    )

    return request


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    parent = build_parent(args.project, args.location, args.collection_id, args.data_store_id, args.branch_id)
    logging.info("Starting import into %s", parent)
    logging.info("URIs: %s", ", ".join(args.uris))

    request = build_request(parent, args.uris, args.reconciliation_mode, args.error_prefix)
    logging.debug("ImportDocumentsRequest: %s", request)

    if args.dry_run:
        logging.info("Dry-run mode enabled; request not sent.")
        return

    client = discoveryengine.DocumentServiceClient()
    operation = client.import_documents(request=request)
    if request.error_config and request.error_config.gcs_prefix:
        logging.info("Error manifest prefix: %s", request.error_config.gcs_prefix)
    logging.info("Operation name: %s", operation.operation.name)
    logging.info("Waiting for import to complete...")

    timeout = None if args.timeout <= 0 else args.timeout
    try:
        result = operation.result(timeout=timeout)
    except futures.TimeoutError:
        logging.warning(
            "Import is still running after %.0f seconds; monitor operation %s manually.",
            timeout or 0,
            operation.operation.name,
        )
        return

    logging.info("Import completed successfully")
    if result:
        logging.debug("Result: %s", result)


if __name__ == "__main__":
    main()
