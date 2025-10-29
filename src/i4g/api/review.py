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

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from i4g.api.auth import require_token
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


# Dependency factory for store (simple)
def get_store() -> ReviewStore:
    """Return a ReviewStore instance (mounted to default DB path)."""
    return ReviewStore()


# -----------------------
# Routes
# -----------------------


@router.post("/", summary="Enqueue a case for review")
def enqueue_case(payload: EnqueueRequest, user=Depends(require_token), store: ReviewStore = Depends(get_store)):
    """Add a case to the review queue."""
    review_id = store.enqueue_case(case_id=payload.case_id, priority=payload.priority)
    # Optionally log that user enqueued it
    store.log_action(review_id, actor=user["username"], action="enqueued", payload={"text": payload.text or ""})
    return {"review_id": review_id, "case_id": payload.case_id}


@router.get("/queue", summary="List queued cases")
def list_queue(status: str = Query("queued"), limit: int = Query(25), store: ReviewStore = Depends(get_store)):
    """List queued cases by status."""
    items = store.get_queue(status=status, limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/{review_id}", summary="Get a review item")
def get_review(review_id: str, store: ReviewStore = Depends(get_store)):
    """Get full review item by ID."""
    item = store.get_review(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    return item


@router.post("/{review_id}/claim", summary="Claim a review")
def claim_review(review_id: str, user=Depends(require_token), store: ReviewStore = Depends(get_store)):
    """Assign current user to the review and log action."""
    store.update_status(review_id, status="in_review", notes=f"claimed by {user['username']}")
    store.log_action(review_id, actor=user["username"], action="claimed")
    return {"review_id": review_id, "status": "in_review"}


@router.post("/{review_id}/annotate", summary="Annotate a review item")
def annotate_review(
    review_id: str, payload: AnnotateRequest, user=Depends(require_token), store: ReviewStore = Depends(get_store)
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
