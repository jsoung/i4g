"""API-level tests for intake endpoints."""

from __future__ import annotations

import json
import time

from fastapi.testclient import TestClient

from i4g.api.app import create_app
from i4g.api.intake import get_service
from i4g.services.intake import IntakeJobResult, IntakeService
from i4g.storage import EvidenceStorage
from i4g.store.intake_store import IntakeStore

API_KEY = {"X-API-KEY": "dev-analyst-token"}


def _build_service(tmp_path) -> IntakeService:
    store = IntakeStore(db_path=tmp_path / "intake.db")
    evidence = EvidenceStorage(local_dir=tmp_path / "evidence")

    class DummyRunner:
        name = "dummy"

        def run(self, intake):
            return IntakeJobResult(case_id="case-api-123", message="Ingested", metadata={"dummy": True})

    return IntakeService(store=store, evidence_storage=evidence, job_runner=DummyRunner())


def test_submit_and_track_intake(tmp_path):
    app = create_app()
    service = _build_service(tmp_path)
    app.dependency_overrides[get_service] = lambda: service

    client = TestClient(app)

    payload = {
        "reporter_name": "Jane Smith",
        "summary": "Fraudulent crypto investment",
        "details": "Victim transferred funds to fake exchange.",
        "submitted_by": "analyst_1",
        "contact_email": "jane@example.com",
        "source": "desktop_helper",
        "metadata": {"channel": "desktop"},
    }

    files = [("files", ("evidence.txt", b"evidence-bytes", "text/plain"))]

    response = client.post("/intakes/", data={"payload": json.dumps(payload)}, files=files, headers=API_KEY)
    assert response.status_code == 201
    data = response.json()
    assert "intake_id" in data
    assert "job_id" in data
    intake_id = data["intake_id"]
    job_id = data["job_id"]

    detail_resp = client.get(f"/intakes/{intake_id}", headers=API_KEY)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["reporter_name"] == "Jane Smith"
    assert len(detail["attachments"]) == 1
    assert detail["status"] in {"received", "processing", "processed"}

    list_resp = client.get("/intakes/", headers=API_KEY)
    assert list_resp.status_code == 200
    listing = list_resp.json()
    assert listing["count"] == 1

    job = None
    for _ in range(5):
        status_resp = client.get(f"/intakes/jobs/{job_id}", headers=API_KEY)
        assert status_resp.status_code == 200
        job = status_resp.json()
        if job["status"] == "completed":
            break
        time.sleep(0.05)

    assert job["status"] == "completed"
    assert job["metadata"]["case_id"] == "case-api-123"

    detail_after = client.get(f"/intakes/{intake_id}", headers=API_KEY)
    assert detail_after.status_code == 200
    detail_payload = detail_after.json()
    assert detail_payload["status"] == "processed"
    assert detail_payload["case_id"] == "case-api-123"

    app.dependency_overrides.clear()
