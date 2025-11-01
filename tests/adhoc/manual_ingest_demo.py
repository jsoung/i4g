"""
Manual smoke test for i4g ingestion and retrieval pipeline.

⚠️ This is NOT an automated unit test.
Run manually to verify end-to-end integration using real Ollama + Chroma.

Usage:
    python tests/adhoc/manual_ingest_demo.py

It will:
1. Initialize StructuredStore + VectorStore.
2. Ingest two realistic scam case samples.
3. Perform a similarity query.
4. Print formatted results.

Requirements:
- Ollama service running locally (`ollama serve`)
- Model installed: `ollama pull nomic-embed-text`
- Chroma installed via `pip install chromadb`
"""

import pprint
from pathlib import Path

from i4g.store.ingest import IngestPipeline
from i4g.store.structured import StructuredStore
from i4g.store.vector import VectorStore


def main() -> None:
    base_dir = Path("data/manual_demo")
    base_dir.mkdir(parents=True, exist_ok=True)

    structured_db = base_dir / "structured_demo.db"
    vector_dir = base_dir / "chroma"

    # Initialize pipeline components
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
