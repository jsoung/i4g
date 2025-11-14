#!/usr/bin/env python3
"""Utility to copy Azure Blob Storage containers into Google Cloud Storage buckets.

Usage example:

    python scripts/migration/azure_blob_to_gcs.py \
        --connection-string "$AZURE_STORAGE_CONNECTION_STRING" \
        --container evidence=gs://i4g-evidence-dev/intake \
        --container reports=gs://i4g-reports-dev \
        --dry-run

The script handles metadata preservation (content-type, cache-control, custom metadata) and
produces optional JSON reports with counts and checksums.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Tuple
from urllib.parse import urlparse

from azure.storage.blob import BlobClient, BlobServiceClient
from google.cloud import storage


@dataclass
class ContainerTarget:
    container: str
    bucket: str
    prefix: str


@dataclass
class TransferStats:
    blobs_seen: int = 0
    blobs_copied: int = 0
    bytes_transferred: int = 0
    skipped_existing: int = 0
    failures: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        return {
            "blobs_seen": self.blobs_seen,
            "blobs_copied": self.blobs_copied,
            "bytes_transferred": self.bytes_transferred,
            "skipped_existing": self.skipped_existing,
            "failures": self.failures,
        }


def parse_container_mapping(values: Iterable[str]) -> Dict[str, ContainerTarget]:
    mapping: Dict[str, ContainerTarget] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Container mapping must be NAME=gs://bucket[/prefix]; got '{value}'")
        name, target = value.split("=", 1)
        parsed = urlparse(target)
        if parsed.scheme != "gs":
            raise ValueError(f"Target must be a gs:// URI; got '{target}'")
        bucket = parsed.netloc
        prefix = parsed.path.lstrip("/")
        mapping[name] = ContainerTarget(container=name, bucket=bucket, prefix=prefix)
    if not mapping:
        raise ValueError("At least one --container mapping is required")
    return mapping


def format_destination_path(target: ContainerTarget, blob_name: str) -> str:
    if target.prefix:
        return f"{target.prefix.rstrip('/')}/{blob_name}"
    return blob_name


def md5_matches(gcs_blob: storage.Blob, source_md5: Optional[bytes]) -> bool:
    if not source_md5 or not gcs_blob.exists():
        return False
    # GCS stores md5_hash as base64-encoded string
    source_b64 = base64.b64encode(source_md5).decode("utf-8")
    return gcs_blob.md5_hash == source_b64


def copy_blob(
    blob_client: BlobClient,
    gcs_blob: storage.Blob,
    overwrite: bool,
    temp_dir: str,
) -> Tuple[bool, int]:
    """Download Azure blob to temp file and upload into GCS.

    Returns (copied?, bytes_transferred).
    """
    azure_props = blob_client.get_blob_properties()
    if gcs_blob.exists():
        if not overwrite and md5_matches(gcs_blob, azure_props.content_settings.content_md5):
            return False, 0
        if not overwrite:
            logging.warning(
                "Destination object %s exists with differing checksum; rerun with --overwrite to replace", gcs_blob.name
            )
            return False, 0

    download = blob_client.download_blob()
    with tempfile.NamedTemporaryFile(dir=temp_dir) as tmp:
        download.readinto(tmp)
        tmp.flush()
        tmp.seek(0)
        gcs_blob.metadata = azure_props.metadata or {}
        if azure_props.content_settings.content_type:
            gcs_blob.content_type = azure_props.content_settings.content_type
        if azure_props.content_settings.content_encoding:
            gcs_blob.content_encoding = azure_props.content_settings.content_encoding
        if azure_props.content_settings.cache_control:
            gcs_blob.cache_control = azure_props.content_settings.cache_control
        gcs_blob.upload_from_file(tmp)
    size = azure_props.size or 0
    return True, size


def migrate_container(
    service_client: BlobServiceClient,
    storage_client: storage.Client,
    target: ContainerTarget,
    dry_run: bool,
    overwrite: bool,
    temp_dir: str,
) -> TransferStats:
    stats = TransferStats()
    container_client = service_client.get_container_client(target.container)
    bucket = storage_client.bucket(target.bucket)

    logging.info("Scanning container '%s' -> bucket '%s' (prefix='%s')", target.container, target.bucket, target.prefix)
    for blob in container_client.list_blobs():
        stats.blobs_seen += 1
        destination_path = format_destination_path(target, blob.name)
        gcs_blob = bucket.blob(destination_path)

        if dry_run:
            if gcs_blob.exists():
                stats.skipped_existing += 1
            continue

        try:
            copied, size = copy_blob(container_client.get_blob_client(blob.name), gcs_blob, overwrite, temp_dir)
            if copied:
                stats.blobs_copied += 1
                stats.bytes_transferred += size
            else:
                stats.skipped_existing += 1
        except Exception as exc:  # noqa: BLE001
            logging.exception("Failed to copy blob '%s'", blob.name)
            stats.failures[blob.name] = str(exc)
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy Azure Blob containers into GCS buckets")
    parser.add_argument(
        "--connection-string",
        default=os.environ.get("AZURE_STORAGE_CONNECTION_STRING"),
        help="Azure Storage account connection string (or set AZURE_STORAGE_CONNECTION_STRING).",
    )
    parser.add_argument(
        "--container",
        action="append",
        dest="containers",
        default=[],
        help="Mapping in the form name=gs://bucket[/prefix]. May be repeated.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing GCS objects even if checksums match.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List objects and detect skips without copying data.",
    )
    parser.add_argument(
        "--temp-dir",
        default=None,
        help="Temporary directory for staging downloads (defaults to system temp).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    parser.add_argument(
        "--report",
        help="Optional path to write a JSON report summarising per-container results.",
    )
    args = parser.parse_args()
    if not args.connection_string:
        parser.error("--connection-string is required (or set AZURE_STORAGE_CONNECTION_STRING)")
    if not args.containers:
        parser.error("At least one --container mapping must be provided")
    return args


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    targets = parse_container_mapping(args.containers)
    service_client = BlobServiceClient.from_connection_string(args.connection_string)
    storage_client = storage.Client()

    report: Dict[str, Dict[str, object]] = {}

    with tempfile.TemporaryDirectory(dir=args.temp_dir) as temp_dir:
        for container_name, target in targets.items():
            stats = migrate_container(
                service_client,
                storage_client,
                target,
                dry_run=args.dry_run,
                overwrite=args.overwrite,
                temp_dir=temp_dir,
            )
            logging.info(
                "Container %s: seen=%d copied=%d skipped=%d bytes=%d failures=%d",
                container_name,
                stats.blobs_seen,
                stats.blobs_copied,
                stats.skipped_existing,
                stats.bytes_transferred,
                len(stats.failures),
            )
            report[container_name] = stats.as_dict()

    if args.report:
        logging.info("Writing report to %s", args.report)
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)


if __name__ == "__main__":
    main()
