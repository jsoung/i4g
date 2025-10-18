#!/usr/bin/env python3
"""
ocr_extract_texts.py
--------------------
Run Tesseract OCR on all PNG chat screenshots in ./chat_screens/
and save recognized text to JSONL for RAGFlow ingestion.
"""

from PIL import Image
import pytesseract
from pathlib import Path
import json
import uuid
from datetime import datetime

def ocr_image_to_doc(image_path):
    text = pytesseract.image_to_string(Image.open(image_path))
    return {
        "id": str(uuid.uuid4()),
        "text": text.strip(),
        "metadata": {
            "source": "synthetic_chat",
            "filename": image_path.name,
            "created_at": datetime.utcnow().isoformat() + "Z",
        },
    }

def main():
    img_dir = Path("chat_screens")
    output = Path("outputs/ocr_output.jsonl")
    images = sorted(img_dir.glob("*.png"))
    docs = [ocr_image_to_doc(img) for img in images]

    with open(output, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"✅ OCR complete: {len(docs)} images processed → {output}")

if __name__ == "__main__":
    main()
