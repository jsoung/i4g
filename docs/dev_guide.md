# Developer Guide — Intelligence for Good (i4g)

This Developer Guide explains how to set up, run, and extend the i4g platform — an experimental system for detecting, analyzing, and reporting online scams (especially crypto and romance scams targeting seniors).

---

## System Overview

i4g combines OCR, language models, semantic entity extraction, classification, and human-in-the-loop review to support law enforcement and victim assistance workflows.

### Core Data Flow

```mermaid
graph TD
A[Chat Screenshots] --> B[OCR (Tesseract)]
B --> C[Semantic Extraction (LangChain + Ollama)]
C --> D[Classification (Rule + LLM)]
D --> E[Ingestion to Knowledge Base]
E --> F[Analyst Review API / Dashboard]
F --> G[Law Enforcement Report Generator]
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
├── tests/
│   ├── unit/
│   └── adhoc/
├── templates/              # Jinja2 report templates
└── scripts/                # CLI & dev utilities
```

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

### OCR + Extraction

```bash
python scripts/run_ocr_pipeline.py --input ./samples/chat_001.png
```

### Semantic NER + Classification

```bash
python scripts/run_semantic_extraction.py --input ./samples/text/
python scripts/classify_text.py "This looks like a scam."
```

### Scam Detection RAG Query

```bash
python scripts/scam_detection_cli.py "Is this a crypto scam?"
```

---

## Analyst Review System

### Backend API

Run the review backend:

```bash
uvicorn i4g.review.api:app --reload
```

Check endpoint:
```
http://localhost:8000/docs
```

### Streamlit Analyst Dashboard

```bash
streamlit run tests/adhoc/analyst_dashboard_demo.py
```

Allows analysts to claim, review, and approve or reject fraud cases.

---

## Report Generation

### Manual Report Preview

```bash
python tests/adhoc/manual_report_demo.py
```

### GDoc Export (if Google API configured)

```bash
python scripts/export_report_gdoc.py --case-id CASE123
```

---

## Developer Utilities

- **Build FAISS Index:**
  ```bash
  python scripts/build_index.py
  ```

- **Run All Unit Tests:**
  ```bash
  pytest -v
  ```

- **Lint and Format:**
  ```bash
  black src tests
  ```

The `scripts/` directory includes additional CLI helpers (for example `generate_context_snapshot.sh` and `query_kb.py`); run them with `--help` to see available options.

---

## Notes for Cloud Deployment

- Production environment expected to run on Linux (GCP or AWS).
- Review API and worker tasks should run as services.
- GDoc exporter requires Google service account credentials.
- Use `docker/` folder for containerized deployment (optional).
