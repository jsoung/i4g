# Smoke Tests — i4g Prototype

These smoke tests provide fast confidence that core ingestion and review workflows still function after code or infrastructure changes. Keep the shared Conda environment (`i4g`) handy—every command that invokes Python below assumes `conda run -n i4g`.

The scenarios are split into two groups:

- **Local smoke tests** run entirely on your workstation using the embedded SQLite stores.
- **GCP smoke tests** hit the deployed FastAPI gateway and Cloud Run jobs in the dev project (`i4g-dev`).

## Local Smoke Tests

### Prerequisites

1. Populate local demo artifacts if you have a fresh checkout:
   ```bash
   conda run -n i4g python scripts/bootstrap_local_sandbox.py --reset
   ```
2. Launch the FastAPI service in a dedicated terminal. Keep it running while you execute the tests:
   ```bash
   conda run -n i4g uvicorn i4g.api.app:app --host 127.0.0.1 --port 8000
   ```
3. Ensure the analyst token `dev-analyst-token` exists (it ships with the repo). Adjust commands if you use a different key.

### 1. FastAPI Intake Submission + Intake Job (API mode)

1. Prepare a JSON payload and simple attachment for the submission. The example below mirrors what the automated smoke script uses:
   ```bash
   cat <<'EOF' >/tmp/intake_payload.json
   {
     "reporter_name": "Test Reporter",
     "summary": "Suspicious crypto request",
     "details": "Victim asked to send crypto to wallet XYZ.",
     "submitted_by": "qa-smoke",
     "source": "smoke-test",
     "metadata": {
       "environment": "local-smoke",
       "ticket": "SMOKE-INTAKE"
     }
   }
   EOF

   echo "evidence screenshot placeholder" >/tmp/intake_evidence.txt
   ```
2. Submit the intake via the FastAPI endpoint and capture the response:
   ```bash
   curl -s \
     -H "X-API-KEY: dev-analyst-token" \
     -F "payload=$(jq -c . /tmp/intake_payload.json)" \
     -F "files=@/tmp/intake_evidence.txt;type=text/plain" \
     http://127.0.0.1:8000/intakes/ > /tmp/intake_response.json
   ```
3. Extract the identifiers for the job execution:
   ```bash
   export I4G_INTAKE__ID=$(jq -r '.intake_id' /tmp/intake_response.json)
   export I4G_INTAKE__JOB_ID=$(jq -r '.job_id' /tmp/intake_response.json)
   ```
4. Execute the intake worker in API mode so it fetches the record via HTTP. The worker will update status and attach a case ID on success:
   ```bash
   env \
     I4G_INTAKE__ID="$I4G_INTAKE__ID" \
     I4G_INTAKE__JOB_ID="$I4G_INTAKE__JOB_ID" \
     I4G_INTAKE__API_BASE=http://127.0.0.1:8000/intakes \
     I4G_API__KEY=dev-analyst-token \
     conda run -n i4g python -m i4g.worker.jobs.intake
   ```
5. Confirm the job completed:
   ```bash
   curl -s -H "X-API-KEY: dev-analyst-token" \
     "http://127.0.0.1:8000/intakes/$I4G_INTAKE__ID" | jq '{status: .status, job: .job.status, case_id: .case_id}'
   ```
   Expected result:
   ```json
   {
     "status": "processed",
     "job": "completed",
     "case_id": "<matches intake_id>"
   }
   ```

### 2. Ingestion Job Dry Run

Validate that the ingestion worker can read the sample dataset and produce diagnostics without writing to the vector store.

```bash
env \
  I4G_INGEST__JSONL_PATH=$PWD/data/retrieval_poc/cases.jsonl \
  I4G_INGEST__DRY_RUN=true \
  I4G_INGEST__BATCH_LIMIT=3 \
  I4G_RUNTIME__LOG_LEVEL=INFO \
  conda run -n i4g python -m i4g.worker.jobs.ingest
```

Expected log excerpts:
```
Dry run enabled; would ingest case_id=...
Ingestion complete: processed=3 failures=0
```

### 3. Optional Local Checks

- **Streamlit Analyst Dashboard:** Once the FastAPI smoke test succeeds, launch the dashboard (`conda run -n i4g streamlit run src/i4g/ui/analyst_dashboard.py`) and verify that intakes and queue actions render.
- **Vertex Retrieval Smoke:** If you have GCP credentials for Discovery Engine, run `conda run -n i4g python scripts/smoke_vertex_retrieval.py --project <project> --data-store-id <data_store>` to validate the managed search stack. This requires access to the Artifact Registry dataset and may be skipped locally.

Document successful runs (or failures) in `planning/change_log.md` when they drive code or infrastructure updates.

## GCP Smoke Tests (Dev Environment)

These steps ensure the deployed services, Cloud Run jobs, and shared storage paths cooperate in the dev project. Authenticate with `gcloud auth login` (and `gcloud config set project i4g-dev`) before continuing.

### Prerequisites

1. **Update the Cloud Run job environment (one-time per project).** This bakes in the static configuration needed for API mode so you only override the intake identifiers per execution:
   ```bash
   gcloud run jobs update process-intakes \
     --project i4g-dev \
     --region us-central1 \
     --container=container-0 \
     --update-env-vars=I4G_INTAKE__API_BASE=https://fastapi-gateway-y5jge5w2cq-uc.a.run.app/intakes,\
I4G_API__KEY=dev-analyst-token,\
I4G_STORAGE__SQLITE_PATH=/tmp/i4g/sqlite/intake.db,\
I4G_RUNTIME__FALLBACK_DIR=/tmp/i4g,\
I4G_INGEST__ENABLE_VECTOR=false
   ```
   Confirm the change with `gcloud run jobs describe process-intakes --format='value(spec.template.spec.template.spec.containers[0].env)'` if needed.
2. Ensure the remote FastAPI gateway is healthy: https://fastapi-gateway-y5jge5w2cq-uc.a.run.app/ (you should see the default OpenAPI docs).

### 1. Submit an Intake via the Deployed API

```bash
curl -sS -L -o /tmp/dev_intake_response.json -w "%{http_code}" \
  -X POST "https://fastapi-gateway-y5jge5w2cq-uc.a.run.app/intakes/" \
  -H "X-API-KEY: dev-analyst-token" \
  -F 'payload={"reporter_name":"Dev Smoke","summary":"Dev smoke submission","details":"Automated smoke test run","source":"smoke-test"}'
```
Expect `201` as the trailing status code. Capture the dynamic identifiers:

```bash
export DEV_INTAKE_ID=$(jq -r '.intake_id' /tmp/dev_intake_response.json)
export DEV_JOB_ID=$(jq -r '.job_id' /tmp/dev_intake_response.json)
```

### 2. Execute the Cloud Run Intake Job

Only the dynamic identifiers change per run because the static configuration is now part of the job definition:

```bash
gcloud run jobs execute process-intakes \
  --project i4g-dev \
  --region us-central1 \
  --wait \
  --container=container-0 \
  --update-env-vars=I4G_INTAKE__ID=$DEV_INTAKE_ID,I4G_INTAKE__JOB_ID=$DEV_JOB_ID
```

You should see `Execution [...] has successfully completed.` in the CLI output.

### 3. Validate the Execution

1. Inspect the Cloud Logging trail for the execution (replace the execution name if different):
   ```bash
   gcloud logging read \
     "resource.type=cloud_run_job AND resource.labels.job_name=process-intakes AND labels.\"run.googleapis.com/execution_name\"=<execution-name>" \
     --project i4g-dev --limit 20 --format text
   ```
   Look for `Intake job completed successfully via API` along with the HTTP 200 updates.
2. Confirm the intake record reflects the processed status:
   ```bash
   curl -sS -H "X-API-KEY: dev-analyst-token" \
     "https://fastapi-gateway-y5jge5w2cq-uc.a.run.app/intakes/$DEV_INTAKE_ID" | \
     jq '{status: .status, job_status: .job.status, case_id: .case_id}'
   ```
   Expected result mirrors the local check (`processed` / `completed`).

Keep a short note in `planning/change_log.md` each time you run the cloud smoke to track regressions or environment drift.
