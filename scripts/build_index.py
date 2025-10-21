"""
Pipeline: OCR results → clean → embed → FAISS index.
"""

import json

from langchain_core.documents import Document

from i4g.embedding.embedder import get_embedder
from i4g.ingestion.preprocess import prepare_documents
from i4g.store.vector import build_faiss_index, save_index


def main():
    with open("data/ocr_output.json") as f:
        ocr_results = json.load(f)

    docs_dict = prepare_documents(ocr_results)
    docs = [Document(page_content=d["content"], metadata={"source": d["source"]}) for d in docs_dict]

    embedder = get_embedder()
    store = build_faiss_index(docs, embedder)
    save_index(store)

    print("✅ FAISS index built and saved successfully.")


if __name__ == "__main__":
    main()
