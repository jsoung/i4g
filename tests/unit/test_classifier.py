"""Unit tests for the fraud classifier."""

import pytest

from i4g.classification.classifier import classify


def _scored_list(vals):
    """Helper: convert simple list to scored-list format with default confidence."""
    return [{"value": v, "confidence": 0.8} for v in vals]


def test_classify_crypto_investment():
    """Detect crypto investment pattern when wallet+crypto+investment phrase present."""
    entities = {
        "wallet_addresses": _scored_list(["1FfmbHfnpaZjKFvyi1okTjJJusN455paPH"]),
        "crypto_assets": _scored_list(["Bitcoin"]),
        "scam_indicators": _scored_list(["investment guarantee"]),
    }
    raw = "Join our investment club for double profit. Send Bitcoin to 1FfmbHfnpaZjKFvyi1okTjJJusN455paPH."
    out = classify(entities, raw)

    assert out["fraud_type"] == "crypto_investment"
    assert out["fraud_confidence"] > 0.5
    assert "wallet_present" in out["reasons"] or "scam_indicators_present" in out["reasons"]


def test_classify_romance_scam():
    """Detect romance scam when relationship + money request tokens present."""
    entities = {
        "people": _scored_list(["John"]),
        "scam_indicators": _scored_list(["romance scam"]),
    }
    raw = "Dear John, I love you. Please send $200 in Bitcoin to meet soon."
    out = classify(entities, raw)

    assert out["fraud_type"] == "romance_scam"
    assert out["fraud_confidence"] > 0.4
    assert "romance_pattern" in out["reasons"]


def test_classify_phishing():
    """Detect phishing-like texts when suspicious URLs or phishing tokens present."""
    entities = {
        "contact_channels": _scored_list(["https://example.com/verify"]),
    }
    raw = "Your account is suspended. Click https://example.com/verify to restore access."
    out = classify(entities, raw)

    assert out["fraud_type"] == "phishing"
    assert out["fraud_confidence"] > 0.3
    assert "phishing" in out["reasons"]


def test_unknown_case_low_confidence():
    """If no clear signals, classifier returns unknown with low confidence."""
    entities = {}
    raw = "Hello, how are you today?"
    out = classify(entities, raw)

    assert out["fraud_type"] == "unknown"
    assert out["fraud_confidence"] < 0.2
