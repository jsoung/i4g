# Technology Evaluation Matrix (Open-First, GCP-Only Target)

_Last updated: 6 Nov 2025_

This document captures candidate technologies to replace DT-IFG’s Azure-centric stack while honoring the migration plan principles (open, modern, low-cost, privacy-first). Each domain lists 2–3 viable options with trade-offs, followed by the recommended direction for Milestone 2 architecture design.

## Identity & Access Control

| Option | Alignment w/ Goals | Ops Complexity | Cost | Notes |
|---|---|---|---|---|
| **Google Cloud Identity / Identity Platform (OIDC)** | ✅ Native to GCP, supports OAuth/OIDC, MFA, integrates with Firebase/Auth; good balance of open protocols and managed service | Low (managed) | Free tier + pay-as-you-go | Fastest path to production; easy to federate with future IdPs; suits volunteer analysts |
| **authentik (self-hosted OSS IdP)** | ✅ OSS, self-hostable on Cloud Run/GKE; supports modern standards | Medium (needs deployment + upgrades) | Infra + maintenance time | More control but higher burden; good if we later need on-prem / multicloud control |
| **Keycloak (self-hosted)** | ✅ Mature OSS, wide protocol support | Medium/High (heavier footprint) | Infra cost | Robust but heavier than authentik; best if we need advanced federation/legacy protocols |

**Recommendation**: Use **Google Cloud Identity Platform** for MVP to minimize ops; design the auth layer (scopes, roles) so we can swap to authentik/Keycloak if we ever need full OSS control.

## Retrieval / Search (Vector + Hybrid)

| Option | Alignment w/ Goals | Ops Complexity | Cost | Notes |
|---|---|---|---|---|
| **Vertex AI Search** | ✅ Fully managed, integrates with GCS/Firestore, supports hybrid search, aligns with LangChain via connectors | Low | Free tier + usage-based | Proprietary but built on open APIs; fastest path to production |
| **AlloyDB + pgvector (managed PostgreSQL)** | ✅ OSS engine with managed ops, pgvector extension for embeddings | Medium | Free trial + usage-based | Requires building retrieval API layer; good balance between control and managed ops |
| **OpenSearch (self-managed on GCP)** | ✅ OSS, supports vector + keyword search | High (cluster management) | Compute + storage | Maximum control but highest ops burden; consider only if scale/feature needs exceed managed options |

**Recommendation**: Prototype both **Vertex AI Search** (managed) and **AlloyDB pgvector** (open) during Milestone 2. Choose the one that delivers required relevance while keeping operations lean; default to AlloyDB if vendor lock-in becomes a concern.

## LLM Hosting / Inference

| Option | Alignment w/ Goals | Ops Complexity | Cost | Notes |
|---|---|---|---|---|
| **Vertex AI (Gemini / Claude / open models)** | ✅ Managed, secure, integrates with GCP IAM | Low | Usage-based (credits possible) | High quality, turnkey; less “open” but pragmatic |
| **Self-managed Ollama on Cloud Run GPU** | ✅ OSS stack, total control, LangChain-friendly | Medium (GPU provisioning, scaling) | GPU costs | Aligns with open principle; needs GPU budget and ops playbooks |
| **Self-hosted open models via Hugging Face Inference Endpoints** | ✅ Open models with managed infra | Medium | Usage-based | Good middle ground; multi-cloud; consider for redundancy |

**Recommendation**: Build initial RAG pipeline against **Vertex AI** for reliability, but maintain compatibility with **self-managed Ollama** so we can pivot to a fully open stack if funding or policy dictates.

## Data Storage (Structured + Unstructured)

| Option | Use Case | Alignment | Notes |
|---|---|---|---|
| **Cloud Storage** | Evidence blobs, generated reports | ✅ Managed, S3-compatible, easy signed URLs | Replace Azure Blob storage |
| **Firestore (Native mode)** | Case metadata, analysts, PII tokens | ✅ Already in use; integrate with PII vault pattern | Ensure HIPAA-like security; use dedicated service accounts |
| **AlloyDB / Cloud SQL (Postgres)** | Structured ingestion data migrated from Azure SQL | ✅ Open (Postgres); managed | Evaluate if relational querying needed; otherwise BigQuery |
| **BigQuery** | Analytics, cross-case insights | ✅ Serverless, open-compatible | Optional if we need analytics beyond Firestore |

## Orchestration & Batch Processing

| Option | Alignment | Notes |
|---|---|---|
| **Cloud Run Jobs + Scheduler** | ✅ Serverless, minimal ops | Replace Azure Functions timers |
| **Workflows** | ✅ Managed automation for multi-step pipelines | Good for ingestion sequences |
| **Composer (Airflow)** | Neutral (proprietary service for OSS Airflow) | Only if pipelines grow complex |

## Secret Management & IAM

- **Secret Manager** remains core (already in DT-IFG). Enforce per-service accounts with least privilege.
- Adopt **Workload Identity Federation** where cross-cloud access is required (e.g., residual Azure integrations during transition).

## Observability Stack

| Option | Alignment | Notes |
|---|---|---|
| **Cloud Logging + Monitoring** | ✅ Managed, integrates with Cloud Run | Baseline |
| **OpenTelemetry collectors** | ✅ Standards-based, export to GCP or third-party | Consider for future multi-cloud needs |
| **Error Reporting (Stackdriver)** | ✅ Minimal setup | Add alerts for ingestion/chat pipelines |

## Summary of Recommended Direction

1. **Identity**: Start with Google Cloud Identity Platform; design auth flows with open protocols so we can switch to authentik later if needed.
2. **Retrieval/Search**: Prototype Vertex AI Search and AlloyDB pgvector; pick the solution balancing open alignment and time-to-value.
3. **LLM**: Build RAG pipeline on Vertex AI while keeping LangChain abstraction to enable Ollama self-hosting if desired.
4. **Storage**: Cloud Storage + Firestore foundational; evaluate AlloyDB or BigQuery based on ingestion schema needs.
5. **Orchestration**: Cloud Run Jobs + Scheduler for ingestion; Workflows if multi-step coordination required.
6. **Observability**: Structured logging with Cloud Logging/Monitoring; add OpenTelemetry emitters later if multi-cloud observability becomes necessary.

Next step: integrate these recommendations into `docs/dt-ifg/future_architecture.md` by describing how each component fits into the end-state topology.
