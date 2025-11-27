#!/usr/bin/env python
"""Bulk ingest JSONL bundles into the local Structured + Vector stores.

Usage:
    python scripts/ingest_bundles.py --input data/bundles/bundle_all.jsonl [--limit 1000]

This is idempotent (uses bundle record `id` as `case_id`) and safe to re-run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from i4g.store.ingest import IngestPipeline


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bulk ingest JSONL bundles into i4g stores")
    p.add_argument("--input", type=Path, required=True, help="Path to JSONL bundle file")
    p.add_argument("--limit", type=int, default=0, help="Optional limit on number of records (0 = all)")
    return p.parse_args()


def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def map_bundle_record(rec: dict) -> dict:
    # Map bundle fields to the ingestion pipeline expected keys
    return {
        "case_id": rec.get("id") or rec.get("case_id"),
        "text": rec.get("text", ""),
        "fraud_type": rec.get("scam_type") or rec.get("fraud_type", "unknown"),
        "fraud_confidence": float(rec.get("fraud_confidence", 0.0) or 0.0),
        "entities": rec.get("entities", {}),
        "metadata": rec.get("metadata", {}),
    }


def main() -> None:
    args = parse_args()
    bundle_path = args.input
    if not bundle_path.exists():
        raise SystemExit(f"Bundle file not found: {bundle_path}")

    pipeline = IngestPipeline()

    count = 0
    for i, rec in enumerate(iter_jsonl(bundle_path), start=1):
        if args.limit and count >= args.limit:
            break
        mapped = map_bundle_record(rec)
        pipeline.ingest_classified_case(mapped)
        count += 1
        if count % 100 == 0:
            print(f"Ingested {count} records...")

    print(f"✅ Ingest complete. Total records ingested: {count}")


if __name__ == "__main__":
    main()
