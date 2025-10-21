# i4g - Scam/Spam Data Processing Toolkit

This repository contains a collection of Python scripts for processing and augmenting datasets related to scams, spam, and other fraudulent activities. The tools help in normalizing data, masking PII, and generating synthetic data for analysis and model training.

## Features

*   **Data Bundling**: Aggregate multiple public scam/spam datasets into a unified JSONL format.
*   **PII Masking**: Automatically find and redact Personally Identifiable Information (PII) like emails, phone numbers, and URLs.
*   **Text Chunking**: Split large text documents into smaller, manageable chunks suitable for RAG systems.
*   **Synthetic Data Generation**: Create realistic chat-style screenshot images from text conversations.

## Project Goals

The primary goal of this project is to build a comprehensive system to combat online scams, with a particular focus on **crypto and romance scams** targeting **senior citizens**.

The envisioned workflow includes:

1.  **Data Ingestion**: Use Optical Character Recognition (OCR) to scan and extract text from chat histories and screenshots of potential scam interactions.
2.  **Knowledge Base Creation**: Process the extracted text to build a structured knowledge base of scam scenarios, tactics, and scripts.
3.  **Scam Detection**: Develop a user-facing tool that leverages this knowledge base (e.g., via a RAG system) to answer user queries and help them determine if they are being scammed.
4.  **Intelligence & Enforcement**:
    *   Extract structured data from the knowledge base for large-scale analysis.
    *   Apply machine learning techniques to identify patterns and cross-reference information.
    *   Generate investigation reports to assist law enforcement in identifying and apprehending criminals.

## Starting Ragflow on Apple Silicon
[Build RAGFlow Docker image](https://ragflow.io/docs/dev/build_docker_image)