#!/usr/bin/env python3
"""Run the weekly Azure → GCP refresh (SQL, blobs, search indexes).

This orchestrator stitches together the existing migration utilities so we can
refresh the MVP datasets on a predictable cadence or wire the flow into a Cloud
Scheduler + Cloud Run job.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple
from urllib.parse import urlparse

from azure_blob_to_gcs import parse_container_mapping  # type: ignore
from google.cloud import storage

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SCRIPTS_DIR = Path(__file__).resolve().parent

DEFAULT_BLOB_CONTAINERS = (
    "intake-form-attachments=gs://i4g-evidence-dev/forms",
    "groupsio-attachments=gs://i4g-evidence-dev/groupsio",
)
DEFAULT_SEARCH_INDEXES = ("groupsio-search", "intake-form-search")
DEFAULT_SEARCH_PREFIX = "gs://i4g-migration-artifacts-dev/search"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the weekly Azure → GCP refresh")
    parser.add_argument(
        "--run-date",
        help="Override run date (YYYYMMDD). Defaults to UTC today.",
    )
    parser.add_argument(
        "--sql-connection-string",
        default=os.environ.get("AZURE_SQL_CONNECTION_STRING"),
        help="ODBC connection string for Azure SQL (defaults to AZURE_SQL_CONNECTION_STRING).",
    )
    parser.add_argument(
        "--firestore-project",
        default="i4g-dev",
        help="Firestore project to receive structured data.",
    )
    parser.add_argument(
        "--blob-connection-string",
        default=os.environ.get("AZURE_STORAGE_CONNECTION_STRING"),
        help="Azure Storage account connection string (defaults to AZURE_STORAGE_CONNECTION_STRING).",
    )
    parser.add_argument(
        "--blob-container",
        action="append",
        dest="blob_containers",
        default=list(DEFAULT_BLOB_CONTAINERS),
        help="Container mapping name=gs://bucket/prefix (repeatable).",
    )
    parser.add_argument(
        "--search-endpoint",
        default=os.environ.get("AZURE_SEARCH_ENDPOINT"),
        help="Azure Cognitive Search endpoint (defaults to AZURE_SEARCH_ENDPOINT).",
    )
    parser.add_argument(
        "--search-admin-key",
        default=os.environ.get("AZURE_SEARCH_ADMIN_KEY"),
        help="Azure Cognitive Search admin key (defaults to AZURE_SEARCH_ADMIN_KEY).",
    )
    parser.add_argument(
        "--search-index",
        action="append",
        dest="search_indexes",
        default=list(DEFAULT_SEARCH_INDEXES),
        help="Search index to refresh (repeatable). Defaults to all supported indexes.",
    )
    parser.add_argument(
        "--search-artifact-prefix",
        default=DEFAULT_SEARCH_PREFIX,
        help="GCS prefix (gs://bucket/path) for storing search export artifacts.",
    )
    parser.add_argument(
        "--vertex-project",
        default="i4g-dev",
        help="GCP project for Discovery imports.",
    )
    parser.add_argument(
        "--vertex-location",
        default="global",
        help="Discovery location (defaults to global).",
    )
    parser.add_argument(
        "--vertex-collection-id",
        default="default_collection",
        help="Discovery collection ID (default_collection).",
    )
    parser.add_argument(
        "--vertex-data-store-id",
        default="retrieval-poc",
        help="Discovery data store ID (e.g. retrieval-poc).",
    )
    parser.add_argument(
        "--vertex-branch-id",
        default="default_branch",
        help="Discovery branch ID (default_branch).",
    )
    parser.add_argument(
        "--reconciliation-mode",
        default="INCREMENTAL",
        choices=["INCREMENTAL", "FULL"],
        help="Vertex import reconciliation mode (default: INCREMENTAL).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    parser.add_argument("--skip-sql", action="store_true", help="Skip the Azure SQL → Firestore refresh.")
    parser.add_argument("--skip-blob", action="store_true", help="Skip the Azure Blob → GCS sync.")
    parser.add_argument("--skip-search", action="store_true", help="Skip the search export/import refresh.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity for this orchestrator.",
    )
    parser.add_argument(
        "--child-log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level to pass to child scripts.",
    )

    args = parser.parse_args()

    missing = []
    if not args.sql_connection_string and not args.skip_sql:
        missing.append("--sql-connection-string / AZURE_SQL_CONNECTION_STRING")
    if not args.blob_connection_string and not args.skip_blob:
        missing.append("--blob-connection-string / AZURE_STORAGE_CONNECTION_STRING")
    if not args.search_endpoint and not args.skip_search:
        missing.append("--search-endpoint / AZURE_SEARCH_ENDPOINT")
    if not args.search_admin_key and not args.skip_search:
        missing.append("--search-admin-key / AZURE_SEARCH_ADMIN_KEY")
    if missing:
        parser.error("Missing required configuration: " + ", ".join(missing))

    return args


def format_command(cmd: Sequence[str], redacted_flags: Iterable[str] | None = None) -> str:
    redacted_flags = set(redacted_flags or [])
    rendered: List[str] = []
    for idx, token in enumerate(cmd):
        if token in redacted_flags:
            rendered.append(f"{token} <redacted>")
            continue
        if idx > 0 and cmd[idx - 1] in redacted_flags:
            # Value for a sensitive flag.
            rendered.append("<redacted>")
            continue
        rendered.append(shlex.quote(token))
    return " ".join(rendered)


def run_command(
    cmd: Sequence[str],
    *,
    dry_run: bool,
    redacted_flags: Iterable[str] | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str] | None:
    logging.info("Executing: %s", format_command(cmd, redacted_flags))
    if dry_run:
        logging.info("Dry-run mode enabled; command skipped.")
        return None

    try:
        result = subprocess.run(
            cmd,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        stdout = (exc.stdout or "").strip()
        stderr = (exc.stderr or "").strip()
        if stdout:
            logging.error("Command stdout:\n%s", stdout)
        if stderr:
            logging.error("Command stderr:\n%s", stderr)
        raise

    if capture_output:
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if stdout:
            logging.info(stdout)
        if stderr:
            logging.warning(stderr)
    return result


def split_gcs_uri(uri: str) -> Tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "gs":
        raise ValueError(f"Expected gs:// URI, got '{uri}'")
    return parsed.netloc, parsed.path.lstrip("/")


def upload_files_to_gcs(files: Iterable[Path], destination_prefix: str, dry_run: bool) -> List[str]:
    bucket_name, prefix = split_gcs_uri(destination_prefix)
    client = None if dry_run else storage.Client()
    uploaded: List[str] = []

    for file_path in sorted(files):
        if not file_path.is_file():
            continue
        object_name = f"{prefix.rstrip('/')}/{file_path.name}" if prefix else file_path.name
        gcs_uri = f"gs://{bucket_name}/{object_name}".rstrip("/")
        logging.info("Uploading %s → %s", file_path, gcs_uri)
        if not dry_run:
            assert client is not None  # narrow type for mypy/pyright
            blob = client.bucket(bucket_name).blob(object_name)
            blob.upload_from_filename(str(file_path))
        uploaded.append(gcs_uri)
    return uploaded


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def run_sql_refresh(args: argparse.Namespace, run_date: str) -> dict:
    if args.skip_sql:
        logging.info("Skipping SQL refresh (per flag).")
        return {}

    ensure_directory(DATA_DIR)
    report_path = DATA_DIR / f"intake_migration_report_{run_date}.json"
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "azure_sql_to_firestore.py"),
        "--connection-string",
        args.sql_connection_string,
        "--firestore-project",
        args.firestore_project,
        "--report",
        str(report_path),
        "--log-level",
        args.child_log_level,
    ]

    run_command(cmd, dry_run=args.dry_run, redacted_flags={"--connection-string"})
    return {"report": str(report_path)}


def run_blob_refresh(args: argparse.Namespace, run_date: str) -> dict:
    if args.skip_blob:
        logging.info("Skipping blob refresh (per flag).")
        return {}

    container_mapping = parse_container_mapping(args.blob_containers)
    container_summary = {
        name: {"bucket": target.bucket, "prefix": target.prefix} for name, target in container_mapping.items()
    }
    container_args: List[str] = []
    for entry in args.blob_containers:
        container_args.extend(["--container", entry])

    dry_report = DATA_DIR / f"blob_migration_incremental_{run_date}_dryrun.json"
    full_report = DATA_DIR / f"blob_migration_incremental_{run_date}.json"

    base_cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "azure_blob_to_gcs.py"),
        "--connection-string",
        args.blob_connection_string,
        "--log-level",
        args.child_log_level,
        "--report",
        str(dry_report),
        *container_args,
    ]

    run_command(
        base_cmd + ["--dry-run"],
        dry_run=args.dry_run,
        redacted_flags={"--connection-string"},
    )

    dry_run_summary: dict | None = None
    delta_detected = True
    if not args.dry_run:
        try:
            with dry_report.open("r", encoding="utf-8") as fh:
                dry_run_summary = json.load(fh)
        except FileNotFoundError:
            logging.warning("Dry-run report %s not found; proceeding with live copy.", dry_report)
        except json.JSONDecodeError as exc:
            logging.warning("Failed to parse dry-run report %s (%s); proceeding with live copy.", dry_report, exc)

    if dry_run_summary is not None:
        delta_detected = any(
            (container_stats.get("blobs_seen", 0) - container_stats.get("skipped_existing", 0)) > 0
            for container_stats in dry_run_summary.values()
        )

    summary: dict = {
        "dry_run_report": str(dry_report),
        "containers": container_summary,
    }

    if not delta_detected:
        logging.info("Dry run detected no new or updated blobs; skipping live copy.")
        summary["skipped_live_copy"] = True
        summary["report"] = None
        return summary

    # Update report path for the live run.
    live_cmd = base_cmd.copy()
    report_index = live_cmd.index("--report")
    live_cmd[report_index + 1] = str(full_report)

    run_command(
        live_cmd,
        dry_run=args.dry_run,
        redacted_flags={"--connection-string"},
    )

    summary["report"] = str(full_report)
    summary["skipped_live_copy"] = False
    return summary


def run_search_refresh(args: argparse.Namespace, run_date: str) -> dict:
    if args.skip_search:
        logging.info("Skipping search refresh (per flag).")
        return {}

    export_dir = DATA_DIR / "search_exports" / run_date
    vertex_dir = export_dir / "vertex"
    ensure_directory(export_dir)
    ensure_directory(vertex_dir)

    cmd_export = [
        sys.executable,
        str(SCRIPTS_DIR / "azure_search_export.py"),
        "--endpoint",
        args.search_endpoint,
        "--admin-key",
        args.search_admin_key,
        "--output-dir",
        str(export_dir),
        "--log-level",
        args.child_log_level,
    ]
    if args.search_indexes:
        cmd_export.extend(["--indexes", *args.search_indexes])

    run_command(
        cmd_export,
        dry_run=args.dry_run,
        redacted_flags={"--admin-key"},
    )

    cmd_transform = [
        sys.executable,
        str(SCRIPTS_DIR / "azure_search_to_vertex.py"),
        "--input-dir",
        str(export_dir),
        "--output-dir",
        str(vertex_dir),
        "--log-level",
        args.child_log_level,
    ]
    if args.search_indexes:
        cmd_transform.extend(["--index", *args.search_indexes])

    run_command(cmd_transform, dry_run=args.dry_run)

    prefix_base = args.search_artifact_prefix.rstrip("/")
    azure_prefix = f"{prefix_base}/{run_date}/azure"
    vertex_prefix = f"{prefix_base}/{run_date}/vertex"
    errors_prefix = f"{prefix_base}/{run_date}/errors"

    azure_files = [p for p in export_dir.glob("*") if p.is_file()]
    vertex_files = list(vertex_dir.glob("*.jsonl"))

    uploaded_azure = upload_files_to_gcs(azure_files, azure_prefix, args.dry_run)
    uploaded_vertex = upload_files_to_gcs(vertex_files, vertex_prefix, args.dry_run)

    if not uploaded_vertex:
        logging.warning("No Vertex JSONL files found; skipping import step.")
        return {
            "export_dir": str(export_dir),
            "vertex_dir": str(vertex_dir),
            "azure_artifacts": uploaded_azure,
            "vertex_artifacts": uploaded_vertex,
        }

    cmd_import = [
        sys.executable,
        str(SCRIPTS_DIR / "import_vertex_documents.py"),
        "--project",
        args.vertex_project,
        "--location",
        args.vertex_location,
        "--collection-id",
        args.vertex_collection_id,
        "--data-store-id",
        args.vertex_data_store_id,
        "--branch-id",
        args.vertex_branch_id,
        "--reconciliation-mode",
        args.reconciliation_mode,
        "--error-prefix",
        errors_prefix,
        "--log-level",
        args.child_log_level,
        "--uris",
        *uploaded_vertex,
    ]

    result = run_command(cmd_import, dry_run=args.dry_run, capture_output=True)
    operation_name = None
    if result and result.stdout:
        match = re.search(r"Operation name:\s*(\S+)", result.stdout)
        if match:
            operation_name = match.group(1)

    summary = {
        "export_dir": str(export_dir),
        "vertex_dir": str(vertex_dir),
        "azure_artifacts": uploaded_azure,
        "vertex_artifacts": uploaded_vertex,
        "import_error_prefix": errors_prefix,
    }
    if operation_name:
        summary["import_operation"] = operation_name
    return summary


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    run_date = args.run_date or datetime.utcnow().strftime("%Y%m%d")
    logging.info("Starting weekly refresh for %s", run_date)
    summary: dict = {
        "run_date": run_date,
        "dry_run": args.dry_run,
        "steps": {},
    }

    try:
        summary["steps"]["sql"] = run_sql_refresh(args, run_date)
        summary["steps"]["blob"] = run_blob_refresh(args, run_date)
        summary["steps"]["search"] = run_search_refresh(args, run_date)
    except subprocess.CalledProcessError as exc:
        logging.error("Command failed with code %s", exc.returncode)
        sys.exit(exc.returncode)

    if args.dry_run:
        logging.info("Dry-run complete; summary not written. Summary: %s", json.dumps(summary, indent=2))
        return

    ensure_directory(DATA_DIR)
    summary_path = DATA_DIR / f"weekly_refresh_{run_date}.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    logging.info("Weekly refresh summary:\n%s", json.dumps(summary, indent=2))
    logging.info("Weekly refresh complete; summary written to %s", summary_path)


if __name__ == "__main__":
    main()
