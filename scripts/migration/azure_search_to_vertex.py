#!/usr/bin/env python3
"""Transform Azure Cognitive Search exports into Vertex AI Search import format.

This utility reads schema/document JSON files produced by
`azure_search_export.py` and emits Discovery Engine style JSONL documents
ready for `gcloud discovery-engine data-stores documents import`.

Example usage:

    python scripts/migration/azure_search_to_vertex.py \
        --input-dir data/search_exports \
        --output-dir data/search_exports/vertex \
        --index groupsio-search intake-form-search

The output JSONL files contain documents with the following shape:

    {
      "id": "...",
      "content": "...",
      "contentType": "text/plain",
      "structData": {...},
      "title": "optional"
    }

Only indexes explicitly mapped in `INDEX_MAPPINGS` are supported.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class IndexMapping:
    """Declarative mapping rules for a single Azure index."""

    def __init__(
        self,
        content_fields: Iterable[str],
        struct_fields: Iterable[str],
        title_field: Optional[str] = None,
    ) -> None:
        self.content_fields: List[str] = list(content_fields)
        self.struct_fields: List[str] = list(struct_fields)
        self.title_field = title_field

    def build_document(self, raw: Dict[str, object]) -> Optional[Dict[str, object]]:
        doc_id = str(raw.get("id"))
        if not doc_id or doc_id == "None":
            logging.warning("Skipping document without id: %s", raw)
            return None

        parts: List[str] = []
        for field in self.content_fields:
            value = raw.get(field)
            if value:
                parts.append(str(value).strip())
        content = "\n\n".join(part for part in parts if part)

        struct: Dict[str, object] = {}
        for field in self.struct_fields:
            value = raw.get(field)
            if value in (None, "", [], {}):
                continue
            struct[field] = value

        doc: Dict[str, object] = {"id": doc_id}
        content_text = content.strip()
        if not content_text:
            fallback_parts: List[str] = []
            for field in self.struct_fields:
                value = raw.get(field)
                if isinstance(value, str) and value.strip():
                    fallback_parts.append(value.strip())
                elif isinstance(value, (list, tuple)):
                    fallback_parts.extend(str(item).strip() for item in value if str(item).strip())
            content_text = "\n\n".join(fallback_parts).strip()

        if not content_text:
            logging.debug("Skipping document %s due to empty textual content", doc_id)
            return None

        if content_text:
            raw_bytes = base64.b64encode(content_text.encode("utf-8")).decode("ascii")
            doc["content"] = {
                "mimeType": "text/plain",
                "rawBytes": raw_bytes,
            }
            struct["content"] = content_text
        if struct:
            doc["structData"] = struct
        elif not content:
            # Nothing to store; skip empty docs.
            logging.debug("Skipping document %s with no content or struct data", doc_id)
            return None

        if self.title_field:
            title = raw.get(self.title_field)
            if title:
                doc.setdefault("structData", {})["title"] = str(title)

        # Discovery Engine limits document IDs to 128 characters.
        if len(doc["id"]) > 128:
            original_id = doc["id"]
            hashed = hashlib.sha256(original_id.encode("utf-8")).hexdigest()
            doc["id"] = f"hash_{hashed[:32]}"
            doc.setdefault("structData", {})["source_id"] = original_id
            logging.debug("Shortened document id %s to %s", original_id, doc["id"])

        return doc


INDEX_MAPPINGS: Dict[str, IndexMapping] = {
    "groupsio-search": IndexMapping(
        content_fields=("subject", "body", "content"),
        struct_fields=(
            "sender_name",
            "sender_id",
            "group_name",
            "topic_id",
            "timestamp",
            "source",
            "blob_urls",
            "groupsio_message_id",
        ),
        title_field="subject",
    ),
    "intake-form-search": IndexMapping(
        content_fields=(
            "incident_details",
            "additional_info",
            "criminal_bank_info",
            "money_send_method",
            "crypto_info",
            "apps_or_websites",
            "criminal_contacts",
            "criminal_address",
            "payment_handles",
            "content",
        ),
        struct_fields=(
            "email",
            "first_name",
            "last_name",
            "country",
            "city",
            "state",
            "reported_to_law",
            "law_agencies",
            "timestamp",
            "blob_urls",
        ),
        title_field="email",
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transform Azure Search exports for Vertex AI Search imports")
    parser.add_argument(
        "--input-dir",
        default="data/search_exports",
        help="Directory containing <index>_documents.jsonl files.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/search_exports/vertex",
        help="Directory to receive Vertex-ready JSONL outputs.",
    )
    parser.add_argument(
        "--index",
        nargs="*",
        default=list(INDEX_MAPPINGS.keys()),
        help="Indexes to transform (defaults to all supported indexes).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args()


def ensure_output_dir(path: str) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    return output


def transform_index(index_name: str, mapping: IndexMapping, input_dir: Path, output_dir: Path) -> None:
    input_path = input_dir / f"{index_name}_documents.jsonl"
    if not input_path.exists():
        logging.error("Missing export file for %s: %s", index_name, input_path)
        return

    output_path = output_dir / f"{index_name}_vertex.jsonl"
    converted = 0
    skipped = 0

    with input_path.open("r", encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            raw = json.loads(line)

            doc = mapping.build_document(raw)
            if not doc:
                skipped += 1
                continue

            dst.write(json.dumps(doc, ensure_ascii=False))
            dst.write("\n")
            converted += 1

    logging.info(
        "Index %s: converted %d documents (skipped %d) → %s",
        index_name,
        converted,
        skipped,
        output_path,
    )


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    input_dir = Path(args.input_dir)
    output_dir = ensure_output_dir(args.output_dir)

    for index_name in args.index:
        if index_name not in INDEX_MAPPINGS:
            logging.error("Index %s is not configured; skipping", index_name)
            continue
        transform_index(index_name, INDEX_MAPPINGS[index_name], input_dir, output_dir)


if __name__ == "__main__":
    main()
