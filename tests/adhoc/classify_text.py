"""
CLI sanity check for the fraud classification pipeline.

Runs:
  - semantic entity extraction (via semantic_ner)
  - fraud classification (via fraud_classifier)
and prints a structured summary including confidence and explanation.

Usage:
    python scripts/classify_text.py "Hi I'm Anna from TrustWallet. Please send 50 USDT for verification."

Assumptions:
  - The Ollama LLM is available locally or at the base_url configured in env.
  - All components are using open-source/free models by default.
"""

from i4g.extraction.semantic_ner import build_llm, extract_semantic_entities
from i4g.classification.classifier import classify
import argparse
import json
import pprint


def main():
    parser = argparse.ArgumentParser(description="Run fraud classification pipeline on input text")
    parser.add_argument("text", type=str, help="Text input to analyze")
    parser.add_argument("--model", type=str, default="llama3.1", help="Model name for LLM (default: llama3.1)")
    parser.add_argument("--base_url", type=str, default=None, help="Base URL for Ollama API if not local")
    args = parser.parse_args()

    print("\n=== i4g Fraud Classification CLI ===\n")

    llm = build_llm(model=args.model, base_url=args.base_url)
    print("[Step 1] Extracting semantic entities ...")
    entities = extract_semantic_entities(args.text, llm)

    print("\nExtracted Entities:")
    pprint.pprint(entities, sort_dicts=False)

    print("\n[Step 2] Running fraud classification ...")
    result = classify(entities)

    print("\n=== Classification Result ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\nDone.\n")


if __name__ == "__main__":
    main()
