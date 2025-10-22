"""
Batch extraction of structured entities from OCR output.
"""

import json
from pathlib import Path
from tqdm import tqdm
from i4g.extraction.ner_rules import extract_entities


def main():
    input_path = Path("data/ocr_output.json")
    output_path = Path("data/entities.json")

    if not input_path.exists():
        print("❌ OCR output not found. Run scripts/run_ocr.py first.")
        return

    with open(input_path) as f:
        ocr_results = json.load(f)

    structured = []
    for item in tqdm(ocr_results, desc="Extracting entities"):
        text = item.get("text", "")
        entities = extract_entities(text)
        structured.append({
            "file": item.get("file"),
            "entities": entities
        })

    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, "w") as f:
        json.dump(structured, f, indent=2)

    print(f"\n✅ Entity extraction complete. Saved to {output_path}")


if __name__ == "__main__":
    main()
