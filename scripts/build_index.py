"""
Pipeline: OCR results → clean → embed → vector index.

Supports both Chroma (default prototype) and FAISS (production-scale) backends.
"""

import argparse
import json
from pathlib import Path
from typing import List

from i4g.ingestion.preprocess import prepare_documents
from i4g.store.vector import VectorStore


def build_ids(sources: List[str]) -> List[str]:
    """Generate deterministic IDs for source chunks."""
    counts = {}
    ids = []
    for src in sources:
        counts[src] = counts.get(src, 0) + 1
        ids.append(f"{src}::chunk{counts[src]}")
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local vector index from OCR output.")
    parser.add_argument("--input", default="data/ocr_output.json", help="Path to OCR results JSON.")
    parser.add_argument(
        "--backend",
        choices=["chroma", "faiss"],
        default="faiss",
        help="Vector backend to use.",
    )
    parser.add_argument("--persist-dir", default=None, help="Override persistence directory (optional).")
    parser.add_argument("--model", default="nomic-embed-text", help="Embedding model name.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove any existing index before building.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"OCR output not found at {input_path}. Run scripts/run_ocr.py first.")

    with input_path.open() as f:
        ocr_results = json.load(f)

    docs = prepare_documents(ocr_results)
    if not docs:
        print("⚠️ No OCR documents available. Nothing to index.")
        return

    texts = [d["content"] for d in docs]
    sources = [d["source"] for d in docs]
    metadatas = [{"source": src} for src in sources]
    ids = build_ids(sources)

    store = VectorStore(
        backend=args.backend,
        persist_dir=args.persist_dir,
        embedding_model=args.model,
        reset=args.reset,
    )
    store.add_texts(texts, metadatas=metadatas, ids=ids)
    store.persist()

    print(f"✅ {args.backend.upper()} index built and saved to {store.persist_dir}.")


if __name__ == "__main__":
    main()
