"""
Manual ad-hoc test script for the review_store FastAPI backend.

This script allows you to quickly verify that the local API endpoints for
case review management (M6 foundation) are functioning as expected.

Run this AFTER launching the API:
    uvicorn i4g.review.api:app --reload

Then in another terminal:
    python tests/adhoc/manual_review_demo.py
"""

import json
import requests

BASE_URL = "http://127.0.0.1:8000"

def pretty(obj):
    """Pretty-print JSON for better readability."""
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def run_demo():
    print("=== 1. Creating a new review case ===")
    payload = {
        "case_id": "CASE-2025-0001",
        "text": "Hi, this is Anna from TrustWallet. Please send 50 USDT to verify your wallet.",
        "llm_result": {
            "people": ["Anna"],
            "organizations": ["TrustWallet"],
            "crypto_assets": ["USDT"],
            "wallet_addresses": [],
            "contact_channels": [],
            "locations": [],
            "scam_indicators": ["verification fee", "send to verify"]
        },
        "classification": {
            "label": "crypto_scam",
            "confidence": 0.93
        }
    }
    r = requests.post(f"{BASE_URL}/reviews", json=payload)
    r.raise_for_status()
    pretty(r.json())

    print("\n=== 2. Listing all review cases ===")
    r = requests.get(f"{BASE_URL}/reviews")
    r.raise_for_status()
    pretty(r.json())

    print("\n=== 3. Updating review decision ===")
    update = {"decision": "accept", "notes": "Classic verification scam."}
    r = requests.patch(f"{BASE_URL}/reviews/CASE-2025-0001", json=update)
    r.raise_for_status()
    pretty(r.json())

    print("\n=== 4. Fetching a single case ===")
    r = requests.get(f"{BASE_URL}/reviews/CASE-2025-0001")
    r.raise_for_status()
    pretty(r.json())


if __name__ == "__main__":
    try:
        run_demo()
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to the API. Make sure the FastAPI server is running.")
