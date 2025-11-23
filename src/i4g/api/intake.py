"""FastAPI router exposing intake submission endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, ValidationError

from i4g.api.auth import require_token
from i4g.services.intake import AttachmentPayload, IntakeService

router = APIRouter(prefix="/intakes", tags=["intakes"])


class IntakeSubmission(BaseModel):
    reporter_name: str
    summary: str
    details: str
    submitted_by: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_handle: Optional[str] = None
    preferred_contact: Optional[str] = None
    incident_date: Optional[str] = None
    loss_amount: Optional[float] = None
    source: str = "unknown"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IntakeJobUpdate(BaseModel):
    status: str
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class IntakeStatusUpdate(BaseModel):
    status: str
    message: Optional[str] = None


class IntakeCaseAttachment(BaseModel):
    case_id: Optional[str] = None
    review_id: Optional[str] = None


def get_service() -> IntakeService:
    return IntakeService()


@router.post("/", summary="Submit a new intake", status_code=201)
async def submit_intake(
    background_tasks: BackgroundTasks,
    payload: str = Form(..., description="JSON payload describing the intake metadata"),
    files: List[UploadFile] = File(default_factory=list, description="Evidence attachments"),
    user=Depends(require_token),
    service: IntakeService = Depends(get_service),
):
    try:
        submission_model = IntakeSubmission.model_validate_json(payload)
    except ValidationError as exc:  # pragma: no cover - FastAPI converts automatically in most flows
        raise HTTPException(status_code=400, detail={"error": "invalid_payload", "details": exc.errors()}) from exc

    submission = submission_model.model_dump()
    submission.setdefault("metadata", {})
    submission["submitted_by"] = submission.get("submitted_by") or user.get("username") or "unknown"
    if not submission["submitted_by"]:
        raise HTTPException(status_code=400, detail="submitted_by is required")

    attachments: List[AttachmentPayload] = []
    for upload in files:
        data = await upload.read()
        attachments.append(
            AttachmentPayload(
                file_name=upload.filename or "upload",
                data=data,
                content_type=upload.content_type,
            )
        )

    result = service.create_intake(
        submission, attachments, create_job=True, job_metadata={"submitted_by": submission["submitted_by"]}
    )

    if result["job_id"]:
        background_tasks.add_task(service.process_job, result["intake_id"], result["job_id"])

    record = service.get_intake(result["intake_id"]) or {}

    return {
        "intake_id": result["intake_id"],
        "job_id": result["job_id"],
        "attachments": result["attachments"],
        "status": record.get("status", "received"),
        "job": record.get("job"),
    }


@router.get("/", summary="List recent intakes")
def list_intakes(
    limit: int = Query(25, ge=1, le=200),
    user=Depends(require_token),
    service: IntakeService = Depends(get_service),
):
    items = service.list_intakes(limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/{intake_id}", summary="Fetch intake details")
def get_intake(intake_id: str, user=Depends(require_token), service: IntakeService = Depends(get_service)):
    record = service.get_intake(intake_id)
    if not record:
        raise HTTPException(status_code=404, detail="Intake not found")
    return record


@router.get("/jobs/{job_id}", summary="Fetch intake job status")
def get_job(job_id: str, user=Depends(require_token), service: IntakeService = Depends(get_service)):
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}", summary="Update an intake job status")
def update_job(
    job_id: str,
    payload: IntakeJobUpdate,
    service: IntakeService = Depends(get_service),
    user=Depends(require_token),
):
    updated = service.update_job_status(
        job_id, status=payload.status, message=payload.message, metadata=payload.metadata
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"updated": True, "job_id": job_id}


@router.post("/{intake_id}/status", summary="Update intake status")
def update_intake_status(
    intake_id: str,
    payload: IntakeStatusUpdate,
    service: IntakeService = Depends(get_service),
    user=Depends(require_token),
):
    service.update_intake_status(intake_id, status=payload.status, message=payload.message)
    return {"updated": True, "intake_id": intake_id}


@router.post("/{intake_id}/case", summary="Attach case metadata to intake")
def attach_case(
    intake_id: str,
    payload: IntakeCaseAttachment,
    service: IntakeService = Depends(get_service),
    user=Depends(require_token),
):
    service.attach_case(intake_id, case_id=payload.case_id, review_id=payload.review_id)
    return {"updated": True, "intake_id": intake_id, "case_id": payload.case_id, "review_id": payload.review_id}


__all__ = ["router"]
