"""Entity normalization module for i4g.

Performs lightweight, rule-based normalization and canonicalization
of extracted semantic entities (Phase M3).

Future phases may replace or extend this logic with ML-based alias resolution
and probabilistic entity linking.
"""

from typing import Dict, List

from i4g.normalization.reference_data import KNOWN_ASSETS, KNOWN_LOCATIONS, KNOWN_ORGS


def normalize_entities(entities: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Normalize and canonicalize extracted entities.

    Cleans, deduplicates, and maps extracted entities to canonical forms
    using rule-based heuristics and alias dictionaries.

    Args:
        entities: Dictionary of raw entity lists from semantic extraction.
            Example:
                {
                    "organizations": ["Binance exchange", "Trust wallet"],
                    "crypto_assets": ["btc", "tether coin"],
                }

    Returns:
        Dictionary of normalized, deduplicated entity values.
    """
    normalized = {}

    for key, vals in entities.items():
        if not isinstance(vals, list):
            continue  # Defensive: skip invalid inputs

        cleaned = []

        for v in vals:
            if not v or not isinstance(v, str):
                continue

            # Normalize text
            v_clean = v.strip().lower()
            v_clean = v_clean.replace(" token", "").replace(" coin", "")
            v_clean = v_clean.replace("wallet app", "wallet").replace(" exchange", "")

            # Apply alias mappings
            if key == "organizations" and v_clean in KNOWN_ORGS:
                v_clean = KNOWN_ORGS[v_clean]
            elif key == "crypto_assets" and v_clean in KNOWN_ASSETS:
                v_clean = KNOWN_ASSETS[v_clean]
            elif key == "locations" and v_clean in KNOWN_LOCATIONS:
                v_clean = KNOWN_LOCATIONS[v_clean]

            # Title-case for readability except for wallet addresses
            if key != "wallet_addresses":
                v_clean = v_clean.title()

            cleaned.append(v_clean)

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for item in cleaned:
            if item not in seen:
                seen.add(item)
                deduped.append(item)

        normalized[key] = deduped

    return normalized


def merge_entities(*entity_dicts: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Merge multiple entity dictionaries into one normalized structure.

    Args:
        *entity_dicts: One or more entity dictionaries.

    Returns:
        Merged dictionary with combined and deduplicated lists.
    """
    merged: Dict[str, List[str]] = {}

    for d in entity_dicts:
        for key, vals in d.items():
            merged.setdefault(key, []).extend(vals)

    for key, vals in merged.items():
        merged[key] = sorted(set(vals))

    return merged
