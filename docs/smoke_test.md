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

### 3. Account List Extraction (Local API + Job)

1. With the FastAPI server from the prerequisites still running, issue an authenticated
   request to the new `/accounts/extract` endpoint. The example below narrows the search window
   and limits results so the run finishes quickly:
   ```bash
   curl -sS -X POST "http://127.0.0.1:8000/accounts/extract" \
     -H "Content-Type: application/json" \
     -H "X-ACCOUNTLIST-KEY: dev-analyst-token" \
     -d '{
       "start_time": "2025-11-01T00:00:00Z",
       "end_time": "2025-11-15T23:59:59Z",
       "top_k": 25,
       "output_formats": ["pdf", "xlsx"]
     }' | jq '{request_id: .request_id, indicators: (.indicators | length), warnings: .warnings}'
   ```
   Expect a JSON payload that lists at least a few indicators plus any warnings for missing
   categories. The artifacts section will contain filesystem paths under `data/reports/account_list`
   when `output_formats` is supplied.
2. Exercise the Cloud Run job entrypoint locally. Start with a dry run to confirm configuration:
   ```bash
   env \
     I4G_ACCOUNT_JOB__WINDOW_DAYS=15 \
     I4G_ACCOUNT_JOB__CATEGORIES=bank,crypto,payments \
     I4G_ACCOUNT_JOB__OUTPUT_FORMATS=pdf,xlsx \
     I4G_ACCOUNT_JOB__DRY_RUN=true \
     I4G_RUNTIME__LOG_LEVEL=INFO \
     conda run -n i4g i4g-account-job
   ```
   Logs should show the computed window plus `Dry run enabled; skipping execution.`
3. Re-run without the dry-run flag so artifacts are generated locally. The command is identical
   minus `I4G_ACCOUNT_JOB__DRY_RUN=true`. Verify that PDFs/XLSX files land in
   `data/reports/account_list/` (or the configured reports bucket / Drive folder when those env vars
   are set) and that the log line `Artifacts generated: {...}` appears.

#### Account list exporter smoke (mock data)

When you only need to confirm that the exporter wiring works (local filesystem, Drive, or Cloud
Storage) without hitting the retriever/LLM stack, run the dedicated mock script:

```bash
conda run -n i4g python tests/adhoc/account_list_export_smoke.py --output-dir data/reports/account_list_smoke
```

The script fabricates a handful of source documents, passes them through stub retriever/extractor
components, and writes CSV/JSON/XLSX/PDF artifacts via `AccountListService`. The output paths are
printed to STDOUT so you can verify Drive/`gs://` uploads or inspect the local files directly.

### 4. Optional Local Checks

- **Streamlit Analyst Dashboard:** Once the FastAPI smoke test succeeds, launch the dashboard (`conda run -n i4g streamlit run src/i4g/ui/analyst_dashboard.py`) and verify that intakes and queue actions render.
- **Vertex Retrieval Smoke:** If you have GCP credentials for Discovery Engine, run `conda run -n i4g python scripts/smoke_vertex_retrieval.py --project <project> --data-store-id <data_store>` to validate the managed search stack. This requires access to the Artifact Registry dataset and may be skipped locally.

Document successful runs (or failures) in `planning/change_log.md` when they drive code or infrastructure updates.

## GCP Smoke Tests (Dev Environment)

These steps ensure the deployed services, Cloud Run jobs, and shared storage paths cooperate in the dev project. Authenticate with `gcloud auth login` (and `gcloud config set project i4g-dev`) before continuing.

> **Terraform drift warning**
> The `process-intakes` and `account-list` jobs are Terraform-managed. It’s fine to temporarily override their container command/args or env vars with `gcloud run jobs update` while running a smoke test, but you must roll those overrides back afterward or Terraform plans will show persistent diffs. Before changing a job, capture the current command/args so you can restore them:
> ```bash
> gcloud run jobs describe process-intakes \
>   --project i4g-dev --region us-central1 \
>   --format='value(spec.template.spec.template.spec.containers[0].command)'
> ```
> After the test, clear any ad-hoc overrides (command/args/env) or re-run the exact `gcloud run jobs update ...` block from Terraform to put the job back into sync. For example, if you set a custom command while debugging:
> ```bash
> gcloud run jobs update process-intakes \
>   --project i4g-dev --region us-central1 \
>   --clear-command --clear-args
> ```
> Repeat the same pattern for `account-list` (swap the job name) so `terraform plan` stays clean for both services.

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

### 1. Automated Cloud Run Smoke (recommended)

If your workstation already has `gcloud` and `curl` available, run the scripted smoke to submit an intake, execute the Cloud Run job, and verify the processed state in one step:

```bash
conda run -n i4g python scripts/smoke_dev_cloud_run.py
```

The script prints a JSON summary similar to:

```json
{
  "intake_id": "...",
  "job_id": "...",
  "execution": "process-intakes-abcde",
  "intake_status": "processed",
  "job_status": "completed"
}
```

If you prefer to run the workflow manually (useful for debugging individual steps), follow the commands below.

### 2. Submit an Intake via the Deployed API

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

### 3. Execute the Cloud Run Intake Job

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

### 4. Validate the Execution

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

### 5. Account List Cloud Run Job (Dev)

This flow validates the scheduled exporter that now backs the analyst reports.

1. Configure the Cloud Run job environment once so static settings match the dev project. Replace
   the bucket/folder placeholders with real values:
   ```bash
   gcloud run jobs update account-list \
     --project i4g-dev \
     --region us-central1 \
     --container=container-0 \
     --update-env-vars=I4G_RUNTIME__LOG_LEVEL=INFO,\
   I4G_ACCOUNT_JOB__WINDOW_DAYS=15,\
   I4G_ACCOUNT_JOB__CATEGORIES=bank,crypto,payments,\
   I4G_ACCOUNT_JOB__OUTPUT_FORMATS=pdf,xlsx,\
   I4G_ACCOUNT_JOB__INCLUDE_SOURCES=true,\
   I4G_ACCOUNT_LIST__DRIVE_FOLDER_ID=<drive-folder-id>,\
   I4G_STORAGE__REPORTS_BUCKET=<reports-bucket>
   ```
   The nested `I4G_ACCOUNT_LIST__*` and `I4G_STORAGE__*` env vars ensure exporters can publish to
   Google Drive or Cloud Storage the same way they do locally. You can omit Drive settings if the
   reports bucket is sufficient.
2. Execute the job in dry-run mode first to confirm settings parsed correctly:
   ```bash
   gcloud run jobs execute account-list \
     --project i4g-dev \
     --region us-central1 \
     --wait \
     --container=container-0 \
     --update-env-vars=I4G_ACCOUNT_JOB__DRY_RUN=true
   ```
   Look for `Dry run enabled; skipping execution.` inside the execution logs. Remove the dry-run
   override for the actual export:
   ```bash
   gcloud run jobs execute account-list \
     --project i4g-dev \
     --region us-central1 \
     --wait \
     --container=container-0
   ```
3. Inspect Cloud Logging for the execution to confirm counts and artifact uploads:
   ```bash
   gcloud logging read \
     "resource.type=cloud_run_job AND resource.labels.job_name=account-list" \
     --project i4g-dev --limit 50 --format text
   ```
   Expect `Account list run ... completed` plus an `Artifacts generated: {...}` line that references
   Drive links or `gs://` paths.
4. If you publish to Cloud Storage, list the report objects to verify timestamps:
   ```bash
   gsutil ls -r gs://<reports-bucket>/account_list/
   ```
   When Drive uploads are enabled, also spot-check the shared folder for the new files. Record the
   run (success or failure) in `planning/change_log.md` to capture operational history.
