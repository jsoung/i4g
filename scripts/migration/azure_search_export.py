#!/usr/bin/env python3
"""Export Azure Cognitive Search index schemas and documents to local JSON files.

The tool reads the following environment variables unless overridden via CLI:

- AZURE_SEARCH_ENDPOINT: e.g. https://example.search.windows.net
- AZURE_SEARCH_ADMIN_KEY: Admin (or query) key with access to the indexes.

Example usage:

    python scripts/migration/azure_search_export.py \
        --indexes users cases \
        --output-dir data/search_exports/20251114

The script writes `<index>_schema.json` and `<index>_documents.jsonl` files for
each index, streaming documents in batches to avoid high memory usage.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Iterable, Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Azure Cognitive Search indexes to JSON artifacts")
    parser.add_argument(
        "--endpoint",
        default=os.environ.get("AZURE_SEARCH_ENDPOINT"),
        help="Azure Cognitive Search endpoint (e.g. https://example.search.windows.net)",
    )
    parser.add_argument(
        "--admin-key",
        default=os.environ.get("AZURE_SEARCH_ADMIN_KEY"),
        help="Azure Cognitive Search admin key (or query key with index read access)",
    )
    parser.add_argument(
        "--indexes",
        nargs="*",
        help="Optional list of index names to export. Defaults to all indexes in the service.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/search_exports",
        help="Directory to write schema and document files (created if missing).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of documents to request per page when streaming index contents.",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        help="Optional limit on documents per index (useful for sampling).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    args = parser.parse_args()
    if not args.endpoint:
        parser.error("--endpoint or AZURE_SEARCH_ENDPOINT is required")
    if not args.admin_key:
        parser.error("--admin-key or AZURE_SEARCH_ADMIN_KEY is required")
    return args


def ensure_output_dir(path: str) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    return output


def resolve_indexes(index_client: SearchIndexClient, requested: Optional[Iterable[str]]) -> list[str]:
    if requested:
        return list(requested)
    return [index.name for index in index_client.list_indexes()]  # type: ignore[return-value]


def export_schema(index_client: SearchIndexClient, index_name: str, output_dir: Path) -> None:
    schema = index_client.get_index(index_name)
    schema_path = output_dir / f"{index_name}_schema.json"
    with schema_path.open("w", encoding="utf-8") as fh:
        json.dump(schema.serialize(), fh, indent=2)
    logging.info("Wrote schema for %s to %s", index_name, schema_path)


def export_documents(
    search_client: SearchClient, index_name: str, output_dir: Path, batch_size: int, max_docs: Optional[int]
) -> None:
    docs_path = output_dir / f"{index_name}_documents.jsonl"
    total_written = 0
    with docs_path.open("w", encoding="utf-8") as fh:
        results = search_client.search(search_text="*", top=batch_size, include_total_count=True)
        for page in results.by_page():
            for doc in page:
                fh.write(json.dumps(doc, ensure_ascii=False))
                fh.write("\n")
                total_written += 1
                if max_docs and total_written >= max_docs:
                    logging.warning("Reached max_docs=%d for %s; truncating export", max_docs, index_name)
                    logging.info("Wrote %d documents for %s", total_written, index_name)
                    return
    logging.info("Wrote %d documents for %s", total_written, index_name)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    output_dir = ensure_output_dir(args.output_dir)
    credential = AzureKeyCredential(args.admin_key)

    index_client = SearchIndexClient(endpoint=args.endpoint, credential=credential)
    indexes = resolve_indexes(index_client, args.indexes)
    logging.info("Exporting indexes: %s", ", ".join(indexes))

    for index_name in indexes:
        logging.info("Processing index %s", index_name)
        export_schema(index_client, index_name, output_dir)
        search_client = SearchClient(endpoint=args.endpoint, index_name=index_name, credential=credential)
        export_documents(search_client, index_name, output_dir, args.batch_size, args.max_docs)


if __name__ == "__main__":
    main()
