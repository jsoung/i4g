from i4g.store.ingest import IngestPipeline

pipeline = IngestPipeline()

sample = {
    "text": "Hi I'm Anna from TrustWallet. Send 50 USDT to verify.",
    "fraud_type": "crypto_investment",
    "fraud_confidence": 0.91,
    "entities": {
        "people": [{"value": "Anna"}],
        "organizations": [{"value": "TrustWallet"}],
        "crypto_assets": [{"value": "USDT"}],
        "wallet_addresses": [{"value": "0xAbC..."}],
    },
}

cid = pipeline.ingest_classified_case(sample)
print("Stored case:", cid)

similar = pipeline.query_similar_cases("TrustWallet verification fee", top_k=3)
print(similar)
