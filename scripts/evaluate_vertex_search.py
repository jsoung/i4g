#!/usr/bin/env python3
"""Evaluate Vertex AI Search relevance against predefined scenarios."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.cloud import discoveryengine_v1beta as discoveryengine
from google.protobuf import json_format

LOGGER = logging.getLogger(__name__)


@dataclass
class Scenario:
    name: str
    query: str
    filter_expression: str | None = None
    boost_json: str | None = None
    page_size: int = 10
    expected_ids: list[str] | None = None
    expected_labels: list[str] | None = None
    expected_tags: list[str] | None = None
    pass_k: int = 3

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Scenario":
        expected_ids = payload.get("expected_ids")
        expected_labels = payload.get("expected_labels")
        expected_tags = payload.get("expected_tags")

        return cls(
            name=payload["name"],
            query=payload["query"],
            filter_expression=payload.get("filter") or payload.get("filter_expression"),
            boost_json=payload.get("boost_json"),
            page_size=int(payload.get("page_size", 10)),
            expected_ids=list(expected_ids) if expected_ids else None,
            expected_labels=list(expected_labels) if expected_labels else None,
            expected_tags=list(expected_tags) if expected_tags else None,
            pass_k=int(payload.get("pass_k", 3)),
        )


DEFAULT_SCENARIOS: list[Scenario] = [
    Scenario(
        name="Wallet verification spike",
        query="suspicious withdrawal",
        filter_expression='tags: ANY("account-security")',
        expected_labels=["wallet_verification"],
        pass_k=5,
        page_size=10,
    ),
    Scenario(
        name="Romance visa pretext",
        query="immigration fee",
        filter_expression='tags: ANY("romance")',
        expected_labels=["romance_bitcoin"],
        pass_k=5,
        page_size=10,
    ),
    Scenario(
        name="Investment pump room",
        query="liquidity injection on radiant",
        filter_expression='tags: ANY("investment")',
        expected_labels=["investment_group"],
        pass_k=5,
        page_size=10,
    ),
    Scenario(
        name="Tech support remote access",
        query="license expired teamviewer",
        filter_expression='tags: ANY("tech_support_scam")',
        expected_labels=["tech_support"],
        pass_k=5,
        page_size=10,
    ),
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project",
        required=True,
        help="Google Cloud project that owns the Discovery data store.",
    )
    parser.add_argument(
        "--location",
        default="global",
        help="Discovery location (default: global).",
    )
    parser.add_argument(
        "--data-store-id",
        required=True,
        help="Discovery data store identifier.",
    )
    parser.add_argument(
        "--serving-config-id",
        default="default_search",
        help="Serving config identifier (default: default_search).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional JSON file containing an array of evaluation scenarios.",
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
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        return [_convert_struct(value) for value in data]
    return data


def load_scenarios(path: Path | None) -> list[Scenario]:
    if path is None:
        return DEFAULT_SCENARIOS

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        msg = "Scenario config must be a list of objects."
        raise SystemExit(msg)
    scenarios = [Scenario.from_dict(entry) for entry in payload]
    return scenarios


def build_request(args: argparse.Namespace, scenario: Scenario) -> discoveryengine.SearchRequest:
    request = discoveryengine.SearchRequest(
        serving_config=discoveryengine.SearchServiceClient.serving_config_path(
            project=args.project,
            location=args.location,
            data_store=args.data_store_id,
            serving_config=args.serving_config_id,
        ),
        query=scenario.query,
        page_size=scenario.page_size,
    )
    if scenario.filter_expression:
        request.filter = scenario.filter_expression
    if scenario.boost_json:
        boost_spec = discoveryengine.SearchRequest.BoostSpec()
        json_format.ParseDict(json.loads(scenario.boost_json), boost_spec._pb)
        request.boost_spec = boost_spec
    return request


def evaluate_scenario(
    client: discoveryengine.SearchServiceClient, args: argparse.Namespace, scenario: Scenario
) -> tuple[bool, int | None, list[dict[str, Any]]]:
    request = build_request(args, scenario)
    LOGGER.debug("Scenario %s request: %s", scenario.name, request)

    results: list[dict[str, Any]] = []
    for index, result in enumerate(client.search(request=request), start=1):
        document = result.document
        struct: dict[str, Any] = {}
        if document.json_data:
            try:
                struct = json.loads(document.json_data)
            except json.JSONDecodeError:
                LOGGER.debug("Failed to decode json_data for document %s", document.id)
        elif document.struct_data:
            struct = _convert_struct(document.struct_data)

        tags = struct.get("tags") if isinstance(struct.get("tags"), list) else []
        label = struct.get("ground_truth_label")
        results.append(
            {
                "rank": index,
                "id": document.id,
                "summary": struct.get("summary") or document.title,
                "label": label,
                "tags": tags,
            }
        )

    match_rank: int | None = None
    for item in results:
        rank = item["rank"]
        doc_id = item["id"]
        label = item.get("label")
        tags = item.get("tags") or []

        matches_id = scenario.expected_ids and doc_id in scenario.expected_ids
        matches_label = scenario.expected_labels and label in scenario.expected_labels
        matches_tags = scenario.expected_tags and any(tag in scenario.expected_tags for tag in tags)

        if matches_id or matches_label or matches_tags:
            match_rank = rank
            break

    passed = match_rank is not None and match_rank <= scenario.pass_k
    return passed, match_rank, results


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    scenarios = load_scenarios(args.config)
    client = discoveryengine.SearchServiceClient()

    total = len(scenarios)
    passes = 0
    worst_rank: int | None = None

    for scenario in scenarios:
        passed, match_rank, results = evaluate_scenario(client, args, scenario)
        status = "PASS" if passed else "FAIL"
        indicator = "✅" if passed else "❌"
        headline = f"{indicator} {status} — {scenario.name}"
        print(headline)
        if match_rank is None:
            print("    No matching document found in top %d results." % len(results))
        else:
            print(f"    First match at rank {match_rank}; pass_k={scenario.pass_k}")
            worst_rank = max(worst_rank or match_rank, match_rank)

        for item in results[: scenario.pass_k]:
            tags = ", ".join(item.get("tags") or [])
            label = item.get("label") or "<unknown>"
            summary = item.get("summary") or "<no summary>"
            print(f"      #{item['rank']}: id={item['id']} label={label} tags={tags}")
            print(f"           {summary}")
        print()

        if passed:
            passes += 1

    print("Summary: %d/%d scenarios passed" % (passes, total))
    if worst_rank is not None:
        print(f"Worst passing rank: {worst_rank}")

    return 0 if passes == total else 1


if __name__ == "__main__":
    sys.exit(main())
