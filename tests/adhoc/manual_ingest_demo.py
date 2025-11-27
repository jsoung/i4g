"""Manual smoke test for the ingestion/retrieval pipeline."""

from __future__ import annotations

import argparse
import pprint
from pathlib import Path
from typing import Sequence

from i4g.store.ingest import IngestPipeline
from i4g.store.structured import StructuredStore
from i4g.store.vector import VectorStore

DEFAULT_STRUCTURED_DB = Path("data/manual_demo/structured_demo.db")
DEFAULT_VECTOR_DIR = Path("data/manual_demo/chroma")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Return CLI arguments describing where to persist demo data."""

    parser = argparse.ArgumentParser(description="Manual ingestion/retrieval smoke test")
    parser.add_argument(
        "--structured-db",
        type=Path,
        default=DEFAULT_STRUCTURED_DB,
        help="Path to the SQLite database used for structured cases",
    )
    parser.add_argument(
        "--vector-dir",
        type=Path,
        default=DEFAULT_VECTOR_DIR,
        help="Directory used for the Chroma vector store",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point for the manual ingestion demo."""

    args = parse_args(argv)
    structured_db = args.structured_db
    vector_dir = args.vector_dir

    structured_db.parent.mkdir(parents=True, exist_ok=True)
    vector_dir.mkdir(parents=True, exist_ok=True)

    structured_store = StructuredStore(str(structured_db))
    vector_store = VectorStore(persist_dir=str(vector_dir))
    pipeline = IngestPipeline(structured_store=structured_store, vector_store=vector_store)

    print("✅ Initialized Structured + Vector stores.")
    print(f"   DB: {structured_db}")
    print(f"   Chroma dir: {vector_dir}\n")

    # ------------------------------------------------------------------
    # Step 1: Ingest two sample scam cases
    # ------------------------------------------------------------------

    samples = [
        {
            "text": "Hi I'm Anna from TrustWallet. Send 50 USDT to verify your wallet.",
            "fraud_type": "crypto_investment",
            "fraud_confidence": 0.91,
            "entities": {
                "people": [{"value": "Anna"}],
                "organizations": [{"value": "TrustWallet"}],
                "crypto_assets": [{"value": "USDT"}],
                "scam_indicators": [{"value": "verification fee"}],
            },
        },
        {
            "text": "Dear John, I love you. Please send Bitcoin to 1FzWL... so we can finally meet.",
            "fraud_type": "romance_scam",
            "fraud_confidence": 0.89,
            "entities": {
                "people": [{"value": "John"}],
                "crypto_assets": [{"value": "Bitcoin"}],
                "wallet_addresses": [{"value": "1FzWL..."}],
                "scam_indicators": [{"value": "money request to meet"}],
            },
        },
    ]

    print("🚀 Ingesting sample cases...")
    for s in samples:
        cid = pipeline.ingest_classified_case(s)
        print(f"   → Stored case_id: {cid}")
    print()

    # ------------------------------------------------------------------
    # Step 2: Query similar cases
    # ------------------------------------------------------------------

    query = "TrustWallet verification"
    print(f"🔍 Querying for: '{query}' ...\n")
    results = pipeline.query_similar_cases(query, top_k=3)

    if not results:
        print("No results found. Ensure Ollama and Chroma are running.")
        return

    print("🧭 Similar Cases:")
    for r in results:
        pprint.pprint(r)
        print("-" * 60)

    print("\n✅ Manual ingestion + retrieval test completed.")


if __name__ == "__main__":
    main()
