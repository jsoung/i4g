#!/usr/bin/env python3
"""Run ad-hoc queries against a Vertex AI Search (Discovery Engine) data store."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence as AbcSequence
from itertools import islice
from typing import Any, Iterable, Sequence

from google.cloud import discoveryengine_v1beta as discoveryengine
from google.protobuf import json_format

LOGGER = logging.getLogger(__name__)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Free-text query string to execute.")
    parser.add_argument(
        "--project",
        required=True,
        help="Google Cloud project that owns the Discovery Engine data store.",
    )
    parser.add_argument(
        "--location",
        default="global",
        help="Discovery Engine location (default: global).",
    )
    parser.add_argument(
        "--data-store-id",
        required=True,
        help="Discovery Engine data store identifier.",
    )
    parser.add_argument(
        "--serving-config-id",
        default="default_search",
        help="Serving config identifier (default: default_search).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=5,
        help="Maximum number of results to return (default: 5).",
    )
    parser.add_argument(
        "--filter",
        dest="filter_expression",
        help="Optional filter expression (see Discovery Engine documentation).",
    )
    parser.add_argument(
        "--boost-json",
        help=("Optional BoostSpec payload expressed as JSON. See SearchRequest.BoostSpec " "for supported keys."),
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw JSON response instead of a compact summary.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args(argv)


def _convert_struct(data: Any) -> Any:
    if isinstance(data, (str, int, float, bool)) or data is None:
        return data
    if hasattr(data, "items"):
        return {key: _convert_struct(value) for key, value in data.items()}
    if isinstance(data, AbcSequence) and not isinstance(data, (str, bytes, bytearray)):
        return [_convert_struct(value) for value in data]
    return data


def _snippet(value: Any, length: int = 120) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text[:length] + ("…" if len(text) > length else "")
    return None


def print_summary(results: Iterable[discoveryengine.SearchResponse.SearchResult]) -> None:
    had_results = False
    for rank, result in enumerate(results, start=1):
        had_results = True
        document = result.document
        struct: dict[str, Any] = {}
        if document.json_data:
            try:
                struct = json.loads(document.json_data)
            except json.JSONDecodeError:
                LOGGER.debug("Failed to decode json_data for document %s", document.id)
        elif document.struct_data:
            struct = _convert_struct(document.struct_data)
        summary = (
            struct.get("summary")
            or struct.get("subject")
            or struct.get("title")
            or _snippet(struct.get("content"))
            or "<no summary>"
        )
        print(f"#{rank}  id={document.id}")
        print(f"    summary: {summary}")
        tags = struct.get("tags")
        if isinstance(tags, list):
            print(f"    tags: {', '.join(tags)}")
        meta_parts: list[str] = []
        source = struct.get("source")
        if isinstance(source, str) and source:
            meta_parts.append(f"source={source}")
        index_type = struct.get("index_type")
        if isinstance(index_type, str) and index_type and index_type != source:
            meta_parts.append(f"index_type={index_type}")
        if meta_parts:
            print(f"    meta: {', '.join(meta_parts)}")
        print()

    if not had_results:
        print("No results returned.")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    client = discoveryengine.SearchServiceClient()
    serving_config = client.serving_config_path(
        project=args.project,
        location=args.location,
        data_store=args.data_store_id,
        serving_config=args.serving_config_id,
    )

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=args.query,
        page_size=args.page_size,
    )

    if args.filter_expression:
        request.filter = args.filter_expression

    if args.boost_json:
        try:
            boost_payload = json.loads(args.boost_json)
        except json.JSONDecodeError as exc:
            msg = f"Failed to parse --boost-json payload: {exc}"
            raise SystemExit(msg) from exc

        boost_spec = discoveryengine.SearchRequest.BoostSpec()
        json_format.ParseDict(boost_payload, boost_spec._pb)
        request.boost_spec = boost_spec

    LOGGER.debug("SearchRequest: %s", request)

    results_iter = client.search(request=request)
    if args.page_size and args.page_size > 0:
        results = list(islice(results_iter, args.page_size))
    else:
        results = list(results_iter)

    if args.raw:
        payload = [json_format.MessageToDict(result._pb) for result in results]  # type: ignore[attr-defined]
        print(json.dumps(payload, indent=2))
    else:
        print_summary(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
