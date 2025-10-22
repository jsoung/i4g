"""
Batch semantic extraction using the chat-style semantic_ner module.
"""

import json
from pathlib import Path
from tqdm import tqdm
from i4g.extraction.semantic_ner import build_llm, extract_semantic_entities

def main():
    input_path = Path("data/ocr_output.json")
    output_path = Path("data/entities_semantic.json")

    if not input_path.exists():
        print("❌ OCR output not found. Run scripts/run_ocr.py first.")
        return

    llm = build_llm(model="llama3.1")

    with open(input_path) as f:
        ocr_results = json.load(f)

    output = []
    for item in tqdm(ocr_results, desc="Semantic extraction"):
        text = item.get("text", "")
        if not text.strip():
            output.append({"file": item.get("file"), "semantic_entities": {}})
            continue

        entities = extract_semantic_entities(text, llm)
        output.append({"file": item.get("file"), "semantic_entities": entities})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Semantic extraction saved to {output_path}")

if __name__ == "__main__":
    main()
