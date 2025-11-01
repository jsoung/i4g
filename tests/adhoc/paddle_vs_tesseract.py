#!/usr/bin/env python3
"""
paddle_vs_tesseract.py
----------------------
Compares the OCR output and performance of Tesseract and PaddleOCR
for a given image file.

Usage:
    python tests/adhoc/paddle_vs_tesseract.py --image data/chat_screens/chat_0001.png
"""

import argparse
import logging
import time
from pathlib import Path

import pytesseract
from paddleocr import PaddleOCR
from PIL import Image

# Suppress verbose logging from PaddleOCR
logging.getLogger("paddleocr").setLevel(logging.ERROR)


def main(image_path: Path):
    """Runs both Tesseract and PaddleOCR on the image and prints the results."""
    if not image_path.is_file():
        print(f"❌ Error: Image file not found at {image_path}")
        return

    print(f"Processing image: {image_path}\n")

    # --- Tesseract ---
    start_time = time.monotonic()
    t_text = pytesseract.image_to_string(Image.open(image_path))
    t_duration = time.monotonic() - start_time

    # --- PaddleOCR ---
    start_time = time.monotonic()
    pocr = PaddleOCR(use_angle_cls=True, lang="en")
    paddle_result = pocr.predict(str(image_path))
    p_text = "\n".join(paddle_result[0]["rec_texts"]) if paddle_result and paddle_result[0] else ""
    p_duration = time.monotonic() - start_time

    print(f"=== TESSERACT ({t_duration:.2f}s) ===")
    print(t_text)
    print(f"\n=== PADDLEOCR ({p_duration:.2f}s) ===")
    print(p_text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare Tesseract and PaddleOCR on an image.")
    parser.add_argument("--image", type=Path, required=True, help="Path to the image file.")
    args = parser.parse_args()
    main(args.image)
