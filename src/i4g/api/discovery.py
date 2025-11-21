"""FastAPI router exposing Discovery Engine search."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from i4g.services.discovery import DiscoverySearchParams, get_default_discovery_params, run_discovery_search

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.get("/search")
def discovery_search(
    query: str = Query(..., min_length=1, description="User-provided Discovery Engine query string."),
    page_size: int = Query(10, ge=1, le=50, description="Number of results to return."),
    project: str | None = Query(None, description="Optional override for the Discovery Engine project."),
    location: str | None = Query(None, description="Optional override for the Discovery Engine location."),
    data_store_id: str | None = Query(None, description="Optional override for the data store ID."),
    serving_config_id: str | None = Query(None, description="Optional override for the serving config."),
    filter_expression: str | None = Query(None, alias="filter", description="Discovery Engine filter expression."),
    boost_json: str | None = Query(None, alias="boost", description="JSON BoostSpec payload."),
):
    """Execute a Discovery Engine search using shared i4g defaults."""

    try:
        params = get_default_discovery_params(query=query, page_size=page_size)
    except RuntimeError as exc:  # pragma: no cover - configuration errors surface to clients
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if project:
        params.project = project
    if location:
        params.location = location
    if data_store_id:
        params.data_store_id = data_store_id
    if serving_config_id:
        params.serving_config_id = serving_config_id
    if filter_expression:
        params.filter_expression = filter_expression
    if boost_json:
        params.boost_json = boost_json

    try:
        return run_discovery_search(params)
    except RuntimeError as exc:  # pragma: no cover - surfaces backend errors
        raise HTTPException(status_code=502, detail=str(exc)) from exc


__all__ = ["router"]
