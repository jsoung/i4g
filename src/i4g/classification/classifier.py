"""Fraud classification utilities for i4g (Phase M3).

This module implements a transparent, rule-based classifier that consumes
merged & scored entities (from semantic + rule extraction) and produces:

{
  "fraud_type": str,
  "fraud_confidence": float,   # 0.0 - 1.0
  "entities": dict,            # the scored entities (unchanged)
  "explanation": str,          # human-readable rationale for the decision
  "reasons": List[str]         # short reason codes for programmatic checks
}

The heuristics are intentionally simple and explainable; they are intended
to be a starting point for ML improvements in later phases.
"""

from typing import Dict, Any, List, Tuple
import statistics
import re

# Thresholds and constants (tuneable)
BASE_CONFIDENCE_FLOOR = 0.05
AGREEMENT_BOOST = 0.10  # boost when strong indicators agree
WALLET_BOOST = 0.20
SCAM_INDICATOR_BOOST = 0.15
CAP_CONFIDENCE = 0.99

# --- Heuristic Keyword Definitions ---
HEURISTICS = {
    "romance": {
        "relationship": ["love", "dear", "miss you", "i love you", "relationship", "meet soon"],
        "money": ["send", "transfer", "pay", "wire", "bitcoin", "btc", "usdt", "wallet", "$"],
    },
    "investment": {
        "keywords": ["investment", "guarantee", "double profit", "high return", "investment club", "investment guarantee"],
    },
    "phishing": {
        "keywords": ["verify account", "suspend", "login", "password", "account suspended", "click here"],
        "url_patterns": [r"(https?://|t\.me/|wa\.me/|@[\w_]+)"],
    }
}

# Pre-compile regex for performance
HEURISTICS["phishing"]["url_regex"] = [re.compile(p) for p in HEURISTICS["phishing"]["url_patterns"]]



def _ensure_scored_format(entities: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Ensure entity values are in the scored format:
    { key: [{"value": str, "confidence": float}, ...], ... }

    Accepts legacy input where values may be simple lists of strings.
    """
    out: Dict[str, List[Dict[str, Any]]] = {}
    for k, v in entities.items():
        if isinstance(v, list) and v and isinstance(v[0], dict) and "value" in v[0]:
            out[k] = v  # already scored
        elif isinstance(v, list):
            out[k] = [{"value": str(x), "confidence": 0.7} for x in v]
        else:
            out[k] = []
    return out


def _collect_evidence(scored_entities: Dict[str, List[Dict[str, Any]]]) -> Tuple[List[str], List[str]]:
    """Collect textual evidence and short-coded reasons."""
    evidences: List[str] = []
    reasons: List[str] = []

    # Wallets
    wallets = scored_entities.get("wallet_addresses", [])
    if wallets:
        evidences.append(f"Found {len(wallets)} wallet address(es): " + ", ".join(w["value"] for w in wallets))
        reasons.append("wallet_present")

    # Crypto assets
    cryptos = scored_entities.get("crypto_assets", [])
    if cryptos:
        evidences.append("Crypto assets mentioned: " + ", ".join(c["value"] for c in cryptos))
        reasons.append("crypto_asset_mentioned")

    # Scam indicators
    indicators = scored_entities.get("scam_indicators", [])
    if indicators:
        evidences.append("Scam indicator phrases: " + ", ".join(i["value"] for i in indicators))
        reasons.append("scam_indicators_present")

    # Contact channels or URLs
    channels = scored_entities.get("contact_channels", [])
    if channels:
        evidences.append("Contact channels: " + ", ".join(c["value"] for c in channels))
        reasons.append("contact_channel_present")

    # People / orgs
    people = scored_entities.get("people", [])
    orgs = scored_entities.get("organizations", [])
    if people:
        evidences.append("Person names: " + ", ".join(p["value"] for p in people))
    if orgs:
        evidences.append("Organizations: " + ", ".join(o["value"] for o in orgs))

    return evidences, reasons


def _average_entity_confidence(scored_entities: Dict[str, List[Dict[str, Any]]]) -> float:
    """Compute the average confidence across all extracted entities.

    Returns BASE_CONFIDENCE_FLOOR if no scored entities exist.
    """
    scores: List[float] = []
    for vals in scored_entities.values():
        for item in vals:
            try:
                scores.append(float(item.get("confidence", 0.0)))
            except Exception:
                continue
    if not scores:
        return BASE_CONFIDENCE_FLOOR
    # Use geometric-friendly average (mean) for now
    return max(BASE_CONFIDENCE_FLOOR, min(1.0, statistics.mean(scores)))


def _detect_romance_pattern(scored_entities: Dict[str, List[Dict[str, Any]]], raw_text: str) -> bool:
    """Simple heuristic for romance scams: presence of relationship tokens + money request."""
    text = raw_text.lower()
    relationship_tokens = HEURISTICS["romance"]["relationship"]
    money_tokens = HEURISTICS["romance"]["money"]
    rel = any(tok in text for tok in relationship_tokens)
    money = any(tok in text for tok in money_tokens)
    return rel and money


def _detect_investment_pattern(scored_entities: Dict[str, List[Dict[str, Any]]], raw_text: str) -> bool:
    """Heuristic for investment/crypto scams: investment keywords + presence of wallet/crypto."""
    text = raw_text.lower()
    invest_tokens = HEURISTICS["investment"]["keywords"]
    has_invest = any(tok in text for tok in invest_tokens)
    has_wallet = len(scored_entities.get("wallet_addresses", [])) > 0
    has_crypto = len(scored_entities.get("crypto_assets", [])) > 0
    return has_invest or (has_wallet and has_crypto)


def _detect_phishing_pattern(scored_entities: Dict[str, List[Dict[str, Any]]], raw_text: str) -> bool:
    """Heuristic for phishing: suspicious URLs / impersonation keywords."""
    text = raw_text.lower()
    phishing_tokens = HEURISTICS["phishing"]["keywords"]
    has_phish_tok = any(tok in text for tok in phishing_tokens)
    # existence of contact channels that look like short URLs or t.me/ etc.
    channels = [c["value"] for c in scored_entities.get("contact_channels", [])]
    has_sus_url = any(any(regex.search(c) for regex in HEURISTICS["phishing"]["url_regex"]) for c in channels)
    return has_phish_tok or has_sus_url


def _decide_fraud_type(scored_entities: Dict[str, List[Dict[str, Any]]], raw_text: str) -> Tuple[str, List[str]]:
    """Return a best-guess fraud type and list of triggered reason codes."""
    reasons: List[str] = []
    # Order matters: romance > investment/crypto > phishing > unknown
    if _detect_romance_pattern(scored_entities, raw_text):
        reasons.append("romance_pattern")
        return "romance_scam", reasons

    if _detect_investment_pattern(scored_entities, raw_text):
        reasons.append("investment_pattern")
        return "crypto_investment", reasons

    if _detect_phishing_pattern(scored_entities, raw_text):
        reasons.append("phishing")
        return "phishing", reasons

    # fallback: if wallet present but no other signals, label as potential_crypto
    if scored_entities.get("wallet_addresses"):
        reasons.append("wallet_only")
        return "potential_crypto", reasons

    return "unknown", reasons


def _calibrate_confidence(base: float, scored_entities: Dict[str, List[Dict[str, Any]]], reasons: List[str]) -> float:
    """Calibrate a base confidence using heuristics.

    base: initial base confidence (average entity confidence)
    """
    conf = base

    # Boost if both wallet and crypto appear
    if scored_entities.get("wallet_addresses") and scored_entities.get("crypto_assets"):
        conf += WALLET_BOOST

    # Boost if scam indicator phrases exist
    if scored_entities.get("scam_indicators"):
        conf += SCAM_INDICATOR_BOOST

    # Additional boost if specific high-confidence reasons present
    if "romance_pattern" in reasons or "investment_pattern" in reasons:
        conf += AGREEMENT_BOOST

    # Cap confidence to a sane value
    conf = min(conf, CAP_CONFIDENCE)

    # Normalize to [0,1]
    conf = max(0.0, min(1.0, conf))
    return conf


def classify(entities: Dict[str, Any], raw_text: str = "") -> Dict[str, Any]:
    """Classify a single case (text + extracted entities) and return a structured result.

    Args:
        entities: Merged & scored entities, typically from semantic extraction.
            Expected format: { "people": [{"value":..., "confidence":...}], ... }
        raw_text: Original text used for pattern-based heuristics (optional).

    Returns:
        Dictionary with keys:
            - fraud_type (str)
            - fraud_confidence (float)
            - entities (dict) (scored entities normalized to standard format)
            - explanation (str)
            - reasons (List[str])
    """
    scored = _ensure_scored_format(entities)
    evidences, evidence_reasons = _collect_evidence(scored)
    base_conf = _average_entity_confidence(scored)

    fraud_type, decision_reasons = _decide_fraud_type(scored, raw_text or "")
    reasons = sorted(set(evidence_reasons + decision_reasons))

    fraud_confidence = _calibrate_confidence(base_conf, scored, decision_reasons)

    # Build explanation text
    explanation_lines: List[str] = []
    explanation_lines.append(f"Base entity confidence: {base_conf:.2f}")
    if evidences:
        explanation_lines.append("Key evidence:")
        for e in evidences:
            explanation_lines.append(f"  - {e}")
    else:
        explanation_lines.append("No entity evidence found.")

    explanation_lines.append(f"Decision: {fraud_type} (reasons: {', '.join(reasons)})")
    explanation = "\n".join(explanation_lines)

    return {
        "fraud_type": fraud_type,
        "fraud_confidence": round(float(fraud_confidence), 3),
        "entities": scored,
        "explanation": explanation,
        "reasons": reasons,
    }
