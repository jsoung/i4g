# Implementation Roadmap (Milestone 3 Draft)

_Last updated: 6 Nov 2025_

This roadmap translates the gap analysis and future-state architecture into actionable workstreams. It assumes a single technical contributor (Jerry) with volunteer support for documentation/testing as available.

## 1. Workstreams Overview

| Stream | Description | Key Outputs |
|---|---|---|
| **Identity & Access** | Stand up OIDC auth, roles, and security rules | Auth service, Streamlit + FastAPI integration, IAM policies |
| **Ingestion & Data Pipelines** | Replace Azure ingestion jobs with GCP-native flows | Cloud Run jobs, scheduler configs, Firestore/AlloyDB data loaders |
| **Retrieval & RAG** | Implement chosen retrieval backend + LLM pipeline | Vector store, LangChain orchestration, evaluation harness |
| **Frontend & UX** | Deliver victim intake UI + analyst dashboard parity | Streamlit feature parity, FastAPI endpoints, docs site updates |
| **Security & Observability** | IAM hardening, secrets, logging/monitoring | Terraform modules, alerting policies, PII vault enforcement |
| **Documentation & Ops** | Author runbooks, migration guides, comms plan | Updated docs, migration checklists, volunteer onboarding |

## 2. Timeline Snapshot (Assuming 8-week plan post-Milestone 2)

```
Week 1-2: Identity & Access, Retrieval PoCs
Week 3-4: Ingestion Pipelines, RAG integration
Week 5-6: Frontend parity, reporting automation
Week 7: Observability, IAM cleanup, dry runs
Week 8: Migration rehearsal, documentation freeze
```

## 3. Detailed Tasks by Stream

### 3.1 Identity & Access
- Implement Google Identity Platform auth flows (victim + analyst) via OIDC.
- Configure Streamlit + FastAPI to verify tokens and enforce roles.
- Define Firestore security rules for `/cases`, `/pii_vault`, `/analysts`.
- Terraform IAM: create dedicated service accounts, grant least-privilege roles.
- Stretch: Evaluate authentik deployment on Cloud Run for future OSS control.

### 3.2 Ingestion & Data Pipelines
- Catalog all Azure ingestion jobs (Forms, GroupsIO, account extracts) with frequency and outputs.
- Build Cloud Run job templates with shared `ingestion` package.
- Create scheduler configs via Terraform; store credentials in Secret Manager.
- Implement logging + alerting (failure notifications, retries).
- Backfill historical data from Azure storage/SQL into GCP stores.

### 3.3 Retrieval & RAG
- Complete PoC comparison (Vertex AI Search vs AlloyDB pgvector) with evaluation dataset.
- Provision chosen retrieval store and load initial embeddings.
- Integrate LangChain pipeline with selected LLM host (Vertex AI initially).
- Add evaluation harness (quality metrics, latency, cost monitoring).
- Implement fallback path for self-hosted Ollama if required.

### 3.4 Frontend & UX
- FastAPI endpoints: victim intake, chat, report generation.
- Streamlit dashboard: case queue filters, document viewer, chat transcript, approval workflow.
- Integrate Cloud Storage signed URL flow for evidence download.
- Implement automated PDF report generator (templating, digital signature stub).
- Coordinate with docs site updates for user/analyst instructions.

### 3.5 Security & Observability
- Configure structured logging (OpenTelemetry + Cloud Logging).
- Create Cloud Monitoring dashboards and alert policies.
- Enforce Secret Manager usage, implement key rotation job.
- Penetration-test endpoints (baseline checks, OWASP top 10 review).
- Document incident response plan (who to notify, triage steps).

### 3.6 Documentation & Ops
- Update `system_review.md`, `future_architecture.md`, and runbooks as changes land.
- Write migration scripts/docs: Azure Blob → Cloud Storage, Azure SQL → AlloyDB.
- Prepare volunteer onboarding pack (roles, access requests, coding standards).
- Draft communications plan (weekly async updates, stakeholder briefs).

## 4. Dependencies & Sequencing

| Task | Depends On |
|---|---|
| Retrieval store deployment | Tech evaluation PoCs |
| Chat API release | Retrieval store + LLM pipeline |
| Streamlit parity | Auth & retrieval pipeline |
| Migration rehearsal | All pipelines + reporting complete |

## 5. Execution Notes
- Use feature flags / environment variables to toggle between Azure and GCP-backed services during transition.
- Maintain `docs/dt-ifg/change_log.md` (to be created) to track major decisions for stakeholders.
- Prefer short-lived branches; merge into `main` with CI (tests + lint).

## 6. Immediate Next Actions
1. Finalize tech decisions (identity, retrieval, LLM) via PoC results.
2. Scaffold Terraform repo with project + Cloud Run modules.
3. Stand up skeleton FastAPI + Streamlit services with end-to-end auth.
4. Draft migration scripts outline for Azure data exits.

Update this roadmap as tasks complete or priorities shift.
