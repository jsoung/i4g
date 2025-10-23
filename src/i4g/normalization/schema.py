"""Canonical schema definitions for normalized entities.

Defines dataclasses for the normalized representation of extracted entities.
Used by downstream indexing and retrieval systems.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class NormalizedRecord:
    """Unified normalized entity structure.

    Attributes:
        people: List of person names involved in the case.
        organizations: Canonical organization names (e.g., "Binance").
        crypto_assets: Canonical crypto asset symbols or names.
        wallet_addresses: Wallet addresses, lowercased, deduplicated.
        contact_channels: Messaging or communication handles.
        locations: Standardized location names.
        scam_indicators: Terms or patterns associated with fraud activity.
        source_text: Optional original text for reference or debugging.
    """

    people: List[str]
    organizations: List[str]
    crypto_assets: List[str]
    wallet_addresses: List[str]
    contact_channels: List[str]
    locations: List[str]
    scam_indicators: List[str]
    source_text: Optional[str] = None
