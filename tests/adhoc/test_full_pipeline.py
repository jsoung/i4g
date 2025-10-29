"""
Manual end-to-end pipeline test.

Usage:
    $ uvicorn i4g.api.app:app --reload
    $ pytest -s tests/adhoc/test_full_pipeline.py
or run directly:
    $ python tests/adhoc/test_full_pipeline.py
"""

import time
import requests
from i4g.extraction.semantic_ner import build_llm, extract_semantic_entities
from i4g.classification.classifier import classify
from i4g.store.review_store import ReviewStore

API_URL = "http://localhost:8000"

def main():
    print("=== STEP 1: OCR extraction ===")
    text = "Hi Anna from TrustWallet, please send 0xAbC... to verify your account."
    print("Extracted text:", text)

    print("\n=== STEP 2: Semantic NER ===")
    llm = build_llm()
    entities = extract_semantic_entities(text, llm)
    print("Entities:", entities)

    print("\n=== STEP 3: Fraud classification ===")
    classification = classify(entities, raw_text=text)
    print("Classification:", classification)

    print("\n=== STEP 4: Queue for review ===")
    store = ReviewStore("/tmp/review_full_pipeline.db")
    review_id = store.enqueue_case(case_id="CASE_DEMO", priority="high")
    print(f"Queued case {review_id}")

    print("\n=== STEP 5: Trigger report generation ===")
    r = requests.post(f"{API_URL}/reports/generate")
    print("API response:", r.json())

    print("\n=== STEP 6: Poll task status ===")
    task_id = r.json().get("task_id", "demo_task_1")
    for _ in range(10):
        time.sleep(1)
        status = requests.get(f"{API_URL}/tasks/{task_id}").json()
        print("Task status:", status)
        if status.get("status") in {"done", "failed"}:
            break

    print("\n=== STEP 7: Verify review record ===")
    case = store.get_review(review_id)
    print("Stored review:", case)

if __name__ == "__main__":
    main()
