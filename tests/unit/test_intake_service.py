"""Unit tests for the intake service orchestration layer."""

from __future__ import annotations

from pathlib import Path

from i4g.services.intake import AttachmentPayload, IntakeJobResult, IntakeService
from i4g.storage import EvidenceStorage
from i4g.store.intake_store import IntakeStore


def test_intake_service_roundtrip(tmp_path):
    db_path = tmp_path / "intake.db"
    store = IntakeStore(db_path=db_path)
    evidence_dir = tmp_path / "evidence"
    evidence = EvidenceStorage(local_dir=evidence_dir)

    class DummyRunner:
        name = "dummy"

        def run(self, intake):
            return IntakeJobResult(case_id="case-123", message="Ingested", metadata={"dummy": True})

    service = IntakeService(store=store, evidence_storage=evidence, job_runner=DummyRunner())

    submission = {
        "reporter_name": "John Doe",
        "summary": "Victim lost access to bank account",
        "details": "The attacker hijacked credentials after phishing email.",
        "submitted_by": "analyst_1",
        "contact_email": "victim@example.com",
        "source": "web_form",
        "metadata": {"channel": "web"},
    }
    attachments = [AttachmentPayload(file_name="evidence.txt", data=b"screenshot", content_type="text/plain")]

    result = service.create_intake(submission, attachments, create_job=True)

    assert result["intake_id"]
    assert result["job_id"]
    assert len(result["attachments"]) == 1

    record = service.get_intake(result["intake_id"])
    assert record is not None
    assert record["reporter_name"] == "John Doe"
    assert record["metadata"]["channel"] == "web"
    assert len(record["attachments"]) == 1

    stored_path = Path(record["attachments"][0]["storage_uri"])
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"screenshot"

    job = service.get_job(result["job_id"])
    assert job is not None
    assert job["status"] == "queued"

    service.process_job(result["intake_id"], result["job_id"])

    job_after = service.get_job(result["job_id"])
    assert job_after is not None
    assert job_after["status"] == "completed"
    assert job_after["metadata"]["case_id"] == "case-123"

    record_after = service.get_intake(result["intake_id"])
    assert record_after is not None
    assert record_after["job"]["status"] == "completed"
    assert record_after["case_id"] == "case-123"
    assert record_after["status"] == "processed"

    listings = service.list_intakes(limit=10)
    assert len(listings) == 1
    assert listings[0]["intake_id"] == result["intake_id"]
