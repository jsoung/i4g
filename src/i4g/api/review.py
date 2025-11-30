"""Review API router.

Endpoints:
- GET /reviews/queue
- GET /reviews/{review_id}
- POST /reviews/           (enqueue)
- POST /reviews/{review_id}/claim
- POST /reviews/{review_id}/annotate
- POST /reviews/{review_id}/decision
- GET /reviews/{review_id}/actions
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from i4g.api.auth import require_token
from i4g.services.hybrid_search import HybridSearchQuery, HybridSearchService, QueryEntityFilter, QueryTimeRange
from i4g.store.retriever import HybridRetriever
from i4g.store.review_store import ReviewStore

# Import the worker task — will be scheduled in background on "accepted"
from i4g.worker.tasks import generate_report_for_case

router = APIRouter()

# Pydantic models for request/response payloads


class EnqueueRequest(BaseModel):
    case_id: str
    priority: Optional[str] = "medium"
    # Optional preview fields for the UI
    text: Optional[str] = None
    classification: Optional[Dict[str, Any]] = None
    entities: Optional[Dict[str, Any]] = None


class DecisionRequest(BaseModel):
    decision: str  # accepted | rejected | needs_more_info
    notes: Optional[str] = None
    auto_generate_report: Optional[bool] = False  # new flag to control auto-generation


class AnnotateRequest(BaseModel):
    annotations: Dict[str, Any]
    notes: Optional[str] = None


class SavedSearchRequest(BaseModel):
    name: str
    params: Dict[str, Any]
    search_id: Optional[str] = None
    favorite: Optional[bool] = False
    tags: Optional[List[str]] = None


class SavedSearchUpdate(BaseModel):
    name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    favorite: Optional[bool] = None
    tags: Optional[List[str]] = None


class SavedSearchCloneRequest(BaseModel):
    search_id: str


class SavedSearchImportRequest(BaseModel):
    name: str
    params: Dict[str, Any]
    favorite: Optional[bool] = False
    search_id: Optional[str] = None
    tags: Optional[List[str]] = None


class TimeRangeModel(BaseModel):
    start: datetime
    end: datetime


class EntityFilterModel(BaseModel):
    type: str
    value: str
    match_mode: Literal["exact", "prefix", "contains"] = "exact"


class HybridSearchRequest(BaseModel):
    text: Optional[str] = None
    classifications: List[str] = Field(default_factory=list)
    datasets: List[str] = Field(default_factory=list)
    case_ids: List[str] = Field(default_factory=list)
    entities: List[EntityFilterModel] = Field(default_factory=list)
    time_range: Optional[TimeRangeModel] = None
    limit: Optional[int] = Field(default=None, ge=1, le=100)
    vector_limit: Optional[int] = Field(default=None, ge=1, le=100)
    structured_limit: Optional[int] = Field(default=None, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class BulkTagUpdateRequest(BaseModel):
    search_ids: List[str]
    add: Optional[List[str]] = None
    remove: Optional[List[str]] = None
    replace: Optional[List[str]] = None


# Dependency factory for store (simple)
def get_store() -> ReviewStore:
    """Return a ReviewStore instance (mounted to default DB path)."""
    return ReviewStore()


def get_retriever() -> HybridRetriever:
    """Return a HybridRetriever instance."""
    return HybridRetriever()


def get_hybrid_search_service() -> HybridSearchService:
    """Return a HybridSearchService instance for dependency injection."""

    return HybridSearchService()


# -----------------------
# Routes
# -----------------------


@router.post("/", summary="Enqueue a case for review")
def enqueue_case(
    payload: EnqueueRequest,
    user=Depends(require_token),
    store: ReviewStore = Depends(get_store),
):
    """Add a case to the review queue."""
    review_id = store.enqueue_case(case_id=payload.case_id, priority=payload.priority)
    # Optionally log that user enqueued it
    store.log_action(
        review_id,
        actor=user["username"],
        action="enqueued",
        payload={"text": payload.text or ""},
    )
    return {"review_id": review_id, "case_id": payload.case_id}


@router.get("/queue", summary="List queued cases")
def list_queue(
    status: str = Query("queued"),
    limit: int = Query(25),
    store: ReviewStore = Depends(get_store),
):
    """List queued cases by status."""
    items = store.get_queue(status=status, limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/search", summary="Search cases across structured/vector stores")
def search_cases(
    text: Optional[str] = Query(None, description="Free-text search for semantic similarity"),
    classification: Optional[str] = Query(None, description="Filter by classification label"),
    case_id: Optional[str] = Query(None, description="Filter by exact case ID"),
    limit: int = Query(5, ge=1, le=50),
    vector_limit: Optional[int] = Query(None, ge=1, le=50),
    structured_limit: Optional[int] = Query(None, ge=1, le=50),
    offset: int = Query(0, ge=0),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of merged results to return"),
    search_service: HybridSearchService = Depends(get_hybrid_search_service),
    user=Depends(require_token),
    store: ReviewStore = Depends(get_store),
):
    """Combine semantic and structured search for analyst triage."""

    payload = HybridSearchRequest(
        text=text,
        classifications=[classification] if classification else [],
        case_ids=[case_id] if case_id else [],
        limit=page_size or limit,
        vector_limit=vector_limit,
        structured_limit=structured_limit,
        offset=offset,
    )
    query = _build_hybrid_query_from_request(payload)
    query_result = search_service.search(query)
    results = query_result["results"]
    search_id = f"search:{uuid.uuid4()}"
    store.log_action(
        review_id="search",
        actor=user["username"],
        action="search",
        payload={
            "search_id": search_id,
            "text": text,
            "classification": classification,
            "case_id": case_id,
            "limit": limit,
            "vector_limit": vector_limit,
            "structured_limit": structured_limit,
            "offset": offset,
            "page_size": page_size,
            "results_count": len(results),
            "total": query_result["total"],
            "vector_hits": query_result.get("vector_hits"),
            "structured_hits": query_result.get("structured_hits"),
        },
    )

    return {
        "results": results,
        "count": len(results),
        "offset": offset,
        "limit": page_size or len(results),
        "total": query_result["total"],
        "vector_hits": query_result.get("vector_hits"),
        "structured_hits": query_result.get("structured_hits"),
        "search_id": search_id,
    }


@router.get("/search/history", summary="List recent search actions")
def search_history(
    limit: int = Query(20, ge=1, le=200),
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    """Return recent search audit entries."""
    actions = store.get_recent_actions(action="search", limit=limit)
    return {"events": actions, "count": len(actions)}


@router.post("/search/query", summary="Execute advanced hybrid search with structured filters")
def search_cases_advanced(
    payload: HybridSearchRequest,
    search_service: HybridSearchService = Depends(get_hybrid_search_service),
    user=Depends(require_token),
    store: ReviewStore = Depends(get_store),
):
    query = _build_hybrid_query_from_request(payload)
    query_result = search_service.search(query)
    search_id = f"search:{uuid.uuid4()}"
    store.log_action(
        review_id="search",
        actor=user["username"],
        action="search",
        payload={
            "search_id": search_id,
            "request": payload.model_dump(),
            "results_count": query_result["count"],
            "total": query_result["total"],
            "vector_hits": query_result.get("vector_hits"),
            "structured_hits": query_result.get("structured_hits"),
        },
    )
    return {**query_result, "search_id": search_id}


@router.get("/search/schema", summary="Describe hybrid search filters for clients")
def get_search_schema(
    search_service: HybridSearchService = Depends(get_hybrid_search_service),
    user=Depends(require_token),
):
    return search_service.schema()


@router.post("/search/saved", summary="Create or update a saved search")
def save_search(
    payload: SavedSearchRequest,
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    try:
        search_id = store.upsert_saved_search(
            payload.name,
            payload.params,
            owner=user.get("username"),
            search_id=payload.search_id,
            favorite=payload.favorite or False,
            tags=payload.tags or [],
        )
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("duplicate_saved_search"):
            owner = "shared"
            if ":" in msg:
                owner_val = msg.split(":", 1)[1]
                owner = owner_val or "shared"
            raise HTTPException(
                status_code=409,
                detail=f"Saved search name already exists (owner={owner})",
            )
        raise
    return {"search_id": search_id}


@router.get("/search/saved", summary="List saved searches")
def list_saved_searches(
    limit: int = Query(50, ge=1, le=200),
    owner_only: bool = Query(False, description="If true, only return searches owned by the caller"),
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    owner = user.get("username") if owner_only else None
    items = store.list_saved_searches(owner=owner, limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/search/tag-presets", summary="List tag presets derived from saved searches")
def list_tag_presets(
    limit: int = Query(50, ge=1, le=200),
    owner_only: bool = Query(False, description="If true, only return tag presets owned by the caller"),
    include_shared: bool = Query(True, description="Include shared presets when listing"),
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    owner = user.get("username") if owner_only else None
    effective_owner = None if (include_shared and not owner_only) else owner
    presets = store.list_tag_presets(owner=effective_owner, limit=limit)
    return {"presets": presets, "count": len(presets)}


@router.post("/search/saved/bulk-tags", summary="Bulk update tags for saved searches")
def bulk_update_tags(
    payload: BulkTagUpdateRequest,
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    if not payload.search_ids:
        raise HTTPException(status_code=400, detail="No search IDs provided")
    updated = store.bulk_update_tags(
        payload.search_ids,
        add=payload.add,
        remove=payload.remove,
        replace=payload.replace,
    )
    return {"updated": updated}


@router.delete("/search/saved/{search_id}", summary="Delete a saved search")
def delete_saved_search(
    search_id: str,
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    deleted = store.delete_saved_search(search_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return {"deleted": True, "search_id": search_id}


@router.patch("/search/saved/{search_id}", summary="Update a saved search")
def patch_saved_search(
    search_id: str,
    payload: SavedSearchUpdate,
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    try:
        updated = store.update_saved_search(
            search_id,
            name=payload.name,
            params=payload.params,
            favorite=payload.favorite,
            tags=payload.tags,
        )
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("duplicate_saved_search"):
            owner = "shared"
            if ":" in msg:
                owner_val = msg.split(":", 1)[1]
                owner = owner_val or "shared"
            raise HTTPException(
                status_code=409,
                detail=f"Saved search name already exists (owner={owner})",
            )
        raise
    if not updated:
        raise HTTPException(status_code=404, detail="Saved search not found or nothing to update")
    return {"updated": True, "search_id": search_id}


@router.post("/search/saved/{search_id}/share", summary="Promote a saved search to shared scope")
def share_saved_search(
    search_id: str,
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    try:
        shared_id = store.clone_saved_search(search_id, target_owner=None)
    except ValueError as exc:
        msg = str(exc)
        if msg == "saved_search_not_found":
            raise HTTPException(status_code=404, detail="Saved search not found")
        if msg.startswith("duplicate_saved_search"):
            owner = "shared"
            if ":" in msg:
                owner_val = msg.split(":", 1)[1]
                owner = owner_val or "shared"
            raise HTTPException(
                status_code=409,
                detail=f"Shared search name already exists (owner={owner})",
            )
        raise
    return {"search_id": shared_id}


@router.get("/search/saved/{search_id}/export", summary="Export a saved search configuration")
def export_saved_search(
    search_id: str,
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    record = store.get_saved_search(search_id)
    if not record:
        raise HTTPException(status_code=404, detail="Saved search not found")
    return record


@router.post("/search/saved/import", summary="Import a saved search definition")
def import_saved_search(
    payload: SavedSearchImportRequest,
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    try:
        search_id = store.import_saved_search(payload.model_dump(), owner=user.get("username"))
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("duplicate_saved_search"):
            owner = "shared"
            if ":" in msg:
                owner_val = msg.split(":", 1)[1]
                owner = owner_val or "shared"
            raise HTTPException(
                status_code=409,
                detail=f"Saved search name already exists (owner={owner})",
            )
        raise HTTPException(status_code=400, detail="Invalid saved search payload")
    return {"search_id": search_id}


@router.get("/case/{case_id}", summary="List review entries for a given case")
def reviews_by_case(
    case_id: str,
    limit: int = Query(5, ge=1, le=50),
    store: ReviewStore = Depends(get_store),
    user=Depends(require_token),
):
    """Return review queue entries associated with a specific case."""
    reviews = store.get_reviews_by_case(case_id=case_id, limit=limit)
    return {"case_id": case_id, "reviews": reviews, "count": len(reviews)}


@router.get("/{review_id}", summary="Get a review item")
def get_review(review_id: str, store: ReviewStore = Depends(get_store)):
    """Get full review item by ID."""
    item = store.get_review(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    return item


def _build_hybrid_query_from_request(payload: HybridSearchRequest) -> HybridSearchQuery:
    """Convert API payload into the service query dataclass."""

    entities = [
        QueryEntityFilter(type=entity.type, value=entity.value, match_mode=entity.match_mode)
        for entity in payload.entities
    ]
    time_range = None
    if payload.time_range:
        if payload.time_range.end < payload.time_range.start:
            raise HTTPException(status_code=400, detail="time_range.end must be after start")
        time_range = QueryTimeRange(start=payload.time_range.start, end=payload.time_range.end)

    return HybridSearchQuery(
        text=payload.text,
        classifications=payload.classifications,
        datasets=payload.datasets,
        case_ids=payload.case_ids,
        entities=entities,
        time_range=time_range,
        limit=payload.limit,
        vector_limit=payload.vector_limit,
        structured_limit=payload.structured_limit,
        offset=payload.offset,
    )


@router.post("/{review_id}/claim", summary="Claim a review")
def claim_review(review_id: str, user=Depends(require_token), store: ReviewStore = Depends(get_store)):
    """Assign current user to the review and log action."""
    store.update_status(review_id, status="in_review", notes=f"claimed by {user['username']}")
    store.log_action(review_id, actor=user["username"], action="claimed")
    return {"review_id": review_id, "status": "in_review"}


@router.post("/{review_id}/annotate", summary="Annotate a review item")
def annotate_review(
    review_id: str,
    payload: AnnotateRequest,
    user=Depends(require_token),
    store: ReviewStore = Depends(get_store),
):
    """Attach annotations and notes to a review; logs action."""
    # Save annotation into actions for now
    store.log_action(
        review_id,
        actor=user["username"],
        action="annotate",
        payload={"annotations": payload.annotations, "notes": payload.notes},
    )
    return {"review_id": review_id, "annotated": True}


@router.post("/{review_id}/decision", summary="Make a decision on a review")
def decision(
    review_id: str,
    payload: DecisionRequest,
    background_tasks: BackgroundTasks,
    user=Depends(require_token),
    store: ReviewStore = Depends(get_store),
):
    """Record a decision (accepted/rejected/needs_more_info).

    If decision is 'accepted' and auto_generate_report is True, schedule background report generation.
    """
    if payload.decision not in {"accepted", "rejected", "needs_more_info", "in_review"}:
        raise HTTPException(status_code=400, detail="Invalid decision")

    store.update_status(review_id, status=payload.decision, notes=payload.notes)
    store.log_action(
        review_id,
        actor=user["username"],
        action="decision",
        payload={"decision": payload.decision, "notes": payload.notes},
    )

    # If accepted and auto_generate_report is requested, schedule background job
    if payload.decision == "accepted" and payload.auto_generate_report:
        # Schedule background task to generate and export report
        # generate_report_for_case will use the default ReviewStore and exporter,
        # and will log action results back into the store.
        background_tasks.add_task(generate_report_for_case, review_id, store)

    return {"review_id": review_id, "status": payload.decision}


@router.get("/{review_id}/actions", summary="Get review action history")
def actions(review_id: str, store: ReviewStore = Depends(get_store)):
    """Return audit trail for a review."""
    actions = store.get_actions(review_id)
    return {"review_id": review_id, "actions": actions}
