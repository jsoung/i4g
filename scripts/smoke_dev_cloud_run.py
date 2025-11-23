#!/usr/bin/env python
"""Automate the dev Cloud Run intake smoke test.

This script submits an intake to the deployed FastAPI gateway, triggers the
Cloud Run intake job with the dynamic identifiers, and verifies that the intake
record transitions to the expected processed state.

Run from the repo root with `conda run -n i4g python scripts/smoke_dev_cloud_run.py`.
Requires `gcloud` and `curl` to be available in PATH and the caller to be
authenticated against the `i4g-dev` project.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Dict, Tuple

DEFAULT_API_URL = "https://fastapi-gateway-y5jge5w2cq-uc.a.run.app"
DEFAULT_TOKEN = "dev-analyst-token"
DEFAULT_PROJECT = "i4g-dev"
DEFAULT_REGION = "us-central1"
DEFAULT_JOB = "process-intakes"
DEFAULT_CONTAINER = "container-0"


class SmokeError(RuntimeError):
    """Raised when any smoke step fails."""


@dataclass
class SmokeResult:
    intake_id: str
    job_id: str
    execution_name: str
    intake_status: str
    job_status: str


def _run_command(cmd: list[str], *, capture_output: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the completed process.

    Raises SmokeError with a helpful message if the command fails.
    """
    try:
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - subprocess failure path
        message = f"Command failed ({' '.join(cmd)}): {exc.stderr or exc.stdout}"
        raise SmokeError(message) from exc


def _submit_intake(api_url: str, token: str) -> Tuple[str, str]:
    payload = {
        "reporter_name": "Dev Smoke",
        "summary": "Automated dev smoke submission",
        "details": "Submitted by smoke_dev_cloud_run.py",
        "source": "smoke-test",
    }
    curl_cmd = [
        "curl",
        "-sS",
        "-L",
        "-o",
        "-",
        "-w",
        "%{http_code}",
        "-X",
        "POST",
        f"{api_url}/intakes/",
        "-H",
        f"X-API-KEY: {token}",
        "-F",
        f"payload={json.dumps(payload)}",
    ]

    proc = _run_command(curl_cmd)
    raw_output = proc.stdout
    # curl -o - -w "%{http_code}" yields body+status. Split off the trailing status code.
    body, status_code = raw_output[:-3], raw_output[-3:]
    if status_code != "201":
        raise SmokeError(f"Intake submission failed (status {status_code}): {body}")

    try:
        response = json.loads(body)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"Invalid JSON from intake submission: {body}") from exc

    intake_id = response.get("intake_id")
    job_id = response.get("job_id")
    if not intake_id or not job_id:
        raise SmokeError(f"Missing intake or job id in response: {response}")

    return intake_id, job_id


def _execute_job(project: str, region: str, job: str, container: str, intake_id: str, job_id: str) -> str:
    env_overrides = f"I4G_INTAKE__ID={intake_id},I4G_INTAKE__JOB_ID={job_id}"
    cmd = [
        "gcloud",
        "run",
        "jobs",
        "execute",
        job,
        "--project",
        project,
        "--region",
        region,
        "--wait",
        "--container",
        container,
        f"--update-env-vars={env_overrides}",
    ]

    proc = _run_command(cmd)
    stdout = proc.stdout
    # If --wait is used the "Execution [name] has successfully completed." string normally appears
    marker = "Execution ["
    start = stdout.find(marker)
    if start != -1:
        start += len(marker)
        end = stdout.find("]", start)
        if end != -1:
            return stdout[start:end]

    # Fallback to describing the latest execution when the CLI output is truncated.
    describe_cmd = [
        "gcloud",
        "run",
        "jobs",
        "describe",
        job,
        "--project",
        project,
        "--region",
        region,
        "--format",
        "value(status.latestCreatedExecution.name)",
    ]
    describe_proc = _run_command(describe_cmd)
    execution_name = describe_proc.stdout.strip()
    if not execution_name:
        raise SmokeError(f"Could not determine execution name. gcloud output: {stdout}")
    return execution_name


def _fetch_intake(api_url: str, intake_id: str, token: str) -> Dict[str, Any]:
    cmd = [
        "curl",
        "-sS",
        "-H",
        f"X-API-KEY: {token}",
        f"{api_url}/intakes/{intake_id}",
    ]
    proc = _run_command(cmd)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"Invalid JSON when fetching intake: {proc.stdout}") from exc


def run_smoke(api_url: str, token: str, project: str, region: str, job: str, container: str) -> SmokeResult:
    intake_id, job_id = _submit_intake(api_url, token)
    execution_name = _execute_job(project, region, job, container, intake_id, job_id)
    intake = _fetch_intake(api_url, intake_id, token)

    status = intake.get("status")
    job_status = intake.get("job", {}).get("status")
    if status != "processed" or job_status != "completed":
        raise SmokeError(
            "Unexpected intake status after job execution: " f"status={status!r}, job_status={job_status!r}"
        )

    return SmokeResult(
        intake_id=intake_id,
        job_id=job_id,
        execution_name=execution_name,
        intake_status=status,
        job_status=job_status,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run dev Cloud Run intake smoke test")
    parser.add_argument("--api-url", default=os.getenv("I4G_SMOKE_API_URL", DEFAULT_API_URL))
    parser.add_argument("--token", default=os.getenv("I4G_SMOKE_TOKEN", DEFAULT_TOKEN))
    parser.add_argument("--project", default=os.getenv("I4G_SMOKE_PROJECT", DEFAULT_PROJECT))
    parser.add_argument("--region", default=os.getenv("I4G_SMOKE_REGION", DEFAULT_REGION))
    parser.add_argument("--job", default=os.getenv("I4G_SMOKE_JOB", DEFAULT_JOB))
    parser.add_argument("--container", default=os.getenv("I4G_SMOKE_CONTAINER", DEFAULT_CONTAINER))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        result = run_smoke(
            api_url=args.api_url.rstrip("/"),
            token=args.token,
            project=args.project,
            region=args.region,
            job=args.job,
            container=args.container,
        )
    except SmokeError as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "intake_id": result.intake_id,
                "job_id": result.job_id,
                "execution": result.execution_name,
                "intake_status": result.intake_status,
                "job_status": result.job_status,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
