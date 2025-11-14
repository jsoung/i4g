#!/usr/bin/env python3
"""Utility for copying legacy Azure SQL intake tables into Firestore staging collections.

Run this script after exporting firewall access for your IP. It supports Active Directory
authentication (using ``DefaultAzureCredential``) or SQL auth connection strings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, Iterator, List, Optional

import pyodbc
from azure.identity import DefaultAzureCredential
from google.cloud import firestore

# pyodbc constant for passing an Azure AD access token into the connection.
SQL_COPT_SS_ACCESS_TOKEN = 1256  # value documented by Microsoft / pyodbc


@dataclass
class TableConfig:
    name: str
    firestore_collection: str
    primary_key: Optional[str]
    sort_key: Optional[str] = None


TABLE_CONFIGS: Dict[str, TableConfig] = {
    "dbo.intake_form_data": TableConfig(
        name="dbo.intake_form_data",
        firestore_collection="intake_forms_staging",
        primary_key="id",
        sort_key="submitted_at",
    ),
    "dbo.intake_form_data_last_processed": TableConfig(
        name="dbo.intake_form_data_last_processed",
        firestore_collection="intake_pipeline_meta",
        primary_key=None,
    ),
    "dbo.groupsio_message_data": TableConfig(
        name="dbo.groupsio_message_data",
        firestore_collection="groupsio_message_cache",
        primary_key="id",
        sort_key="timestamp",
    ),
}


@dataclass
class TableStats:
    name: str
    source_count: int = 0
    checksum: hashlib._hashlib.HASH = field(default_factory=lambda: hashlib.sha256())
    committed_docs: int = 0

    def update(self, row: Dict[str, Any]) -> None:
        serialized = json.dumps(row, sort_keys=True).encode("utf-8")
        self.checksum.update(serialized)
        self.source_count += 1

    def as_dict(self) -> Dict[str, Any]:
        return {
            "table": self.name,
            "source_rows": self.source_count,
            "committed_docs": self.committed_docs,
            "checksum": self.checksum.hexdigest(),
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy Azure SQL intake tables into Firestore staging collections",
    )
    parser.add_argument(
        "--connection-string",
        required=True,
        help="ODBC connection string for the Azure SQL database.",
    )
    parser.add_argument(
        "--use-aad",
        action="store_true",
        help="Use DefaultAzureCredential to fetch an Azure AD access token for the connection.",
    )
    parser.add_argument(
        "--aad-user",
        help="User principal name to set as UID when using Azure AD tokens (required if not embedded in the connection string).",
    )
    parser.add_argument(
        "--firestore-project",
        required=True,
        help="Target Google Cloud project ID for Firestore writes.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Number of documents to write per Firestore batch (<= 500).",
    )
    parser.add_argument(
        "--tables",
        nargs="*",
        default=list(TABLE_CONFIGS.keys()),
        choices=list(TABLE_CONFIGS.keys()),
        help="Specific tables to migrate (defaults to all intake tables).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch rows and log stats without writing to Firestore.",
    )
    parser.add_argument(
        "--report",
        help="Optional path to write a JSON summary report.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args()


def get_sql_connection(connection_string: str, use_aad: bool, aad_user: Optional[str]) -> pyodbc.Connection:
    if use_aad:
        credential = DefaultAzureCredential()
        token = credential.get_token("https://database.windows.net/.default")
        token_bytes = token.token.encode("utf-16-le")
        attrs_before = {SQL_COPT_SS_ACCESS_TOKEN: token_bytes}
        if aad_user and "uid=" not in connection_string.lower():
            connection_string = f"{connection_string};Uid={aad_user}"
        return pyodbc.connect(connection_string, attrs_before=attrs_before)
    return pyodbc.connect(connection_string)


def fetch_rows(conn: pyodbc.Connection, table: str, fetch_size: int = 1000) -> Iterator[Dict[str, Any]]:
    query = f"SELECT * FROM {table}"
    cursor = conn.cursor()
    cursor.execute(query)
    columns = [desc[0] for desc in cursor.description]
    while True:
        rows = cursor.fetchmany(fetch_size)
        if not rows:
            break
        for row in rows:
            yield dict(zip(columns, row))


def sanitize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def sanitize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {k: sanitize_value(v) for k, v in row.items() if v is not None}


def commit_batch(batch: firestore.WriteBatch) -> None:
    batch.commit()


def migrate_table(
    conn: pyodbc.Connection,
    client: firestore.Client,
    config: TableConfig,
    batch_size: int,
    dry_run: bool,
) -> TableStats:
    stats = TableStats(name=config.name)
    batch = client.batch()
    batch_count = 0
    collection_ref = client.collection(config.firestore_collection)

    for raw_row in fetch_rows(conn, config.name):
        sanitized = sanitize_row(raw_row)
        stats.update(sanitized)
        doc_id = None
        if config.primary_key:
            pk_value = sanitized.get(config.primary_key)
            if pk_value is None:
                logging.warning("Skipping row missing primary key %s in %s", config.primary_key, config.name)
                continue
            doc_id = str(pk_value)

        if not dry_run:
            doc_ref = collection_ref.document(doc_id) if doc_id else collection_ref.document()
            batch.set(doc_ref, sanitized)
            batch_count += 1
            if batch_count >= batch_size:
                batch.commit()
                stats.committed_docs += batch_count
                batch = client.batch()
                batch_count = 0

    if not dry_run and batch_count:
        batch.commit()
        stats.committed_docs += batch_count

    return stats


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))

    if args.use_aad and "uid=" not in args.connection_string.lower() and not args.aad_user:
        raise SystemExit("When --use-aad is set, provide --aad-user or include UID=... in the connection string.")

    logging.info("Connecting to Azure SQL...")
    conn = get_sql_connection(args.connection_string, args.use_aad, args.aad_user)
    try:
        logging.info("Connecting to Firestore project %s", args.firestore_project)
        client = firestore.Client(project=args.firestore_project)

        summaries: List[Dict[str, Any]] = []
        for table_name in args.tables:
            config = TABLE_CONFIGS[table_name]
            logging.info("Migrating table %s -> collection %s", config.name, config.firestore_collection)
            stats = migrate_table(conn, client, config, args.batch_size, args.dry_run)
            summaries.append(stats.as_dict())
            logging.info(
                "Table %s processed %s rows (checksum=%s)",
                config.name,
                stats.source_count,
                stats.checksum.hexdigest(),
            )

        if args.report:
            logging.info("Writing report to %s", args.report)
            with open(args.report, "w", encoding="utf-8") as fh:
                json.dump(summaries, fh, indent=2)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
