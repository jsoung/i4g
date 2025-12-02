#!/usr/bin/env python3
"""Fetch `/reviews/search/schema` and refresh the docs snapshot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_OUTPUT = Path("docs/examples/reviews_search_schema.json")


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Refresh the cached hybrid search schema snapshot.")
    parser.add_argument(
        "--api-base",
        default=os.environ.get("FASTAPI_BASE", "http://127.0.0.1:8000"),
        help="FastAPI base URL (defaults to FASTAPI_BASE or http://127.0.0.1:8000).",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("I4G_API_KEY"),
        help="API key with analyst scope (defaults to I4G_API_KEY).",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=f"Destination path for the schema payload (defaults to {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation level for the saved snapshot (default: 2).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP request timeout in seconds (default: 30).",
    )
    return parser


def fetch_schema(api_base: str, api_key: str | None, timeout: float) -> Any:
    """Retrieve the hybrid search schema JSON payload from the API."""
    url = f"{api_base.rstrip('/')}/reviews/search/schema"
    request = Request(url)
    request.add_header("Accept", "application/json")
    if api_key:
        request.add_header("X-API-KEY", api_key)

    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            data = response.read()
    except HTTPError as exc:  # pragma: no cover - exercised in integration workflows.
        raise RuntimeError(f"Schema request failed with status {exc.code}: {exc.reason}") from exc
    except URLError as exc:  # pragma: no cover - exercised in integration workflows.
        raise RuntimeError(f"Unable to reach schema endpoint: {exc.reason}") from exc

    return json.loads(data)


def write_schema(payload: Any, output: Path, indent: int) -> None:
    """Persist the schema payload to disk, creating parent folders when needed."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=indent) + "\n", encoding="utf-8")


def main() -> None:
    """Entrypoint for the schema snapshot refresher."""
    parser = build_argument_parser()
    args = parser.parse_args()

    payload = fetch_schema(args.api_base, args.api_key, args.timeout)
    output = Path(args.output)
    write_schema(payload, output, args.indent)
    print(f"Wrote schema snapshot to {output}")


if __name__ == "__main__":
    main()
