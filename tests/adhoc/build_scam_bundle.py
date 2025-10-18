#!/usr/bin/env python3
"""
build_scam_bundle.py

Downloads / loads several public scam/spam datasets, masks PII, chunks
and normalizes into a JSONL bundle that can be ingested by RAGFlow/DeepDoc.

Usage:
  python3 tests/adhoc/build_scam_bundle.py --outdir data/bundles --chunk_chars 800

Dependencies:
  pip install datasets requests tqdm regex
"""

import argparse
import json
import os
import re
from pathlib import Path

from tqdm import tqdm

# Try to import Hugging Face datasets (used for SMS and phishing mirrors)
try:
    from datasets import load_dataset
except Exception as e:
    raise SystemExit("Please install `datasets` (pip install datasets) before running this script.") from e

import requests

# ---------------------------
# Configurable dataset sources
# ---------------------------
UCI_SMS_HF = "ucirvine/sms_spam"  # Hugging Face mirror of UCI SMS
PHISHING_HF = "ealvaradob/phishing-dataset"  # example HF phishing mirror
ZENODO_SCAM_URL = "https://zenodo.org/records/15212527/files/scam_conversations.jsonl"  # try direct file; if different, script will save landing page

# ---------------------------
# Simple PII regexes (tunable)
# ---------------------------
PII_PATTERNS = {
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}"),
    "PHONE": re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}"),
    "URL": re.compile(r"https?://[^\s]+|www\.[^\s]+"),
    # crude credit card-ish (13-19 digits in groups)
    "CARD": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    # SSN-ish (US): 3-2-4
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}


def mask_pii(text):
    if not text:
        return text
    s = text
    for token, pat in PII_PATTERNS.items():
        s = pat.sub(f"<REDACTED_{token}>", s)
    return s


# ---------------------------
# Chunking helper
# ---------------------------
def chunk_text(ret_text, max_chars=800):
    """
    Break text into chunks of at most max_chars, trying to split on sentence endings.
    Returns list of chunks.
    """
    if not ret_text:
        return []
    # crude sentence split: split on .!? or newline
    sentences = re.split(r"(?<=[\.\!\?\n])\s+", ret_text.strip())
    chunks = []
    cur = ""
    for sent in sentences:
        if not sent:
            continue
        if len(cur) + len(sent) + 1 <= max_chars:
            cur = (cur + " " + sent).strip()
        else:
            if cur:
                chunks.append(cur)
            if len(sent) <= max_chars:
                cur = sent.strip()
            else:
                # hard-split long sentence
                for i in range(0, len(sent), max_chars):
                    chunks.append(sent[i : i + max_chars])
                cur = ""
    if cur:
        chunks.append(cur)
    return chunks


# ---------------------------
# Normalizers for each dataset
# ---------------------------
def process_ucirvine_sms(dataset, out_docs, chunk_chars):
    for i, item in enumerate(dataset):
        # dataset fields vary; HF mirror tends to have 'label' and 'text' or 'sms'
        text = item.get("text") or item.get("sms") or item.get("message") or ""
        label = item.get("label") or item.get("class") or None
        source_id = f"ucisms-{i}"
        text = mask_pii(text)
        chunks = chunk_text(text, max_chars=chunk_chars)
        for j, c in enumerate(chunks or [text]):
            doc = {
                "id": f"{source_id}-{j}",
                "source": "ucirvine_sms",
                "text": c,
                "date": None,
                "platform": "sms",
                "scam_type": (
                    "spam" if label and str(label).lower().startswith("spam") else "ham" if label else "unknown"
                ),
                "metadata": {"orig_index": i},
            }
            out_docs.append(doc)


def process_phishing_hf(dataset, out_docs, chunk_chars):
    for i, item in enumerate(dataset):
        # different mirrors use different fields; guess common ones:
        body = item.get("body") or item.get("email_body") or item.get("text") or item.get("content") or ""
        subject = item.get("subject") or item.get("title") or ""
        label = item.get("label") or item.get("class") or item.get("is_phish") or item.get("label_text")
        source_id = f"phish-{i}"
        combined = (subject + "\n\n" + body).strip()
        combined = mask_pii(combined)
        chunks = chunk_text(combined, max_chars=chunk_chars)
        for j, c in enumerate(chunks or [combined]):
            doc = {
                "id": f"{source_id}-{j}",
                "source": "phishing_hf",
                "text": c,
                "date": item.get("date") or None,
                "platform": "email",
                "scam_type": (
                    "phishing" if label and str(label).lower() in ("phish", "phishing", "1", "spam") else "unknown"
                ),
                "metadata": {"orig_index": i},
            }
            out_docs.append(doc)


def process_zenodo_scc(local_path, out_docs, chunk_chars):
    """
    The Zenodo Scam Conversation Corpus may be a line-delimited JSON or a zip of JSON files.
    This function reads a local JSONL if present.
    """
    if not os.path.exists(local_path):
        print(f"[warn] Zenodo file not found at {local_path}")
        return
    with open(local_path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            try:
                rec = json.loads(line.strip())
            except Exception:
                continue
            # expected SCC JSON structure (convo-level or message-level)
            convo_id = rec.get("id") or f"zenodo-{i}"
            # Many scam corpora have a list of messages
            messages = rec.get("messages") or rec.get("conversation") or []
            if not messages and isinstance(rec.get("text"), str):
                messages = [{"text": rec.get("text"), "role": "unknown"}]
            # Convert into message-level docs
            text_join = "\n".join([mask_pii(m.get("text", "")) for m in messages if m.get("text")])
            chunks = chunk_text(text_join, max_chars=chunk_chars)
            for j, c in enumerate(chunks or [text_join]):
                doc = {
                    "id": f"{convo_id}-{j}",
                    "source": "zenodo_scc",
                    "text": c,
                    "date": rec.get("date") or None,
                    "platform": rec.get("platform") or "chat",
                    "scam_type": rec.get("scam_type") or "scam",
                    "metadata": {"orig": rec.get("meta") or {}},
                }
                out_docs.append(doc)


# ---------------------------
# Main orchestration
# ---------------------------
def main(outdir="outputs", chunk_chars=800, force_zenodo_download=False):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    docs = []

    print("[1/4] Loading UCI SMS (Hugging Face mirror)...")
    try:
        sms_ds = load_dataset(UCI_SMS_HF, split="train")
        process_ucirvine_sms(sms_ds, docs, chunk_chars)
        print(f"  -> added {len(docs)} SMS-based docs so far")
    except Exception as e:
        print("  [error] failed to load UCI SMS via datasets:", e)

    print("[2/4] Loading Phishing dataset (Hugging Face mirror)...")
    try:
        phish_ds = load_dataset(PHISHING_HF, split="train")
        before = len(docs)
        process_phishing_hf(phish_ds, docs, chunk_chars)
        print(f"  -> added {len(docs)-before} phishing docs")
    except Exception as e:
        print("  [warn] failed to load phishing HF dataset via datasets:", e)

    # Attempt to download zenodo scam corpus (if direct file exists)
    local_zenodo_path = outdir / "zenodo_scam.jsonl"
    # if force_zenodo_download or not local_zenodo_path.exists():
    if False:
        print("[3/4] Downloading Zenodo Scam Conversation Corpus from Zenodo landing URL...")
        try:
            r = requests.get(ZENODO_SCAM_URL, stream=True, timeout=30)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                with open(local_zenodo_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 14):
                        fh.write(chunk)
                print("  -> downloaded zenodo file to", local_zenodo_path)
            else:
                # Save landing page (some Zenodo datasets require manual download due to redirects)
                landing = requests.get("https://zenodo.org/records/15212527", timeout=30)
                with open(local_zenodo_path, "w", encoding="utf-8") as fh:
                    fh.write(landing.text)
                print("  -> Zenodo landing page saved; please download the dataset manually if JSONL not present.")
        except Exception as e:
            print("  [warn] zenodo download attempt failed:", e)

    # Process local zenodo file if it's JSONL
    process_zenodo_scc(str(local_zenodo_path), docs, chunk_chars)

    # Write per-dataset outputs (simple split by 'source')
    out_by_source = {}
    for d in docs:
        out_by_source.setdefault(d["source"], []).append(d)

    for src, items in out_by_source.items():
        fname = outdir / f"{src}.jsonl"
        with open(fname, "w", encoding="utf-8") as fh:
            for it in items:
                fh.write(json.dumps(it, ensure_ascii=False) + "\n")
        print(f"  wrote {len(items)} docs to {fname}")

    # Write combined bundle
    bundle_path = outdir / "bundle_all.jsonl"
    with open(bundle_path, "w", encoding="utf-8") as fh:
        for it in docs:
            fh.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"[done] wrote combined bundle to {bundle_path} ({len(docs)} total docs)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="outputs", help="output directory")
    parser.add_argument("--chunk_chars", type=int, default=800, help="max chars per chunk")
    parser.add_argument("--force-zenodo-download", action="store_true", help="force download zenodo file")
    args = parser.parse_args()
    main(outdir=args.outdir, chunk_chars=args.chunk_chars, force_zenodo_download=args.force_zenodo_download)
