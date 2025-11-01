"""
Preprocessing and text chunking utilities.
"""

import re
from typing import Dict, List


def clean_text(text: str) -> str:
    """Remove newlines, emojis, and extra whitespace."""
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"[^\x00-\x7F]+", "", text)  # remove emojis/non-ASCII
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
    """Split text into chunks for embedding."""
    words = text.split()
    return [" ".join(words[i : i + chunk_size]) for i in range(0, len(words), chunk_size)]


def prepare_documents(ocr_results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Clean and chunk multiple OCR results into small docs."""
    docs = []
    for item in ocr_results:
        cleaned = clean_text(item["text"])
        if not cleaned:
            continue
        for chunk in chunk_text(cleaned):
            docs.append({"source": item["file"], "content": chunk})
    return docs
