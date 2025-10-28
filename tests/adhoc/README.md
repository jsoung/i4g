# Ad-Hoc Test Scripts

This directory contains a collection of ad-hoc scripts for quick testing, demonstration, and experimentation with different components of the `i4g` project. These are not automated unit tests but are useful for development and verification.

## Dashboard and Manual Tests

### `analyst_dashboard_demo.py`
-   **Description:** Demonstrates the analyst dashboard functionality, showcasing how data is visualized and interacted with in the `i4g` project.
-   **Usage:** `python tests/adhoc/analyst_dashboard_demo.py`

### `manual_ingest_demo.py`
-   **Description:** A manual, end-to-end smoke test for the full ingestion and retrieval pipeline. It initializes the stores, ingests two sample scam cases, and then performs a similarity query to verify the results.
-   **Usage:** `python tests/adhoc/manual_ingest_demo.py`

### `manual_report_demo.py`
-   **Description:** A manual test for generating reports based on predefined data. It verifies the report generation logic without exporting.
-   **Usage:** `python tests/adhoc/manual_report_demo.py`

### `manual_report_export_demo.py`
-   **Description:** A manual, end-to-end smoke test for the full report generation and export pipeline. It uses a text query to generate a report and saves it locally as a `.docx` file.
-   **Usage:** `python tests/adhoc/manual_report_export_demo.py`

### `manual_review_demo.py`
-   **Description:** A script for manually reviewing and verifying the results of the fraud classification pipeline.
-   **Usage:** `python tests/adhoc/manual_review_demo.py`

### `manual_task_demo.py`
-   **Description:** Demonstrates the manual execution of tasks in the pipeline, useful for debugging and verifying individual components.
-   **Usage:** `python tests/adhoc/manual_task_demo.py`

## Core Component Tests

### `bge_embed_server.py`
-   **Description:** Starts a simple FastAPI server to serve embeddings using the `BAAI/bge-small-en` model.
-   **Usage:** `python tests/adhoc/bge_embed_server.py`

### `build_scam_bundle.py`
-   **Description:** Downloads and processes several public scam/spam datasets (e.g., from Hugging Face and Zenodo). It masks PII, chunks the text, and saves the output as a normalized JSONL file ready for ingestion.
-   **Usage:** `python tests/adhoc/build_scam_bundle.py --outdir data/bundles --chunk_chars 800`

### `classify_text.py`
-   **Description:** A command-line tool to quickly test the full fraud classification pipeline on a piece of text. It extracts entities and then provides a classification score and explanation.
-   **Usage:** `python tests/adhoc/classify_text.py "Sample scam text to analyze."`

### `hf_embedding.py`
-   **Description:** A test snippet for calling the Hugging Face Inference API to get embeddings. Requires a valid HF API token.
-   **Usage:** `python tests/adhoc/hf_embedding.py`

### `ocr_extract_texts.py`
-   **Description:** Runs Tesseract OCR on all PNG images in the `./chat_screens/` directory and saves the recognized text to `outputs/ocr_output.jsonl`.
-   **Usage:** `python tests/adhoc/ocr_extract_texts.py`

### `paddle_vs_tesseract.py`
-   **Description:** Compares the OCR output and performance of Tesseract vs. PaddleOCR for a given image file.
-   **Usage:** `python tests/adhoc/paddle_vs_tesseract.py --image <path_to_image>`

### `test_ingest_and_search.py`
-   **Description:** Tests the ingestion of data and performs a search query to validate the pipeline's functionality.
-   **Usage:** `python tests/adhoc/test_ingest_and_search.py`

### `test_ollama_connection.py`
-   **Description:** A simple script to verify the connection to a running Ollama server by sending a sample chat message.
-   **Usage:** `python tests/adhoc/test_ollama_connection.py`

### `test_paddle.py`
-   **Description:** A basic test script for running PaddleOCR on a sample image and viewing the output.
-   **Usage:** `python tests/adhoc/test_paddle.py`

### `test_store_structured.py`
-   **Description:** A script for testing the basic CRUD (Create, Read, Update, Delete) operations of the `StructuredStore` (SQLite backend).
-   **Usage:** `python tests/adhoc/test_store_structured.py`

### `test_store_vector.py`
-   **Description:** A script for testing the `IngestPipeline` and the vector store. It ingests a single classified case and then runs a similarity query.
-   **Usage:** `python tests/adhoc/test_store_vector.py`

### `synthesize_chat_screenshots.py`
-   **Description:** Generates synthetic chat screenshot PNG images from a JSONL file containing text messages. This is useful for creating visual training data for OCR.
-   **Usage:** `python tests/adhoc/synthesize_chat_screenshots.py --input <path_to_jsonl> --limit 20`
