"""
CLI script to OCR a folder of images using Tesseract.
"""

import argparse
import json
from pathlib import Path

from i4g.ocr.tesseract import batch_extract_text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run OCR on screenshots.")
    parser.add_argument("--input", required=True, help="Path to folder of images")
    parser.add_argument("--output", default="data/ocr_output.json", help="Output JSON path")
    args = parser.parse_args()

    Path("data").mkdir(exist_ok=True)
    results = batch_extract_text(args.input)

    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ OCR complete. Results saved to {args.output}")
