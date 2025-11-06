# Future-State Architecture (DT-IFG → i4g, GCP-Only, Open-Friendly)

_Last updated: 6 Nov 2025_

This document sketches the proposed end-state architecture that replaces DT-IFG’s Azure/GCP hybrid with an all-GCP stack while embracing open standards and minimal vendor lock-in. It reflects the technology evaluations in `technology_evaluation.md` and addresses the gaps identified in `gap_analysis.md`.

## 1. Guiding Objectives

1. **Parity before cutover**: Match or exceed DT-IFG capabilities across ingestion, chat, search, reporting.
2. **Open-first**: Prefer open protocols, OSS-compatible services, or managed offerings that allow future portability.
3. **Volunteer-friendly operations**: Low administrative burden, clear runbooks.
4. **Privacy & security**: Enforce tokenized PII handling, least-privilege IAM, auditable access.
5. **Cost control**: Stay within free tier/nonprofit credits until scale requires upgrades.

## 2. High-Level Topology

```
┌──────────────────────────────────────────────────────────────┐
│                        User Channels                         │
│  Victims (Web/Mobile) | Analysts (Dashboard) | LEO (Reports) │
└────────────┬───────────────────────┬─────────────────────────┘
             │ HTTPS                 │ HTTPS                    │
┌────────────▼───────────────────────▼─────────────────────────┐
│                    Cloud Run (us-central1)                   │
│  ┌────────────────────────┐   ┌───────────────────────────┐  │
│  │ FastAPI API (RAG & API │   │ Streamlit Analyst Portal  │  │
│  │ Gateway)               │   │ (OAuth/OIDC)              │  │
│  └────────────────────────┘   └───────────────────────────┘  │
│             │ REST / gRPC        │ REST / WebSocket           │
└─────┬───────▼────────────────────▼────────────────────────────┘
      │
      │  Async jobs / PubSub (optional)
┌─────▼───────────────────────────────────────────────────────┐
│                  Data & Intelligence Layer                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐ │
│  │ Firestore    │ │ Cloud Storage│ │ Vertex AI Search or  │ │
│  │ (Cases, PII) │ │ (Evidence)   │ │ AlloyDB + pgvector   │ │
│  └─────┬────────┘ └──────┬───────┘ └─────────┬────────────┘ │
│        │                 │                   │              │
│  ┌─────▼────────┐  ┌─────▼────────┐  ┌───────▼───────────┐ │
│  │ PII Vault    │  │ Ingestion     │  │ RAG Orchestration │ │
│  │ Tokenization │  │ Pipelines     │  │ (LangChain)       │ │
│  └──────────────┘  └──────────────┘  └───────────────────┘ │
└─────────────────────────────────────────────────────────────┘
      │                        │                      │
      │ Scheduler triggers     │ Secrets, IAM         │ Telemetry
┌─────▼─────────────┐  ┌───────▼────────────┐  ┌──────▼──────────┐
│ Cloud Scheduler   │  │ Secret Manager     │  │ Logging &       │
│ + Run Jobs        │  │ + Workload ID      │  │ Monitoring       │
└───────────────────┘  └────────────────────┘  └────────────────┘
```

## 3. Key Components

### 3.1 Identity & Access Control
- **Primary option**: Google Cloud Identity Platform (OIDC) with custom user attributes for roles (`victim`, `analyst`, `admin`, `leo`).
- **Fallback / future option**: authentik or Keycloak running on Cloud Run or GKE if we need self-hosted control.
- All services consume tokens via standard OIDC flows; Streamlit and FastAPI share a lightweight auth service (token verification, role enforcement).

### 3.2 API & Presentation Layer
- **FastAPI service** on Cloud Run provides:
  - Victim intake endpoints
  - Chat/RAG endpoints (`POST /api/chat`, `POST /api/cases`)
  - Report generation (`POST /api/cases/{id}/report`)
  - PII tokenization pipeline entry point
- **Streamlit analyst portal** on Cloud Run with OAuth integration, case queues, document viewer (Cloud Storage signed URLs), chat transcript inspection.
- Shared `api` package with domain models and permission checks to keep logic consistent.

### 3.3 Retrieval & RAG
- **LangChain orchestration** deployed in the FastAPI service.
- Embedding + retrieval store options:
  - **Vertex AI Search** (managed) with connectors to Cloud Storage and Firestore.
  - **AlloyDB + pgvector** (open) managed by GCP; maintain schema migrations via Alembic.
- LLM inference:
  - Start with **Vertex AI** models for reliability (Gemini 1.5). Abstracted via LangChain to allow drop-in replacement.
  - Maintain optional path for **Ollama** hosted on Cloud Run GPU instances for cost control / openness.
- Prompt management stored in Firestore/Secrets with versioning to aid governance.

### 3.4 Data Storage & PII Controls
- **Firestore** remains source of truth for cases, analysts, config. Introduce dedicated collection `/pii_vault` with AES-256-GCM encrypted values and token metadata.
- **Cloud Storage** buckets:
  - `i4g-evidence-{env}` for uploads (ingress via signed URL, lifecycle policies).
  - `i4g-reports-{env}` for generated PDFs (access controlled).
- **AlloyDB / Cloud SQL** optional for structured ingestion data migrated from Azure SQL.
- **BigQuery** optional for downstream analytics/monitoring dashboards once data volume grows.

### 3.5 Ingestion Pipelines
- Replace Azure Functions with Cloud Run Jobs or Functions triggered by Cloud Scheduler and Eventarc:
  - Google Forms / Sheets ingestion: `scheduler → Cloud Run job → Fetch & normalize → Store in Firestore/Storage`.
  - GroupsIO / mailboxes: use Workflows for multi-step (fetch, parse, dedupe).
  - Financial account extracts: integrate via partner APIs (to be catalogued) using TF-managed credentials in Secret Manager.
- Logging for each run stored in Cloud Logging with alerts on failure.

### 3.6 Observability & Operations
- Structured JSON logging using OpenTelemetry exporters to Cloud Logging.
- Cloud Monitoring dashboards for ingest success rate, chat latency, Firestore write errors.
- Error Reporting + alert policies (pager/email) for sole maintainer or future on-call rotation.
- Terraform modules (Milestone 3) for reproducible infrastructure.

### 3.7 Security & IAM
- Dedicated service accounts per service (FastAPI, Streamlit, ingestion jobs, scheduler tasks).
- PII vault operations confined to a service account with `roles/datastore.user` + custom encryption permissions.
- Workload Identity Federation for any residual Azure integration during transition.
- Secret Manager used for all credentials, rotated quarterly (automated via Cloud Scheduler function).

## 4. Environment Strategy
- **Projects**: `i4g-prod`, `i4g-staging`, `i4g-dev` (optional). Each with mirrored resources except production restrictions on IAM and logging retention.
- **Branches**: `main` (prod) and `staging` branch tied to staging environment via GitHub Actions.
- **CI/CD**: GitHub Actions workflows deploy to Cloud Run (FastAPI, Streamlit), manage Cloud Run Jobs, run tests (pytest, unit + integration).

## 5. Open-Source Alignment Checklist
- ✅ OIDC-compatible auth (swap between Google Identity and authentik/Keycloak).
- ✅ LangChain orchestration for retrieval pipeline (pluggable vector stores, LLMs).
- ✅ Storage built on open APIs (Firestore has gRPC/REST; Cloud Storage S3-compatible; AlloyDB Postgres-based).
- ✅ Observability via OpenTelemetry-compatible stack.
- ✅ IaC via Terraform (or Pulumi) stored in `infra/` repo.

## 6. Outstanding Decisions (to resolve in Milestone 2)

| Area | Decision Needed | Owners | Due |
|---|---|---|---|
| Identity provider | Finalize initial IdP: Google Identity vs authentik | Jerry | End of Milestone 2 |
| Retrieval backend | Vertex AI Search vs AlloyDB pgvector (PoC metrics) | Jerry | End of Milestone 2 |
| LLM hosting | Primary inference provider + fallback plan | Jerry | Before Milestone 3 |
| Data warehouse | Whether to introduce BigQuery for analytics | Jerry | During Milestone 3 planning |
| Terraform vs other IaC | Confirm tooling for infra repo | Jerry | Start of Milestone 3 |

## 7. Next Steps
1. Build PoC notebooks / scripts to benchmark retrieval quality across Vertex AI Search and AlloyDB pgvector using sample DT-IFG cases.
2. Stand up minimal FastAPI + Streamlit skeletons on Cloud Run (staging project) with Google Identity auth to validate deployment pipeline.
3. Define Terraform module structure (projects, service accounts, storage buckets, Cloud Run services).
4. Document migration runbooks (data export from Azure → GCP) to prepare for Milestone 4.

This architecture will be refined as PoC results come in. Update this document alongside Milestone 2 progress.
