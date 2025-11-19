"""Cloud Run job entrypoint for processing queued intake submissions."""

from __future__ import annotations

import logging
import os
import sys

import httpx

from i4g.services.intake import IntakeService
from i4g.services.intake_job_runner import LocalPipelineIntakeJobRunner

LOGGER = logging.getLogger("i4g.worker.jobs.intake")


def _configure_logging() -> None:
    level_name = os.getenv("I4G_RUNTIME__LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _safe_post(
    client: httpx.Client,
    path: str,
    payload: dict,
    *,
    required: bool = True,
    log_context: str,
) -> httpx.Response | None:
    try:
        response = client.post(path, json=payload)
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        if not required and exc.response.status_code == 404:
            LOGGER.warning("API resource missing during %s: %s", log_context, exc)
            return None
        raise


def _process_via_api(intake_id: str, job_id: str, api_base: str, api_key: str | None) -> int:
    runner = LocalPipelineIntakeJobRunner()
    headers = {"X-API-KEY": api_key} if api_key else {}
    base = api_base.rstrip("/")
    with httpx.Client(base_url=base, headers=headers, timeout=30.0) as client:
        try:
            _safe_post(
                client,
                f"/jobs/{job_id}",
                {"status": "running", "message": "Processing intake", "metadata": {"runner": runner.name}},
                required=False,
                log_context="job status update (running)",
            )
            _safe_post(
                client,
                f"/{intake_id}/status",
                {"status": "processing", "message": "Ingestion started"},
                required=False,
                log_context="intake status update (processing)",
            )

            record_resp = client.get(f"/{intake_id}")
            record_resp.raise_for_status()
            record = record_resp.json()

            result = runner.run(record)
            metadata = dict(result.metadata or {})
            metadata.setdefault("runner", runner.name)
            metadata["case_id"] = result.case_id

            _safe_post(
                client,
                f"/{intake_id}/case",
                {"case_id": result.case_id, "review_id": None},
                required=False,
                log_context="case attachment",
            )
            _safe_post(
                client,
                f"/jobs/{job_id}",
                {"status": "completed", "message": result.message, "metadata": metadata},
                required=False,
                log_context="job status update (completed)",
            )
            _safe_post(
                client,
                f"/{intake_id}/status",
                {"status": "processed", "message": result.message},
                required=False,
                log_context="intake status update (processed)",
            )

            LOGGER.info(
                "Intake job completed successfully via API: intake_id=%s case_id=%s",
                intake_id,
                result.case_id,
            )
            return 0
        except Exception as exc:  # pragma: no cover - defensive logging for production failures
            LOGGER.exception("Intake job failed via API: intake_id=%s", intake_id)
            failure_payload = {"status": "failed", "message": str(exc)}
            try:
                _safe_post(
                    client,
                    f"/jobs/{job_id}",
                    failure_payload,
                    required=False,
                    log_context="job status update (failure)",
                )
                _safe_post(
                    client,
                    f"/{intake_id}/status",
                    {"status": "error", "message": str(exc)},
                    required=False,
                    log_context="intake status update (error)",
                )
            except Exception:  # pragma: no cover - best-effort failure reporting
                LOGGER.exception("Failed to report intake job failure to API")
            return 1


def main() -> int:
    """Entry point executed by the Cloud Run job container."""

    _configure_logging()

    intake_id = os.getenv("I4G_INTAKE__ID")
    job_id = os.getenv("I4G_INTAKE__JOB_ID")
    if not intake_id or not job_id:
        LOGGER.error("Both I4G_INTAKE__ID and I4G_INTAKE__JOB_ID environment variables are required")
        return 1

    LOGGER.info("Processing intake job: intake_id=%s job_id=%s", intake_id, job_id)

    api_base = os.getenv("I4G_INTAKE__API_BASE")
    if api_base:
        api_key = os.getenv("I4G_INTAKE__API_KEY") or os.getenv("I4G_API__KEY")
        return _process_via_api(intake_id, job_id, api_base, api_key)

    service = IntakeService()
    try:
        service.process_job(intake_id, job_id)
        LOGGER.info("Intake job completed successfully: intake_id=%s", intake_id)
        return 0
    except Exception:  # pragma: no cover - defensive logging for production failures
        LOGGER.exception("Intake job failed: intake_id=%s", intake_id)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
