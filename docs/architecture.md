# i4g System Architecture

> **Document Version**: 1.1
> **Last Updated**: November 30, 2025
> **Audience**: Engineers, technical stakeholders, university partners

---

## Executive Summary

**i4g** is a cloud-native, AI-powered platform that helps scam users document fraud and generate law enforcement reports. The system uses a **privacy-by-design** architecture where personally identifiable information (PII) is tokenized immediately upon upload and stored separately from case data.

You now run two first-party consoles. The **Next.js portal** on Cloud Run serves victims, volunteer analysts, and law enforcement officers through server-side proxy routes that preserve the privacy guarantees described below. The **Streamlit operations console** stays online for internal developers and sys-admins who need dashboards, data analytics, and live ingestion telemetry without exposing those tools to external users.

**Key Design Principles**:
1. **Zero Trust**: No analyst ever sees raw PII
2. **Serverless**: Zero budget constraint drives Cloud Run deployment
3. **Scalability**: Handles 20 concurrent users on GCP free tier
4. **Security**: AES-256-GCM encryption, OAuth 2.0, Firestore rules

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      User Layer                          │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│  │  User    │      │ Analyst  │      │   LEO    │        │
│  └────┬─────┘      └────┬─────┘      └────┬─────┘        │
└───────┼─────────────────┼─────────────────┼──────────────┘
    │                 │                 │
    │ HTTPS           │ HTTPS           │ HTTPS
    │                 │                 │
┌───────┼─────────────────┼─────────────────┼──────────────┐
│       │     GCP Cloud Run (us-central1)   │              │
│  ┌────▼─────────────────▼─────────────────▼────┐         │
│  │         Load Balancer (HTTPS)               │         │
│  └──┬─────────────────────┬────────────────────┘         │
│     │                     │                              │
│  ┌──▼─────────┐      ┌────▼──────────┐                   │
│  │  FastAPI   │      │  Next.js      │                   │
│  │  Backend   │      │  Analyst      │                   │
│  │  (Python)  │      │  Console      │                   │
│  └──┬─────────┘      └────┬──────────┘                   │
└─────┼─────────────────────┼──────────────────────────────┘
  │                     │
  │   Firestore API     │
  │                     │
┌─────▼─────────────────────▼──────────────────────────────┐
│                  Data Layer (GCP)                        │
│  ┌──────────────┐  ┌────────────┐  ┌───────────┐  ┌────────────┐
│  │  Firestore   │  │   Cloud    │  │  Secret   │  │ Vertex AI  │
│  │   (NoSQL)    │  │  Storage   │  │  Manager  │  │  Search    │
│  └──────┬───────┘  └────────────┘  └───────────┘  └────────────┘
└─────────┼────────────────────────────────────────────────┘
          │
          │  Cloud SQL (ingestion + entity tables)
          │
┌─────────▼────────────────────────────────────────────────┐
│                 Dual Extraction Indexes                  │
│  ┌──────────────┐    ┌───────────────┐                   │
│  │ Cloud SQL /  │    │ Vertex AI     │                   │
│  │ AlloyDB      │    │ Search Corpus │                   │
│  └──────────────┘    └───────────────┘                   │
└─────────┬────────────────────────────────────────────────┘
          │
          │ HTTP (localhost:11434)
          │
┌─────────▼────────────────────────────────────────────────┐
│               External Services                          │
│  ┌──────────────┐    ┌────────────┐                      │
│  │    Ollama    │    │  SendGrid  │                      │
│  │  LLM Server  │    │   Email    │                      │
│  └──────────────┘    └────────────┘                      │
└──────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. **FastAPI Backend**

**Responsibilities**:
- REST API endpoints for case management
- PII tokenization and encryption
- LLM-powered scam classification
- Authentication (OAuth 2.0 JWT validation)
- Firestore CRUD operations

**Technology Stack**:
- Python 3.11
- FastAPI 0.104+ (async/await support)
- LangChain 0.2+ (RAG pipeline)
- google-cloud-firestore (database client)
- google-cloud-storage (file uploads)
- cryptography (AES-256-GCM encryption)

**Key Endpoints**:
- `POST /api/cases` - Submit new case
- `GET /api/cases` - List assigned cases
- `GET /api/cases/{id}` - Get case details (PII masked)
- `PATCH /api/cases/{id}` - Update case status
- `POST /api/cases/{id}/approve` - Generate LEO report
- `GET /api/health` - Health check

Note: The `POST /api/cases` endpoint above is listed as a planned user-facing intake route in the architecture. In the current implementation this exact endpoint is not present — case intake is handled via the review queue and review-related routes (see `src/i4g/api/review.py` and the `/reviews` router). Consider this endpoint "planned" until a dedicated intake route is added.

---

### 2. **Experience Layer**

#### Next.js External Portal

**Responsibilities**:
- Orchestrate the full victim → analyst → law enforcement workflow with OAuth-backed authentication
- Expose search, review, approval, and report delivery experiences through a React UI that mirrors the FastAPI contracts
- Render case detail pages with evidence thumbnails, inline entity highlighting, and Discovery powered search facets
- Provide bulk report exports, smoke-test hooks, and future citizen-facing intake forms without revealing backend secrets

**Technology Stack**:
- Node.js 20 (Cloud Run)
- Next.js 15 App Router with React 19 RC and TypeScript
- Tailwind CSS, `@i4g/ui-kit`, and shared design tokens
- `@i4g/sdk` plus proto-backed adapter selected via `I4G_API_KIND` env var

**Key Features**:
- Hybrid rendering (Server Components + edge-ready client interactivity)
- Cloud Run friendly build (PNPM workspaces, multi-stage Dockerfile)
- API route proxy that injects server-only secrets for FastAPI calls
- Configurable mock mode for demos without backend dependencies

#### Streamlit Operations Console

**Responsibilities**:
- Give internal developers and sys-admins a fast path to query cases, review ingestion telemetry, and validate Discovery relevance tuning
- Host privileged dashboards (PII handling audit trails, queue depth monitors, weekly migration metrics) without impacting the hardened external portal
- Surface ad-hoc data science notebooks and quick visualizations that do not belong in the production-facing UI

**Technology Stack**:
- Python 3.11 with Streamlit 1.28+
- Shared component library (`i4g.ui.widgets`) to reuse FastAPI schemas directly in widgets
- OAuth session reuse via the same FastAPI-issued JWTs consumed by Next.js

**Key Features**:
- Runs behind Cloud Run IAM so only on-call engineers and sys-admins can launch it
- Ships with environment toggles (`I4G_ENV`, `I4G_ANALYTICS_MODE`) to switch between local SQLite/Chroma and GCP services
- Imports `i4g.services.discovery` directly so Discovery experiments stay consistent with the backend

### 3a. **Account List Extraction Service**

**Responsibilities**:
- Expose `POST /accounts/extract` for on-demand analyst runs with API-key enforcement (`X-ACCOUNTLIST-KEY`).
- Coordinate retrieval (`FinancialEntityRetriever`), LLM extraction (`AccountEntityExtractor`), and artifact generation (`AccountListExporter`).
- Publish CSV/JSON/XLSX/PDF outputs to the local reports directory, Cloud Storage, or Google Drive (when configured) and return signed links to the caller and the Streamlit console.
- Power the Cloud Run job `account-list` (scheduled via Cloud Scheduler) so recurring exports share the exact same code path as the interactive API.

**Technology Stack**:
- Python 3.11 shared package (`src/i4g/services/account_list/*`).
- LangChain + Ollama locally (Vertex AI/Gemini ready once service accounts are wired).
- ReportLab + OpenPyXL for artifact rendering.
- Cloud Run job container (`i4g-account-job` entrypoint) plus optional Google Drive uploads via ADC scopes.

**Key Features**:
- Category catalog (bank, crypto, payments today; IP/ASN/browser planned) driven by configuration so new indicators only need prompt/query definitions.
- Deduplication + metadata summary stored alongside artifacts, surfaced in the Streamlit dashboard via a summary/status table.
- Manual smoke harness (`tests/adhoc/account_list_export_smoke.py`) to verify exporter plumbing without hitting the LLM stack.
- FastAPI also exposes `/accounts/runs`, enabling the analyst console’s new `/accounts` page to trigger manual runs, refresh audit history via server-side API routes, and expose artifact links / warnings inline without leaking service credentials to the browser.

---

### 3b. **Dual Extraction Ingestion Pipeline**

**Responsibilities**:
- Normalize Discovery bundles into structured case/entity payloads (`ingest_payloads.prepare_ingest_payload`).
- Execute `i4g.worker.jobs.ingest`, which orchestrates entity extraction, SQL writes (`SqlWriter`), Firestore fan-out (`FirestoreWriter`), and Vertex AI Search document imports (`VertexWriter`).
- Persist ingestion run metrics plus retry payloads so operators can audit progress (`IngestionRunTracker`) and replay failed Firestore/Vertex batches via `i4g.worker.jobs.ingest_retry`.

**Technology Stack**:
- Python workers launched locally or via Cloud Run jobs using `conda run -n i4g python -m i4g.worker.jobs.{ingest,ingest_retry}`.
- Cloud SQL / SQLite for `cases`, `entities`, and `ingestion_runs`; Firestore for analyst-facing case documents; Vertex AI Search (`retrieval-poc`) for semantic retrieval.
- Settings-driven toggles (`I4G_STORAGE__FIRESTORE_PROJECT`, `I4G_VERTEX_SEARCH_*`, `I4G_INGEST_RETRY__BATCH_LIMIT`) resolved by `i4g.settings.get_settings()` so environment overrides stay declarative.

**Key Features**:
- Run tracking (`scripts/verify_ingestion_run.py`) records case/entity counts plus backend-specific write totals, enabling reproducible smokes across local/dev/prod.
- `_maybe_enqueue_retry` serializes the SQL result + payload + error, allowing the retry worker to rehydrate the exact Firestore/Vertex writes without repeating entity extraction.
- Retry worker operates in dry-run or live mode, reporting successes/failures per backend; batches can be tuned to stay under rate limits.

**Operational Status (Nov 30, 2025)**:
- Dev ingestion run `01993af5-09ab-4ecf-b0c8-cd86702b8edd` processed 200 `retrieval_poc_dev` cases with SQL/Firestore reaching 200 writes each; Vertex imported 155 documents before hitting the "Document batch requests/min" quota (HTTP 429 ResourceExhausted).
- `python -m i4g.worker.jobs.ingest_retry` (batch size 10) drained the 45 queued Vertex payloads once quota recovered, so the corpus is eventually consistent even when the live run throttles.
- Until the Vertex quota is raised, operators should stagger ingestion batches (e.g., lower ingestion job batch sizes) or schedule retry workers immediately after large ingests to finish the semantic index.

---

### 3. **Firestore Database**

**Collections**:

```
/cases
  └─ {case_id}
      ├─ created_at: timestamp
      ├─ user_email: string
      ├─ title: string
      ├─ description: string (tokenized: <PII:SSN:7a8f2e>)
      ├─ classification: {type, confidence}
      ├─ status: "pending_review" | "in_progress" | "resolved"
      ├─ assigned_to: analyst_uid
      ├─ evidence_files: [gs://urls]
      └─ notes: [{author, text, timestamp}]

/pii_vault
  └─ {token_id}
      ├─ case_id: string
      ├─ pii_type: "ssn" | "email" | "phone" | "credit_card"
      ├─ encrypted_value: bytes (AES-256-GCM)
      ├─ encryption_key_version: string
      └─ created_at: timestamp

/analysts
  └─ {uid}
      ├─ email: string
      ├─ full_name: string
      ├─ role: "analyst" | "admin"
      ├─ approved: boolean
      ├─ ferpa_certified: boolean
      └─ last_login: timestamp
```

**Security Rules**:
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Analysts can only read assigned cases
    match /cases/{case_id} {
      allow read: if request.auth != null &&
                     resource.data.assigned_to == request.auth.uid;
    }

    // PII vault locked to backend service account
    match /pii_vault/{token} {
      allow read, write: if request.auth.token.email == 'i4g-backend@i4g-prod.iam.gserviceaccount.com';
    }
  }
}
```

---

### 4. **Ollama LLM Server**

**Responsibilities**:
- Local LLM inference (no API costs)
- Scam classification (romance, crypto, phishing, other)
- PII extraction from unstructured text

**Model**: llama3.1 (8B parameters, 4-bit quantization)

**Inference API**:
```bash
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.1",
  "messages": [
    {
      "role": "user",
      "content": "Classify this scam: I met someone on Tinder..."
    }
  ]
}'
```

**Deployment**: Cloud Run with GPU (T4) for faster inference

---

## Data Flow: Evidence Upload → Report Generation

```
1. VICTIM SUBMITS CASE
   ↓
   POST /api/cases
   {
     "title": "Romance scam",
     "description": "My SSN is 123-45-6789...",
     "evidence_files": [...]
   }

2. PII EXTRACTION & TOKENIZATION
   ↓
   Regex detects: "123-45-6789" (SSN pattern)
   ↓
   Encrypt with AES-256-GCM
   ↓
   Store in /pii_vault: {token: "7a8f2e", encrypted_value: "..."}
   ↓
   Replace in description: "My SSN is <PII:SSN:7a8f2e>..."

3. SCAM CLASSIFICATION
   ↓
   LLM inference (Ollama)
   ↓
   Result: {"type": "Romance Scam", "confidence": 0.92}

4. STORE CASE IN FIRESTORE
   ↓
   /cases/{case_id}:
   {
     "description": "My SSN is <PII:SSN:7a8f2e>...",
     "classification": {"type": "Romance Scam", "confidence": 0.92},
     "status": "pending_review"
   }

5. ANALYST REVIEWS CASE
   ↓
   GET /api/cases/{case_id}
   ↓
   Returns: "My SSN is ███████..." (PII masked)

6. ANALYST APPROVES
   ↓
   POST /api/cases/{case_id}/approve
   ↓
   Fetch encrypted PII from /pii_vault
   ↓
   Decrypt: "123-45-6789"
   ↓
   Generate PDF report with real PII
   ↓
   Upload to Cloud Storage: gs://i4g-reports/{case_id}.pdf
   ↓
   Email user with secure download link
```

---

## Deployment Architecture

### GCP Free Tier Strategy

| Service | Free Tier | Estimated Usage | Cost |
|---------|-----------|-----------------|------|
| Cloud Run | 2M requests/month | 100K requests/month | $0 |
| Firestore | 50K reads/day | 1K reads/day | $0 |
| Cloud Storage | 5 GB | 2 GB (evidence files) | $0 |
| Cloud Logging | 50 GB/month | 10 GB/month | $0 |
| Secret Manager | 6 active secrets | 3 secrets | $0 |

**Total Monthly Cost**: **$0** (within free tier limits)

**Scaling Trigger**: If usage exceeds free tier, apply for:
1. Google for Nonprofits ($10K/year credits)
2. AWS Activate ($5K credits)
3. NSF SBIR grant ($50K)

---

### Cloud Run Configuration

API deployment (Python FastAPI):

```bash
gcloud run deploy i4g-api \
  --image gcr.io/i4g-prod/api:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --service-account i4g-backend@i4g-prod.iam.gserviceaccount.com \
  --max-instances 10 \
  --memory 1Gi \
  --timeout 300 \
  --set-env-vars "FIRESTORE_PROJECT_ID=i4g-prod,ENVIRONMENT=production" \
  --set-secrets "TOKEN_ENCRYPTION_KEY=TOKEN_ENCRYPTION_KEY:latest"
```

Analyst console deployment (Next.js container image built via PNPM workspaces):

```bash
gcloud run deploy i4g-console \
    --image us-central1-docker.pkg.dev/i4g-dev/applications/analyst-console:dev \
    --region us-central1 \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars NEXT_PUBLIC_USE_MOCK_DATA=false \
    --set-env-vars I4G_API_URL=https://fastapi-gateway-y5jge5w2cq-uc.a.run.app/ \
    --set-env-vars I4G_API_KIND=proto \
    --set-env-vars I4G_API_KEY=dev-analyst-token
```

**Auto-Scaling**:
- Minimum instances: 0 (scales to zero when idle)
- Maximum instances: 10 (free tier limit)
- Concurrency: 20 requests per instance
- Cold start time: ~3 seconds

---

## Security Architecture

> **Note:** All IAM, authentication, and role-planning details now live in `docs/iam.md`. This section only summarizes the privacy controls already documented elsewhere.

**Identity-Aware Proxy (IAP)** now fronts every Cloud Run service (FastAPI, Analyst Console, Streamlit). Users hit the standard Cloud Run URLs, are prompted by Google sign-in if needed, and traffic is forwarded only when the caller is listed in the IAP policy. This replaces the short-lived helper SPA.

### 1. **PII Isolation**

```
┌─────────────────────────────────────────────────────┐
│                  Untrusted Zone                     │
│  ┌────────────┐         ┌────────────┐              │
│  │ User Input │   -->   │ API Layer  │              │
│  └────────────┘         └──────┬─────┘              │
└────────────────────────────────┼────────────────────┘
                                 │
                       ┌─────────▼─────────┐
                       │   PII Extraction  │
                       │  (Regex + LLM)    │
                       └─────────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                                     │
    ┌─────────▼────────┐              ┌────────────▼────────┐
        │   PII Vault      │              │   Cases DB          │
        │  (Encrypted)     │              │  (Tokenized)        │
        │  Firestore       │              │  Firestore          │
        │  /pii_vault      │              │  /cases             │
        └──────────────────┘              └──────────┬──────────┘
          ⚠️ RESTRICTED                           │
         (Backend SA only)                            │
                     ┌────────▼──────────┐
                     │ Next.js Analyst   │
                                         │ Console (PII      │
                                         │ masked ███████)   │
                                         └───────────────────┘
```

---

### 3. **Encryption**

**At Rest**:
- **Firestore**: Automatic AES-256 encryption (Google-managed keys)
- **Cloud Storage**: Customer-Managed Encryption Keys (CMEK)
- **PII Vault**: Additional AES-256-GCM layer (app-level encryption)

**In Transit**:
- **All API calls**: TLS 1.3
- **Cloud Run**: HTTPS only (HTTP redirects to HTTPS)
- **Ollama**: HTTP localhost (same machine, no network)

**Key Management**:
```bash
# Encryption key stored in Secret Manager
gcloud secrets create TOKEN_ENCRYPTION_KEY \
  --data-file=<(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')

# Monthly key rotation (automated via Cloud Scheduler)
gcloud secrets versions add TOKEN_ENCRYPTION_KEY --data-file=new_key.txt
```

---

## Monitoring & Observability

### Structured Logging

```json
{
  "timestamp": "2025-10-30T12:00:00Z",
  "severity": "INFO",
  "correlation_id": "uuid-v4",
  "user_id": "analyst_uid_123",
  "action": "case_approved",
  "metadata": {
    "case_id": "uuid-v4",
    "classification": "Romance Scam",
    "confidence": 0.92
  }
}
```

---

### Custom Metrics

- **Request Rate**: `custom.googleapis.com/i4g/api_requests_per_second`
- **PII Vault Access**: `custom.googleapis.com/i4g/pii_vault_access_count`
- **Classification Accuracy**: `custom.googleapis.com/i4g/classification_accuracy`
- **LEO Reports Generated**: `custom.googleapis.com/i4g/reports_generated_count`

---

### Alerting Policies

1. **High Error Rate**: 5xx errors >5% for 5 minutes
2. **High Latency**: p95 latency >2 seconds for 5 minutes
3. **PII Vault Anomaly**: >100 accesses per minute
4. **Free Tier Quota**: >80% of monthly quota used

---

## Performance Benchmarks

### Response Times (p95)

- `POST /api/cases` (with LLM classification): 3.5 seconds
- `GET /api/cases`: 150 ms
- `GET /api/cases/{id}`: 200 ms
- `POST /api/cases/{id}/approve` (generate report): 2.2 seconds

### Throughput

- **Concurrent users**: 20 (tested with Locust)
- **Cases per day**: 50 (prototype usage)
- **LLM inference**: 5 tokens/second (Ollama on Cloud Run GPU)

---

## Disaster Recovery

### Backup Strategy

```bash
# Daily Firestore export (Cloud Scheduler cron job)
gcloud firestore export gs://i4g-backups/$(date +%Y%m%d) \
  --collection-ids=cases,analysts,pii_vault

# Retention: 7 days
gsutil lifecycle set lifecycle.json gs://i4g-backups
```

**lifecycle.json**:
```json
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 7}
      }
    ]
  }
}
```

---

### Recovery Procedures

**Scenario 1: Accidental case deletion**

```bash
# 1. Find latest backup
gsutil ls gs://i4g-backups/

# 2. Import backup
gcloud firestore import gs://i4g-backups/20251030/
```

**Scenario 2: PII vault corruption**

```bash
# 1. Stop API (prevent further writes)
gcloud run services update i4g-api --no-traffic

# 2. Restore from backup
gcloud firestore import gs://i4g-backups/20251030/ --collection-ids=pii_vault

# 3. Validate restoration
python scripts/validate_pii_vault.py

# 4. Resume traffic
gcloud run services update i4g-api --traffic
```

---

## Technology Stack

### Backend
- **Language**: Python 3.11
- **Framework**: FastAPI 0.104+ (async, type hints)
- **RAG Pipeline**: LangChain 0.2+ (LCEL composition)
- **LLM**: Ollama (llama3.1 8B model, 4-bit quantization)
- **Vector DB**: ChromaDB (local embeddings via nomic-embed-text)

### Frontend
- **External portal**: Next.js 15 (victim, analyst, and law enforcement UI)
- **Operations console**: Streamlit 1.28+ (internal dashboards for developers and sys-admins)
- **Shared styling**: Tailwind CSS design tokens + focused CSS for PII redaction and responsive layouts

### Cloud Infrastructure
- **Hosting**: Google Cloud Platform
  - Cloud Run (API + dashboard)
  - Firestore (NoSQL database)
  - Cloud Storage (file uploads)
  - Secret Manager (API keys, encryption keys)
  - Cloud Logging (structured logs)
  - Cloud Monitoring (metrics + alerts)

### CI/CD
- **Version Control**: GitHub
- **CI Pipeline**: GitHub Actions
  - Lint (black, isort, mypy)
  - Test (pytest, 80% coverage)
  - Build (Docker image)
  - Deploy (Cloud Run via gcloud CLI)

---

## Future Architecture Improvements

### Phase 2 (Post-MVP)
- [ ] Add Redis caching layer (reduce Firestore reads)
- [ ] Implement async task queue (Celery + Cloud Tasks)
- [ ] Multi-region deployment (us-central1 + europe-west1)
- [ ] CDN for static assets (Cloud CDN)

### Phase 3 (Scale)
- [ ] Microservices split (auth, classification, report generation)
- [ ] Event-driven architecture (Pub/Sub)
- [ ] Real-time analytics dashboard (BigQuery + Data Studio)
- [ ] Mobile app (React Native)

---

## Questions & Support

- Maintainer: Jerry Soung (jerry.soung@gmail.com)
- Documentation: https://github.com/jsoung/i4g/tree/main/docs
- API Docs: https://api.i4g.org/docs

---

**Last Updated**: 2025-10-30<br/>
**Next Review**: 2026-01-30
