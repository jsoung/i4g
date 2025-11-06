# Milestone 1 – Capability Gap Analysis (DT-IFG → i4g)

_Last updated: 6 Nov 2025_

## Executive Summary
- DT-IFG currently depends on a **hybrid Azure + GCP** stack; i4g targets an **all-GCP** implementation. Most functional gaps stem from Azure-specific ingestion, search, and chatbot services that i4g must re-create with GCP-native components or open-aligned managed services.
- i4g's target architecture introduces **privacy-first workflow (PII vault, tokenization)**, structured reporting, and Cloud Run deployment. These are not yet present in DT-IFG, so we must ship them before cutover to avoid regressions in privacy and volunteer operations.
- The plan assumes we will re-evaluate existing i4g prototype choices (Firebase Auth, bespoke LangChain/Ollama stack, etc.) and select modern, open, standards-based alternatives where they offer clearer paths to interoperability and sustainability.
- The largest migration risks are: (1) porting Azure ingestion/search pipelines, (2) replicating the live chat + search experience with the chosen open RAG stack, and (3) establishing production-grade IAM and observability in GCP.

## Capability Matrix

| Capability Area | DT-IFG (Current State) | i4g Target (Docs + Code) | Gap / Risk | Migration Notes |
|---|---|---|---|---|
| **Authentication & Access Control** | Firebase Authentication with before-sign-in trigger; minimal role separation; analysts sign in via Firebase | OAuth 2.0 / OIDC provider (Google Identity, Authentik, etc.) with role-based access; Firestore security rules tied to `analysts` collection | Medium – need to migrate user identities + approvals off Firebase; ensure victim + analyst flows coexist | Run a short selection exercise (Google Identity vs OSS IdP) during Milestone 2; consider short-term bridge via Firebase → OIDC federation |
| **Analyst Dashboard** | Next.js (Firebase Hosting) UI with callable functions; basic chat & document viewers | Streamlit dashboard (Cloud Run) with OAuth, case queues, PII masking | Medium – UI paradigms differ; Streamlit dashboard not yet feature-complete with DT-IFG front-end (chat history, document previews) | Prioritize parity features: queue filters, document viewer, chat transcript display; reuse existing Firestore data model |
| **Victim Intake & Chat Experience** | Real-time chat backed by Azure chatbot API (Cognitive Search indices + functions) | Planned FastAPI endpoints + LLM pipeline (Ollama/Vertex AI) for intake and assistance | High – i4g chat helper not production-ready; Azure chatbot must remain until GCP RAG stack matches quality | Milestone 2/3 must include RAG pipeline hardening + evaluation; consider staged rollout or dual-running chat APIs |
| **Case Intake / Evidence Upload** | Azure Functions ingest Google Forms, GroupsIO, account extracts into Azure Blob/SQL; callable GCP function only issues SAS URLs | i4g ingestion modules (OCR, normalization) exist in code but not deployed; target is Cloud Run pipelines writing to Cloud Storage + Firestore/Chroma | High – ingestion is Azure-only today; i4g pipelines need production deployment, scheduling, and storage redesign | Inventory each Azure ingestion job; design equivalent GCP workflows (Cloud Scheduler + Cloud Run jobs) and migrate data stores |
| **Data Storage** | Firestore (user metadata); Azure Blob (documents); Azure SQL (structured data); Azure Cognitive Search (indices) | Firestore (cases + analysts + PII vault), Cloud Storage (evidence), Chroma/FAISS → eventually managed vector DB; optional Cloud SQL | High – need data migration (Blob→GCS, SQL→Firestore/Cloud SQL) and new search store | Define migration scripts + cutover sequencing in Milestone 4; evaluate Vertex AI Search vs self-managed vector store |
| **PII Protection & Tokenization** | Limited; Firestore stores user metadata; Azure ingestion likely holds raw PII; no centralized tokenization | Core requirement: immediate PII tokenization, encrypted `/pii_vault`, masked UI views | High – must retrofit PII controls before production go-live | Implement tokenization service early; backfill existing data; ensure audit trails |
| **Search & Retrieval** | Azure Cognitive Search APIs provide vector/hybrid search; callable functions proxy results | Target stack: LangChain-compatible retrieval layer (Vertex AI Search, AlloyDB PGVector, OpenSearch, etc.) with open schema control | High – i4g needs scalable vector store + hybrid search to match Azure relevance | Evaluate Vertex AI Search vs managed PGVector/OpenSearch; build migration path for indices |
| **LLM / RAG Pipeline** | Azure-hosted chatbot service with proprietary prompts; GCP functions call external API | Candidate stack: LangChain orchestration with either self-managed (Ollama), Vertex AI, or other open LLM endpoints | Medium – need production-ready inference (cost, latency) and prompt parity | Prototype two options (self-managed vs managed) and select based on openness, cost, and maintainability |
| **Reporting & Exports** | Limited evidence of automated reports; manual processes likely dominate | Automated PDF report generation, digital signatures, bulk export planned | Medium – new functionality to build; no regression risk but schedule impact | Implement reporting after data model stabilized; confirm legal format requirements |
| **Scheduling & Automation** | Azure Functions timers handle ingestion; no Cloud Scheduler jobs in GCP | Cloud Scheduler expected to orchestrate Cloud Run jobs/tasks | Medium – must recreate automation in GCP with least privilege accounts | Document each schedule (frequency, owners); provision equivalent Scheduler jobs with monitoring |
| **IAM & Secrets** | Default compute SA w/ Editor, shared secrets in Secret Manager, limited role separation | Dedicated service accounts per service, strict least privilege, Secret Manager w/ rotation | Medium – need cleanup during migration; risk of privilege creep if left late | Tackle IAM redesign alongside new deployments to avoid rework |
| **Observability & Ops** | Minimal Cloud Logging; no structured metrics or alerting | Structured logging, Cloud Monitoring dashboards, alerting defined | Medium – implement logging patterns in new services; add uptime checks pre-cutover | Build logging/monitoring baseline in parallel with new Cloud Run services |
| **CI/CD & Infrastructure as Code** | Manual Firebase deploys; Cloud Build used ad-hoc; no Terraform | GitHub Actions + Terraform/infra repo envisioned (not implemented) | Low/Medium – nice-to-have for sustainability; not a hard blocker but improves velocity | Milestone 3 should codify pipelines; plan Terraform state/storage |
| **Documentation & Runbooks** | Mix of docx and ad-hoc notes; discovery bundle captured; not version-controlled | Markdown docs in repo; asynchronous updates planned | Low – already improving; ensure volunteer onboarding captures Azure context | Keep docs updated per milestone; migrate remaining docx content into repo |

## Azure-Only Dependencies Requiring Replacement
1. **Cognitive Search indices** → design equivalent in Vertex AI Search or managed PGVector + text embeddings.
2. **Azure Blob Storage + SAS issuance** → migrate files into Cloud Storage; replace callable function with signed URLs or Identity-Aware access.
3. **Azure Functions ingestion jobs** → reimplement with Cloud Run Jobs/Functions + Scheduler; ensure connectors for Google Forms, GroupsIO, financial data sources.
4. **Azure SQL** → migrate structured data to Cloud SQL (Postgres) or Firestore/BigQuery depending on query patterns.
5. **Azure chatbot API** → replace with GCP-hosted RAG service (FastAPI + LangChain + Vertex/Ollama) including prompt parity and evaluation metrics.

## Quick Wins
- **IAM Hardening**: Create dedicated service accounts and adjust function configs before new workloads launch.
- **Documentation Migration**: Convert Azure workflow `.docx` files into markdown to unblock knowledge transfer.
- **Secret Inventory**: Catalog Secret Manager entries (Azure keys, chatbot API keys) and define rotation cadence.

## High-Risk Areas
- **Data Pipeline Porting**: Rebuilding ingestion + search pipelines in GCP is multi-week effort with testing dependencies.
- **Chat Experience Quality**: Need quantitative benchmarks to ensure i4g LLM responses meet or exceed Azure quality before cutover.
- **Data Migration & Parity Testing**: Moving blobs, indices, and structured records demands staged validation and rollback planning.

## Next Steps
1. Validate matrix with DT-IFG stakeholders to capture any missing capabilities (especially Azure-only jobs not in export).
2. Start drafting future-state architecture (`docs/future_architecture.md`) using gaps highlighted above.
3. Run lightweight technology evaluations for identity, retrieval, and LLM hosting options to inform Milestone 2 decisions.
4. Inventory required datasets/artifacts for migration (blob containers, SQL schemas, search index definitions) to feed Milestone 4 planning.
