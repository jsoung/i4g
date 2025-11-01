"""Unit tests for i4g.normalization.normalizer.

These tests verify alias normalization, deduplication,
and entity merging logic for Phase M3.
"""

import pytest

from i4g.normalization.normalizer import merge_entities, normalize_entities
from i4g.normalization.reference_data import KNOWN_ASSETS, KNOWN_ORGS


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            {"organizations": ["Trust wallet", "Binance exchange"]},
            {"organizations": ["Trustwallet", "Binance"]},
        ),
        (
            {"crypto_assets": ["btc", "tether coin", "ethereum"]},
            {"crypto_assets": ["Bitcoin", "Usdt", "Ethereum"]},
        ),
    ],
)
def test_alias_normalization(raw, expected):
    """Test known alias replacement for organizations and assets."""
    result = normalize_entities(raw)
    for key in expected:
        assert result[key] == expected[key]


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            {"wallet_addresses": ["0xabc", "0xABC", "0xabc"]},
            {"wallet_addresses": ["0xabc"]},
        ),
        (
            {"people": ["Alice", "alice", "Bob"]},
            {"people": ["Alice", "Bob"]},
        ),
    ],
)
def test_deduplication(raw, expected):
    """Ensure case-insensitive deduplication works."""
    result = normalize_entities(raw)
    # Lowercase for wallet addresses only
    for key, vals in result.items():
        if key == "wallet_addresses":
            vals = [v.lower() for v in vals]
        assert vals == expected[key]


def test_merge_entities_combines_and_deduplicates():
    """Test merging multiple entity dictionaries."""
    d1 = {"organizations": ["Binance"], "crypto_assets": ["BTC"]}
    d2 = {"organizations": ["TrustWallet"], "crypto_assets": ["BTC", "USDT"]}

    merged = merge_entities(d1, d2)

    assert set(merged["organizations"]) == {"Binance", "TrustWallet"}
    assert set(merged["crypto_assets"]) == {"BTC", "USDT"}


def test_ignore_invalid_input_types():
    """Ensure non-list values are safely ignored."""
    result = normalize_entities({"organizations": "Not a list"})
    assert result == {}


def test_known_reference_dicts_are_not_empty():
    """Quick sanity check to ensure alias dictionaries are loaded."""
    assert len(KNOWN_ORGS) > 0
    assert len(KNOWN_ASSETS) > 0
