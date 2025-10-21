"""
OCR module using Tesseract for text extraction from screenshots or PDFs.
"""

import pytesseract
from PIL import Image, ImageOps
from pathlib import Path
from typing import Dict, List
from tqdm import tqdm


def extract_text(image_path: str) -> str:
    """
    Perform OCR on a given image using Tesseract.
    Args:
        image_path (str): Path to the image file.
    Returns:
        str: Extracted text.
    """
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)  # auto-rotate if needed
    img = img.convert("L")              # grayscale
    return pytesseract.image_to_string(img, lang="eng")


def batch_extract_text(image_dir: str) -> List[Dict[str, str]]:
    """
    OCR for all images in a directory.
    Args:
        image_dir (str): Directory containing images.
    Returns:
        List[Dict[str, str]]: List of {filename, text}.
    """
    results = []
    img_paths = list(Path(image_dir).glob("*.*"))
    for img_path in tqdm(img_paths, desc="Running OCR"):
        text = extract_text(str(img_path))
        results.append({"file": img_path.name, "text": text})
    return results
