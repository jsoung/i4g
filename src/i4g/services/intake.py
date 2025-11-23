"""Service layer coordinating intake submissions and storage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from i4g.services.factories import build_evidence_storage, build_intake_store
from i4g.services.intake_job_runner import IntakeJobResult, IntakeJobRunner, LocalPipelineIntakeJobRunner
from i4g.storage import EvidenceStorage, StoredAttachment
from i4g.store.intake_store import IntakeStore


@dataclass
class AttachmentPayload:
    """In-memory representation of an intake attachment before persistence."""

    file_name: str
    data: bytes
    content_type: Optional[str]


class IntakeService:
    """Orchestrate intake persistence across relational and blob stores."""

    def __init__(
        self,
        *,
        store: Optional[IntakeStore] = None,
        evidence_storage: Optional[EvidenceStorage] = None,
        job_runner: Optional[IntakeJobRunner] = None,
    ) -> None:
        self._store = store or build_intake_store()
        self._evidence = evidence_storage or build_evidence_storage()
        self._job_runner = job_runner or LocalPipelineIntakeJobRunner()

    # ------------------------------------------------------------------
    # Intake creation helpers
    # ------------------------------------------------------------------
    def create_intake(
        self,
        submission: Dict[str, Any],
        attachments: Iterable[AttachmentPayload],
        *,
        create_job: bool = True,
        job_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persist a new intake and optionally queue an ingestion job."""

        intake_id = self._store.create_intake(**submission)

        stored_attachments: List[StoredAttachment] = []
        for item in attachments:
            stored = self._evidence.save(
                intake_id,
                item.file_name,
                item.data,
                item.content_type,
            )
            self._store.add_attachment(
                intake_id,
                file_name=stored.file_name,
                content_type=stored.content_type,
                size_bytes=stored.size_bytes,
                checksum_sha256=stored.checksum_sha256,
                storage_uri=stored.storage_uri,
                storage_backend=stored.backend,
            )
            stored_attachments.append(stored)

        job_id: Optional[str] = None
        if create_job:
            effective_metadata: Dict[str, Any] = {"runner": self._job_runner.name}
            if job_metadata:
                effective_metadata.update(job_metadata)
            job_id = self._store.create_job(
                intake_id,
                status="queued",
                message="Queued for ingestion",
                metadata=effective_metadata,
            )

        return {
            "intake_id": intake_id,
            "job_id": job_id,
            "attachments": [stored.__dict__ for stored in stored_attachments],
        }

    # ------------------------------------------------------------------
    # Retrieval + job helpers for API wiring
    # ------------------------------------------------------------------
    def get_intake(self, intake_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get_intake(intake_id)

    def list_intakes(self, limit: int = 25) -> List[Dict[str, Any]]:
        return self._store.list_intakes(limit=limit)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._store.get_job(job_id)

    def update_job_status(
        self,
        job_id: str,
        *,
        status: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self._store.update_job_status(job_id, status=status, message=message, metadata=metadata)

    def update_intake_status(self, intake_id: str, *, status: str, message: Optional[str] = None) -> None:
        self._store.update_intake_status(intake_id, status=status, message=message)

    def attach_case(self, intake_id: str, *, case_id: Optional[str], review_id: Optional[str]) -> None:
        self._store.attach_case(intake_id, case_id=case_id, review_id=review_id)

    # ------------------------------------------------------------------
    # Job execution helpers
    # ------------------------------------------------------------------
    def process_job(self, intake_id: str, job_id: str) -> IntakeJobResult:
        """Execute the ingestion workflow for a queued intake job."""

        self._store.update_job_status(job_id, status="running", message="Processing intake")
        self._store.update_intake_status(intake_id, status="processing", message="Ingestion started")

        record = self._store.get_intake(intake_id)
        if not record:
            error_msg = f"intake_not_found:{intake_id}"
            self._store.update_job_status(job_id, status="failed", message=error_msg)
            raise ValueError(error_msg)

        try:
            result = self._job_runner.run(record)
            self._store.attach_case(intake_id, case_id=result.case_id, review_id=None)

            job_metadata = dict(result.metadata or {})
            job_metadata.setdefault("runner", self._job_runner.name)
            job_metadata["case_id"] = result.case_id

            self._store.update_job_status(job_id, status="completed", message=result.message, metadata=job_metadata)
            self._store.update_intake_status(intake_id, status="processed", message=result.message)
            return result
        except Exception as exc:  # pragma: no cover - defensive logging in production
            self._store.update_job_status(job_id, status="failed", message=str(exc))
            self._store.update_intake_status(intake_id, status="error", message=str(exc))
            raise


__all__ = [
    "AttachmentPayload",
    "IntakeService",
    "IntakeJobResult",
    "IntakeJobRunner",
    "LocalPipelineIntakeJobRunner",
]
