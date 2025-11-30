#!/usr/bin/env python
"""Utility for asserting ingestion run metrics after a smoke test."""

from __future__ import annotations

import argparse
import sys
from typing import Any, Mapping

import sqlalchemy as sa

from i4g.settings import get_settings
from i4g.store import sql as sql_schema
from i4g.store.sql import build_engine


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Return CLI arguments describing the run selection and expectations.

    Args:
        argv: Optional list of CLI arguments. When ``None``, defaults to ``sys.argv``.

    Returns:
        Parsed :class:`argparse.Namespace` containing CLI options.
    """

    parser = argparse.ArgumentParser(
        description="Validate an ingestion_runs row against expected metrics",
    )
    parser.add_argument("--run-id", help="Explicit run_id to inspect instead of the latest run", default=None)
    parser.add_argument("--dataset", help="Filter runs to a specific dataset before selecting the latest", default=None)
    parser.add_argument(
        "--status",
        help="Expected run status (defaults to 'succeeded')",
        default="succeeded",
    )
    parser.add_argument(
        "--expect-case-count",
        type=int,
        help="Exact case_count expected for the run",
        default=None,
    )
    parser.add_argument(
        "--min-case-count",
        type=int,
        help="Minimum acceptable case_count",
        default=None,
    )
    parser.add_argument(
        "--expect-sql-writes",
        type=int,
        help="Exact sql_writes expected",
        default=None,
    )
    parser.add_argument(
        "--expect-firestore-writes",
        type=int,
        help="Exact firestore_writes expected",
        default=None,
    )
    parser.add_argument(
        "--expect-vertex-writes",
        type=int,
        help="Exact vertex_writes expected",
        default=None,
    )
    parser.add_argument(
        "--max-retry-count",
        type=int,
        help="Upper bound for retry_count (omit to allow any value)",
        default=None,
    )
    parser.add_argument(
        "--require-vector-enabled",
        action="store_true",
        help="Assert that vector_enabled is truthy",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Permit 'partial' status runs (overrides --status)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the selected row as a JSON-ish dict",
    )
    return parser.parse_args(argv)


def fetch_run(args: argparse.Namespace) -> Mapping[str, Any]:
    """Select a single ``ingestion_runs`` row based on CLI filters.

    Args:
        args: Parsed CLI arguments describing the desired run and expectations.

    Returns:
        Mapping of column names to values for the selected row.

    Raises:
        SystemExit: If no run matches the supplied filters.
    """

    # Ensure settings are loaded so build_engine reflects env overrides.
    resolved_settings = get_settings()
    engine = build_engine(settings=resolved_settings)

    stmt = sa.select(sql_schema.ingestion_runs)
    if args.run_id:
        stmt = stmt.where(sql_schema.ingestion_runs.c.run_id == args.run_id)
    if args.dataset:
        stmt = stmt.where(sql_schema.ingestion_runs.c.dataset == args.dataset)
    stmt = stmt.order_by(sql_schema.ingestion_runs.c.created_at.desc()).limit(1)

    with engine.connect() as conn:
        row = conn.execute(stmt).mappings().first()

    if row is None:
        target = args.run_id or args.dataset or "latest"
        raise SystemExit(f"No ingestion run found for target={target}")

    return row


def validate(row: Mapping[str, Any], args: argparse.Namespace) -> list[str]:
    """Return validation failures for the selected row.

    Args:
        row: Selected ingestion run row.
        args: CLI arguments containing expectation thresholds.

    Returns:
        List of string error messages (empty when validation succeeds).
    """

    errors: list[str] = []
    status = row["status"]
    expected_status = args.status
    if args.allow_partial and expected_status == "succeeded":
        expected_status = "partial"
    if expected_status and status != expected_status:
        errors.append(f"status expected={expected_status} actual={status}")

    if args.expect_case_count is not None and row["case_count"] != args.expect_case_count:
        errors.append(f"case_count expected={args.expect_case_count} actual={row['case_count']}")
    if args.min_case_count is not None and row["case_count"] < args.min_case_count:
        errors.append(f"case_count minimum={args.min_case_count} actual={row['case_count']}")
    if args.expect_sql_writes is not None and row["sql_writes"] != args.expect_sql_writes:
        errors.append(f"sql_writes expected={args.expect_sql_writes} actual={row['sql_writes']}")
    if args.expect_firestore_writes is not None and row["firestore_writes"] != args.expect_firestore_writes:
        errors.append(f"firestore_writes expected={args.expect_firestore_writes} actual={row['firestore_writes']}")
    if args.expect_vertex_writes is not None and row["vertex_writes"] != args.expect_vertex_writes:
        errors.append(f"vertex_writes expected={args.expect_vertex_writes} actual={row['vertex_writes']}")
    max_retry_count = args.max_retry_count
    if max_retry_count is not None and row["retry_count"] > max_retry_count:
        errors.append(f"retry_count exceeded max={max_retry_count} actual={row['retry_count']}")
    if args.require_vector_enabled and not bool(row["vector_enabled"]):
        errors.append("vector_enabled expected=True actual=False")

    return errors


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional list of CLI arguments.

    Returns:
        Zero on success, non-zero when validation fails.
    """

    args = parse_args(argv)
    row = fetch_run(args)

    if args.verbose:
        print({key: row[key] for key in row.keys()})

    errors = validate(row, args)
    if errors:
        print("❌ Ingestion run validation failed:")
        for message in errors:
            print(f"  - {message}")
        return 1

    summary = (
        f"✅ run_id={row['run_id']} dataset={row['dataset']} status={row['status']} "
        f"cases={row['case_count']} sql={row['sql_writes']} firestore={row['firestore_writes']} "
        f"vertex={row['vertex_writes']} retries={row['retry_count']}"
    )
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
