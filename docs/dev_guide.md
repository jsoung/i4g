# Developer Guide — Intelligence for Good (i4g)

This Developer Guide explains how to set up, run, and extend the i4g platform — an experimental system for detecting, analyzing, and reporting online scams (especially crypto and romance scams targeting seniors).

---

## System Overview

i4g combines OCR, language models, semantic entity extraction, classification, and human-in-the-loop review to support law enforcement and victim assistance workflows.

### Core Data Flow

```mermaid
graph TD
    A["Chat Screenshots"] --> B["OCR (Tesseract)"]
    B --> C["Semantic Extraction<br/>(LangChain + Ollama)"]
    C --> D["Classification<br/>(Rule + LLM)"]
    D --> E["Ingestion to Knowledge Base"]
    E --> F["Analyst Review API / Dashboard"]
    F --> G["Law Enforcement Report Generator"]
```

---

## Project Layout

```
i4g/
├── src/i4g/
│   ├── ocr/                # OCR via Tesseract
│   ├── extraction/         # NER + Semantic Extraction
│   ├── classification/     # Fraud classifiers
│   ├── embedding/          # Vector embeddings
│   ├── store/              # Vector + Structured + Review DB
│   ├── rag/                # RAG pipeline & retrieval
│   ├── reports/            # Report generation & GDoc export
│   ├── review/             # FastAPI review service
│   ├── worker/             # Background tasks (report gen)
│   └── ...
├── data/                   # Runtime artifacts (bundles, chat_screens, reports, SQLite)
├── tests/
│   ├── unit/
│   └── adhoc/
├── templates/              # Jinja2 report templates
└── scripts/                # Production/admin CLI utilities
```

**Operational vs. Developer Utilities**

- `scripts/`: automation you can run in production or staging (OCR pipeline, semantic extraction, index rebuilds).
- `tests/adhoc/`: developer-only demos, diagnostics, data synthesizers, and lightweight utilities (including context snapshots).

---

## Local Datastore

The `data/i4g_store.db` file is a local SQLite database used for storing application data, including:

-   **Structured Data:** Extracted entities, classification results, and other structured information.
-   **Vector Embeddings:** Embeddings of text for semantic search.
-   **Review Data:** Data for the analyst review system.

This file is created automatically when you run the application and is not meant to be shared or committed to version control. If you want to start with a fresh database, you can delete this file.

---

## Setup Instructions

### Prerequisites

- macOS or Linux (Apple Silicon M3 tested)
- Python ≥ 3.11
- Tesseract OCR installed (`brew install tesseract`)
- Ollama running locally (`ollama serve`)
- FAISS (for vector store)
- Optional: Google Cloud SDK (for GDoc export)

### Environment Setup

```bash
git clone https://github.com/jsoung/i4g.git
cd i4g
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

To test your setup:

```bash
pytest -q
```


## Running the Core Pipelines

There are also targeted demos under `tests/adhoc/` if you want to exercise a single feature (OCR, extraction, reporting, etc.); check the README in that folder for usage details.

## Restoring Sample Data & Artifacts

If you cleaned out the `data/` directory (or are onboarding to a fresh clone), run these helper scripts before jumping into the demos so you have realistic fixtures to work with.

1. **Download + Normalize Scam Text Bundles**

    ```bash
    python tests/adhoc/build_scam_bundle.py --outdir data/bundles --chunk_chars 800
    ```

    This pulls public-domain scam/phishing corpora via Hugging Face, masks obvious PII, and writes JSONL bundles such as `data/bundles/ucirvine_sms.jsonl` and `data/bundles/bundle_all.jsonl`.

2. **Synthesize Chat Screenshots for OCR Demos**

    ```bash
    python tests/adhoc/synthesize_chat_screenshots.py --input data/bundles/ucirvine_sms.jsonl --limit 20
    ```

    Generated PNGs land in `data/chat_screens/`. That folder is the expected input directory for the OCR script, so you can immediately run:

    ```bash
    python scripts/run_ocr.py --input data/chat_screens
    ```

3. **Reprime SQLite / Vector Stores (optional)**

    ```bash
    python tests/adhoc/manual_ingest_demo.py
    ```

    This seeds `data/manual_demo/` with a structured SQLite DB and a Chroma vector index using two representative scam cases. Rerun as needed whenever you want a clean slate for ingestion demos.

4. **Seed Analyst Review Queue**

    ```bash
    python tests/adhoc/synthesize_review_cases.py --reset --queued 5 --in-review 2 --accepted 1 --rejected 1
    ```

    Populates `data/i4g_store.db` with synthetic review items so the Streamlit dashboard has cases ready to demonstrate claim/accept/reject flows.

Once these assets exist, the downstream scripts referenced below will find usable inputs without manual data hunting.

### Hugging Face API Tokens

Some ad-hoc scripts (for example `tests/adhoc/hf_embedding.py`) call the Hugging Face Inference API. Create a personal access token at <https://huggingface.co/settings/tokens> and expose it before running those scripts:

```bash
export HF_API_TOKEN=hf_xxx    # put this in your shell profile if you use it often
python tests/adhoc/hf_embedding.py "Sample text to embed"
```

Without the token, the API returns `401 Invalid credentials`.

### OCR + Extraction

```bash
python scripts/run_ocr.py --input data/chat_screens
```

That path is where the synthetic screenshots land; swap in another directory if you are running OCR on real evidence.

### Semantic NER + Classification

```bash
python scripts/run_semantic_extraction.py
python tests/adhoc/classify_text.py "This looks like a scam."
```

`run_semantic_extraction.py` reads the OCR output saved to `data/ocr_output.json` by the previous step and writes enriched entities to `data/entities_semantic.json`.

### Scam Detection RAG Query

```bash
i4g-admin query --question "Is this a crypto scam?"
```

---

## Analyst Review System

### Backend API

Run the review backend:

```bash
uvicorn i4g.api.app:app --reload
```

Check endpoint:
```
http://localhost:8000/docs
```

### Streamlit Analyst Dashboard

```bash
streamlit run tests/adhoc/analyst_dashboard_demo.py
```

**Streamlit Analyst Dashboard**

- **Seed data first:** `python tests/adhoc/synthesize_review_cases.py --reset --queued 5` so the queue has items to triage.
- **Launch UI:** `streamlit run tests/adhoc/analyst_dashboard_demo.py` (full workflow for claiming, accepting, and rejecting cases).
- **Search faster:** blend vector + structured lookups, adjust result counts, and paginate without re-running queries; hits tally shows total coverage.
- **Saved search controls:** tag-based grouping, quick presets, CSV export, rename/share/delete, and bulk tag edits directly in the sidebar.
- **Audit trail:** every run lands in `/reviews/search/history`; preview previous runs or replay them from the recent history panel.

---

## Report Generation

### Manual Report Preview

```bash
python tests/adhoc/manual_report_demo.py
```

### GDoc Export (if Google API configured)

```bash
python tests/adhoc/manual_report_export_demo.py
```

Generated `.docx` files are written to `data/reports/` whether you trigger them from the demos, the Streamlit dashboard, or the API.

---

## Developer Utilities

**Core Scripts**

- **Build FAISS index:** `python scripts/build_index.py --backend faiss --reset`
- **Run unit tests:** `pytest -v`
- **Format source:** `black src tests`
- **Snapshot context:** `bash tests/adhoc/generate_context_snapshot.sh --help`

**Saved Search Admin (`i4g-admin`)**

- `i4g-admin export-saved-searches --owner alice --output alice.json`
- `i4g-admin import-saved-searches --shared --input team.json`
- `i4g-admin bulk-update-tags --owner alice --tags urgent wallet --remove legacy`
- `i4g-admin prune-saved-searches --owner alice --tags legacy`

Install locally with `pip install -e .` to expose `i4g-admin` everywhere; run `i4g-admin --help` to browse each subcommand.

---

## Notes for Cloud Deployment

- Production environment expected to run on Linux (GCP or AWS).
- Review API and worker tasks should run as services.
- GDoc exporter requires Google service account credentials.
- Use `docker/` folder for containerized deployment (optional).
