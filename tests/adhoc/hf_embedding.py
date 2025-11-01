"""
Quick sanity check for the Hugging Face Inference API embedding endpoint.

Usage:
    export HF_API_TOKEN=hf_xxx   # create one at https://huggingface.co/settings/tokens
    python tests/adhoc/hf_embedding.py "Optional text to embed"
"""

import os
import sys
from typing import Sequence

import requests

API_URL = "https://api-inference.huggingface.co/models/BAAI/bge-small-en-v1.5"


def _read_token() -> str:
    token = os.environ.get("HF_API_TOKEN")
    if not token:
        raise SystemExit("Set HF_API_TOKEN in your environment (https://huggingface.co/settings/tokens).")
    return token


def _payload(texts: Sequence[str]) -> dict:
    if not texts:
        texts = ["This is a sample text to embed."]
    return {"inputs": list(texts)}


def main(args: Sequence[str]) -> None:
    token = _read_token()
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(API_URL, headers=headers, json=_payload(args))
    print(resp.status_code)
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        print({"error": str(exc), "details": resp.text})
        return
    print(resp.json())


if __name__ == "__main__":
    main(sys.argv[1:])
