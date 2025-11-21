"""Shared helpers for Google Discovery Engine search flows."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence

from google.cloud import discoveryengine_v1beta as discoveryengine
from google.protobuf import json_format

from i4g.settings import get_settings


@dataclass(frozen=True)
class DiscoveryDefaults:
    """Resolved environment defaults used for Discovery Engine queries."""

    project: str
    location: str
    data_store_id: str
    serving_config_id: str


@dataclass
class DiscoverySearchParams:
    """Normalized search inputs accepted by :func:`run_discovery_search`."""

    query: str
    project: str
    location: str
    data_store_id: str
    serving_config_id: str = "default_search"
    page_size: int = 10
    filter_expression: Optional[str] = None
    boost_json: Optional[str] = None


def _load_defaults() -> DiscoveryDefaults:
    """Resolve Discovery Engine defaults from env vars + settings."""

    settings = get_settings()
    project = os.getenv("I4G_VERTEX_SEARCH_PROJECT") or (settings.vector.vertex_ai_project or "")
    location = os.getenv("I4G_VERTEX_SEARCH_LOCATION") or settings.vector.vertex_ai_location or "global"
    data_store = os.getenv("I4G_VERTEX_SEARCH_DATA_STORE") or ""
    serving_config = os.getenv("I4G_VERTEX_SEARCH_SERVING_CONFIG") or "default_search"

    if not project or not data_store:
        raise RuntimeError(
            "Discovery Engine defaults are missing. Set I4G_VERTEX_SEARCH_PROJECT and "
            "I4G_VERTEX_SEARCH_DATA_STORE environment variables."
        )

    return DiscoveryDefaults(
        project=project,
        location=location,
        data_store_id=data_store,
        serving_config_id=serving_config,
    )


def get_default_discovery_params(query: str, page_size: int = 10) -> DiscoverySearchParams:
    """Return a populated :class:`DiscoverySearchParams` using environment defaults."""

    defaults = _load_defaults()
    return DiscoverySearchParams(
        query=query,
        project=defaults.project,
        location=defaults.location,
        data_store_id=defaults.data_store_id,
        serving_config_id=defaults.serving_config_id,
        page_size=page_size,
    )


def _convert_struct(value: Any) -> Any:
    """Recursively convert protobuf Structs to standard Python types."""

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "items"):
        return {key: _convert_struct(child) for key, child in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_convert_struct(item) for item in value]
    return value


@lru_cache(maxsize=1)
def _search_client() -> discoveryengine.SearchServiceClient:
    """Cache the Discovery Engine client to avoid reconnect overhead."""

    return discoveryengine.SearchServiceClient()


def _parse_boost_spec(boost_json: Optional[str]) -> Optional[discoveryengine.SearchRequest.BoostSpec]:
    """Convert BoostSpec JSON into the protobuf type Discovery Engine expects."""

    if not boost_json:
        return None

    try:
        payload = json.loads(boost_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse BoostSpec JSON: {exc}") from exc

    boost_spec = discoveryengine.SearchRequest.BoostSpec()
    json_format.ParseDict(payload, boost_spec._pb)
    return boost_spec


def run_discovery_search(params: DiscoverySearchParams) -> Dict[str, Any]:
    """Execute a Discovery Engine search and return structured results.

    Args:
        params: Normalized search inputs.

    Returns:
        Dictionary containing the formatted results plus response metadata.
    """

    client = _search_client()
    serving_config = client.serving_config_path(
        project=params.project,
        location=params.location,
        data_store=params.data_store_id,
        serving_config=params.serving_config_id or "default_search",
    )

    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=params.query,
        page_size=max(1, min(params.page_size or 10, 50)),
    )

    if params.filter_expression:
        request.filter = params.filter_expression

    boost_spec = _parse_boost_spec(params.boost_json)
    if boost_spec:
        request.boost_spec = boost_spec

    try:
        search_response = client.search(request=request)
    except Exception as exc:  # pragma: no cover - network/backend failure
        raise RuntimeError(f"Discovery Engine search failed: {exc}") from exc

    formatted: List[Dict[str, Any]] = []
    raw_results = list(search_response)
    for rank, result in enumerate(raw_results, start=1):
        document = result.document
        struct_data: Dict[str, Any] = {}

        if document.json_data:
            try:
                struct_data = json.loads(document.json_data)
            except json.JSONDecodeError:
                struct_data = _convert_struct(document.struct_data) if document.struct_data else {}
        elif document.struct_data:
            struct_data = _convert_struct(document.struct_data)

        summary = (
            struct_data.get("summary")
            or struct_data.get("text")
            or struct_data.get("title")
            or getattr(document, "title", "")
        )

        tags = struct_data.get("tags") or []
        label = struct_data.get("ground_truth_label")
        raw_payload = json_format.MessageToDict(result._pb)  # type: ignore[attr-defined]

        formatted.append(
            {
                "rank": rank,
                "document_id": document.id,
                "document_name": document.name,
                "summary": summary,
                "label": label,
                "tags": tags,
                "source": struct_data.get("source") or struct_data.get("index_type"),
                "index_type": struct_data.get("index_type"),
                "struct": struct_data,
                "rank_signals": raw_payload.get("rankSignals", {}),
                "raw": raw_payload,
            }
        )

    return {
        "results": formatted,
        "total_size": getattr(search_response, "total_size", len(formatted)),
        "next_page_token": getattr(search_response, "next_page_token", ""),
    }


__all__ = [
    "DiscoverySearchParams",
    "get_default_discovery_params",
    "run_discovery_search",
]
