# i4g - Scam/Spam Data Processing Toolkit

This repository contains a collection of Python scripts for processing and augmenting datasets related to scams, spam, and other fraudulent activities. The tools help in normalizing data, masking PII, and generating synthetic data for analysis and model training.

## Features

*   **Data Bundling**: Aggregate multiple public scam/spam datasets into a unified JSONL format.
*   **PII Masking**: Automatically find and redact Personally Identifiable Information (PII) like emails, phone numbers, and URLs.
*   **Text Chunking**: Split large text documents into smaller, manageable chunks suitable for RAG systems.
*   **Synthetic Data Generation**: Create realistic chat-style screenshot images from text conversations.

## Scripts

### `build_scam_bundle.py`

Downloads and processes several public scam/spam datasets (e.g., from Hugging Face and Zenodo). It masks PII, chunks the text, and saves the output as a normalized JSONL file.

**Usage:**
```bash
python3 scripts/build_scam_bundle.py --outdir data/bundles --chunk_chars 800
```

### `synthesize_chat_screenshots.py`

Generates synthetic chat screenshots (PNG images) from a JSONL file containing text messages. This is useful for creating visual training data.

**Usage:**
```bash
python3 scripts/synthesize_chat_screenshots.py --input data/bundles/ucirvine_sms.jsonl --limit 50
```

## Installation

1.  Clone the repository:
    ```bash
    git clone <your-repo-url>
    cd i4g
    ```

2.  It is recommended to use a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```