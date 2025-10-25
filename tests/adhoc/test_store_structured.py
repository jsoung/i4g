from i4g.store.structured import StructuredStore
from i4g.store.schema import ScamRecord

store = StructuredStore("data/test_i4g.db")

record = ScamRecord(
    case_id="case-123",
    text="Hi I'm Anna from TrustWallet. Send 50 USDT to 0xAbC...",
    entities={"people": ["Anna"], "wallet_addresses": ["0xAbC..."], "scam_indicators": ["verification fee"]},
    classification="crypto_investment",
    confidence=0.87,
)

store.upsert_record(record)
found = store.get_by_id("case-123")
recent = store.list_recent(10)
matches = store.search_by_field("wallet_addresses", "0xAbC")
store.delete_by_id("case-123")
store.close()
