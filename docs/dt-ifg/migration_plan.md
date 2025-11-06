# DT-IFG → i4g Migration Plan (GCP-Only)

_Last updated: 5 Nov 2025_

## 1. Purpose
- Provide a clear path for evolving from the current DT-IFG production system to the next-generation i4g platform.
- Ensure **capability parity** before decommissioning any DT-IFG component.
- Align the team (mostly part-time volunteers) on priorities, deliverables, and status checkpoints.
- Anchor all future work on a **single-cloud (GCP-only)** architecture to reduce complexity.

## 2. Guiding Principles
1. **No Capability Regression** – every DT-IFG feature (ingestion, search, chat, reporting) must exist in i4g before cutover.
2. **GCP-Only Target** – replace Azure Functions, Blob Storage, Cognitive Search, and SQL with GCP equivalents (Cloud Functions/Run, Cloud Storage, Vertex AI Search or managed vector DB, Cloud SQL/Firestore/BigQuery).
3. **Open & Modern Stack** – favor vendor-neutral, open-source, or standards-based components (e.g., OAuth/OIDC, LangChain-compatible services, managed OSS) even if they differ from today’s i4g prototype.
4. **Zero/Low Cost First** – stay within GCP free tier or nonprofit credits; minimize operational overhead.
5. **Privacy & Security First** – maintain or improve DT-IFG’s data controls (Firestore PII vault, Secret Manager, IAM hardening).
6. **Communicate Asynchronously** – concise documentation and status updates for stakeholders with limited availability.

## 3. Milestones & Deliverables

### Milestone 1 — Capability Gap Analysis (Week 1–2)
- **Goals**: Document all DT-IFG capabilities and map them to existing/planned i4g features. Identify functional, data, and operational gaps.
- **Key Activities**:
  - Extract capability list from `system_review.md` (DT-IFG) and i4g docs (`architecture.md`, PRDs, TDD).
  - Build gap matrix (capability → DT-IFG implementation → i4g status → gaps/risks).
  - Highlight “Azure-only” functions that must be ported to GCP.
- **Deliverables**: `docs/gap_analysis.md` (matrix + executive summary).
- **Success Criteria**: Stakeholders agree on completeness of the gap list.

### Milestone 2 — Target GCP Architecture (Week 3–4)
- **Goals**: Design the future-state i4g system entirely on GCP while preserving DT-IFG capabilities.
- **Key Activities**:
  - Produce updated architecture diagrams (logical + deployment) showing GCP services.
  - Define data flow for ingestion, storage, search, chat, and reporting within GCP.
  - Evaluate modern, open-aligned replacements for each capability (identity, search, vector DB, orchestration) and document recommended options.
  - Specify replacements:
    - Azure Functions → Cloud Run/Functions + Scheduler (or equivalent serverless jobs)
    - Blob Storage/SAS → Cloud Storage signed URLs / IAM-based access
    - Cognitive Search → Vertex AI Search, managed PGVector, or other open-compatible retrieval stack
    - Azure SQL → Cloud SQL / Firestore / BigQuery (with preference for open standards)
  - Document security/IAM refactor (least-privilege service accounts, Secret Manager usage).
- **Deliverables**: `docs/future_architecture.md` (diagram, component descriptions, integration notes).
- **Success Criteria**: Architecture approved for implementation; unresolved decisions clearly listed.

### Milestone 3 — Implementation Roadmap (Week 5–6)
- **Goals**: Translate gaps and architecture into executable workstreams with sequencing and owners (even if owner = “TBD/volunteer”).
- **Key Activities**:
  - Break tasks into streams: Data ingestion, Search/RAG, Frontend & UX, IAM/Infra, Observability.
  - Define milestones & dependencies (e.g., ingestion migration needed before chat parity).
  - Estimate effort, propose timeline (even rough) for each stream.
  - Capture tooling/CI/CD changes (e.g., Terraform, GitHub Actions, secret management).
- **Deliverables**: `docs/implementation_roadmap.md` (work breakdown + timeline chart).
- **Success Criteria**: Team agrees the roadmap is actionable; volunteers can pick tasks confidently.

### Milestone 4 — Validation & Migration Plan (Week 7–8)
- **Goals**: Define how we prove parity, migrate data, and cut over without disrupting current users.
- **Key Activities**:
  - Draft test plan covering unit, integration, load, security, and user acceptance.
  - Plan data migration (Azure storage → Cloud Storage, SQL → Cloud SQL/BigQuery, search indices → new vector store).
  - Outline rollout strategy (parallel run, feature flags, rollback steps).
  - Update operational runbooks (monitoring, incident response, key rotations).
- **Deliverables**: `docs/migration_checklist.md` (test matrix + runbooks). Optional supporting scripts.
- **Success Criteria**: All stakeholders sign off on readiness criteria; clear go/no-go checklist.

## 4. Communication & Reporting
- **Status cadence**: Weekly written update (Markdown or Google Doc) summarizing:
  - Milestone progress (traffic-light status)
  - Risks/blockers
  - Next week’s focus
- **Docs of record**: Store all planning artifacts in the `/docs` or `/dtp/system_review/` folder for easy access and version control.
- **Stakeholder briefings**: 30-minute sync every two weeks (if bandwidth allows) with non-technical stakeholders; otherwise share recorded Loom/Slides summary.

## 5. Immediate Next Steps
1. Kick off Milestone 1 by drafting the capability matrix skeleton (`docs/gap_analysis.md`).
2. Circulate this migration plan to the volunteer team for acknowledgement.
3. Collect any missing DT-IFG documentation (e.g., Azure workflow details) needed for the gap analysis.

---

*Prepared for the DT-IFG volunteer team. Update as priorities shift or new constraints emerge.*
