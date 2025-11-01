"""
Rule-based Named Entity Extraction for scam-related content.

This uses simple regex and keyword heuristics to identify
useful entities (wallet addresses, URLs, crypto terms, etc.).
"""

import re
from typing import Dict, List


def extract_wallets(text: str) -> List[str]:
    """Find crypto wallet addresses (Ethereum, BTC, etc.)."""
    patterns = [
        r"0x[a-fA-F0-9]{40}",  # Ethereum
        r"bc1[a-zA-HJ-NP-Z0-9]{25,39}",  # Bitcoin bech32
        r"[13][a-km-zA-HJ-NP-Z1-9]{25,34}",  # Bitcoin legacy
    ]
    wallets = []
    for pat in patterns:
        wallets.extend(re.findall(pat, text))
    return list(set(wallets))


def extract_urls(text: str) -> List[str]:
    """Find URLs or Telegram/WhatsApp links."""
    urls = re.findall(r"(https?://[^\s]+)", text)
    tgram = re.findall(r"t\.me/[A-Za-z0-9_]+", text)
    wa = re.findall(r"wa\.me/\d+", text)
    return list(set(urls + tgram + wa))


def extract_phone_numbers(text: str) -> List[str]:
    """Find phone numbers."""
    phone_pattern = re.compile(r"(\+?\d{1,2}[-.\s]??\(?\d{2,4}\)?[-.\s]??\d{3,4}[-.\s]??\d{3,4})")
    return list(set(phone_pattern.findall(text)))


def extract_names(text: str) -> List[str]:
    """
    Very lightweight name extraction — not full NLP.
    Looks for capitalized 2-word sequences (e.g. John Doe).
    """
    return re.findall(r"\b[A-Z][a-z]+\s[A-Z][a-z]+\b", text)


def extract_crypto_keywords(text: str) -> List[str]:
    """Detect crypto-related terms."""
    keywords = [
        "bitcoin",
        "btc",
        "eth",
        "ethereum",
        "usdt",
        "bnb",
        "wallet",
        "metamask",
    ]
    found = [kw for kw in keywords if kw.lower() in text.lower()]
    return list(set(found))


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Aggregate all extraction results into a single dictionary.
    """
    return {
        "wallet_addresses": extract_wallets(text),
        "urls": extract_urls(text),
        "phone_numbers": extract_phone_numbers(text),
        "names": extract_names(text),
        "crypto_keywords": extract_crypto_keywords(text),
    }
