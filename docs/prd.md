> [!NOTE]
> This PRD serves as an initial communication document for the i4g team. It will evolve as experimentation and architectural design progress.


# Product Requirements Document (PRD)

## Overview
**i4g** is an experimental platform designed to detect, analyze, and help prevent **crypto and romance scams**, particularly those targeting **senior citizens**. The system ingests chat histories, screenshots, and related materials, performs OCR and semantic analysis, and assists victims, analysts, and law enforcement in identifying and tracking scam operations.

## Objectives
- Detect potential scam communications using AI-driven semantic and structured analysis.
- Build a growing knowledge base of scam patterns for educational and investigative purposes.
- Facilitate collaboration between fraud analysts and law enforcement agencies.
- Empower victims to verify suspicious conversations early and access intelligent chat-based assistance.

## Assumptions
- All software, models, and tools used in the current development phase are **free and open source**.
- If budget becomes available, components may be replaced with **paid or commercial alternatives** where appropriate for performance or reliability improvements.
- While the system is designed to be **runnable on Apple Silicon (e.g., M3)** for development convenience, **production deployment** will target **cloud-based Linux environments** with sufficient CPU, memory, and **GPU acceleration** when available.

## Personas
| Persona | Description | Goals | Pain Points |
|----------|--------------|--------|--------------|
| **Victim (Senior Citizen)** | Engaged in suspicious online conversations (crypto or romance) | Understand whether they are being scammed; get AI chat assistance; voluntarily share data to help others | Fear, shame, lack of technical literacy |
| **Fraud Analyst** | Reviews borderline or uncertain classifications | Validate or reject suspected scams; provide structured annotations | Overwhelming data volume, repetitive analysis |
| **Scammer (Adversarial Persona)** | Operates scams via social media, dating apps, or crypto groups | Deceive victims for money or data | Increasing AI
| **Law Enforcement Officer** | Receives summarized, evidence-rich reports | Use aggregated evidence to prosecute scammers | Lack of structured data from victims |

## Use Cases
### Victim Verification & Assistance
   - A user visits the i4g website and interacts with a **chat helper** powered by LLMs.
   - The system provides **real-time guidance** to help identify suspicious activity and protect the user from further harm.
   - Victims can optionally **upload chat histories or screenshots** to contribute to the knowledge base.
   - Uploaded data is processed via OCR (Tesseract) and semantic extraction (LangChain + Ollama).
   - Classification outcomes:
     - **Likely Scam** → Added to knowledge base.
     - **Unclear** → Queued for analyst review.
     - **False Positive** → Discarded.

### Fraud Analyst Review
   - Analysts use a web-based dashboard to review queued cases.
   - They can annotate each case with relevant notes or metadata.
   - Each case is then marked as **accepted** (True Positive) or **rejected** (False Positive).
   - Accepted cases, along with annotations, are integrated into the knowledge base for future training and analysis.

### Knowledge Base Growth
   - True Positive samples enrich embeddings and structured data stores.
   - The knowledge base becomes queryable for pattern recognition and cross-referencing of scam entities.

### Law Enforcement Escalation & Automated Reporting
   - When related scams surpass an internal severity threshold, the system:
     - Aggregates related entities (names, accounts, wallets, IPs, screenshots).
     - Uses a **RAG and Agentic pipeline** to generate comprehensive, evidence-based reports.
     - These reports follow **standardized templates** (e.g., FBI or Interpol formats) and are **machine-generated** with charts, tables, and contextual evidence—**not manually compiled**.

## Functional Requirements
- **Ingestion Layer**
  - OCR via Tesseract for screenshots.
  - Text normalization, PII masking, and language detection.

- **Extraction Layer**
  - LangChain-based semantic NER (names, locations, crypto wallet IDs, emotional tone).

- **Knowledge Base & Retrieval Layer**
  - Vector store (ChromaDB or FAISS) + structured JSON store.

- **Classification Layer**
  - LLM-assisted probabilistic scoring for scam likelihood.

- **Human-in-the-loop Review**
  - Web dashboard for analysts to review, annotate, and classify cases.

- **Reporting & Escalation**
  - Automated RAG + Agentic pipelines for generating evidence reports with structured templates.

## Non-Functional Requirements
- Lightweight, CPU-optimized pipeline for local testing (Apple Silicon compatible).
- Scalable, containerized deployment in cloud Linux environments.
- Optional GPU acceleration for inference-heavy workloads.
- Data privacy: all sensitive information is anonymized and redacted.

## Milestones
## ✅ Updated Development Milestones

| Milestone | Description | Status |
|------------|-------------|--------|
| **M1** | OCR + Extraction (Tesseract + LangChain + Ollama) | ✅ Completed |
| **M2** | Semantic NER + Structured Entity Extraction | ✅ Completed |
| **M3** | Fraud Classification + Confidence Scoring | ✅ Completed |
| **M4** | Structured & Vector Storage (Database + Chroma Integration) | ✅ Completed |
| **M5** | Analyst Review Interface (Web Dashboard) | ✅ Completed |
| **M6** | Automated Law Enforcement Report Generation (RAG + Agentic) | ⚙️ Ongoing |

### M4: Structured Storage & Retrieval
#### Objective
Create a robust storage and retrieval layer that turns processed scam reports (from semantic extraction and classification) into a structured, queryable, and semantically searchable knowledge base. This forms the foundation for RAG-based reporting, analyst tools, and law enforcement collaboration.

#### Scope
The M4 milestone covers two storage modalities:
1. Structured store – for relational data (entities, classifications, metadata)
1. Vector store – for semantic embeddings (contextual similarity search)

#### Key Functionalities
* Persist scam cases as structured records
* Store embeddings for semantic similarity
* Provide query and retrieval APIs for both structured and vector lookups
* Enable hybrid retrieval (structured + semantic)
* Support data flow from M3 classification to M5 reporting

#### Implementation Plan
| Step | Module | Description | Output |
|---|---|---|---|
| M4.1 | schema.py | Define ScamRecord dataclass and helpers | Dataclass & schema utils |
| M4.2 | structured.py | Implement local persistence layer (SQLite) | Record CRUD API |
| M4.3 | vector.py | Add semantic embedding and retrieval logic | Embedding store |
| M4.4 | ingest.py | Implement ingestion pipeline | Unified record ingestion |
| M4.5 | retriever.py | Build hybrid retrieval interface | Combined semantic+structured search |
| M4.6 | tests/unit/ | Add deterministic unit tests for all modules | |

#### Future Extension
* Optional transition to PostgreSQL for production
* Distributed vector store support (Milvus, Pinecone)
* Integration with law enforcement export pipeline (M5)
* Incremental ingestion and record versioning

## Success Metrics
- ≥90% accuracy on detecting scam intent in validation datasets.
- Reduction of analyst review load by ≥70%.
- Successful generation of structured reports for ≥3 distinct scam clusters.

## Next Steps
- Expand persona details with anonymized real examples.
- Define schema for the knowledge base and structured entities.
- Begin drafting the Technical Design Document (TDD) aligned with this PRD.

## Reporting Updates

Reports are now exported as `.docx` files instead of Google Docs. This change improves compatibility, simplifies the export process, and removes the dependency on Google Cloud credentials.
