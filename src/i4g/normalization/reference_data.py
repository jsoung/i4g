"""Reference data for normalization.

This module defines alias maps and canonical names for organizations,
cryptocurrencies, and other frequently encountered entities in fraud-related text.
All mappings here are intended for rule-based normalization (Phase M3).

These dictionaries can later be replaced or augmented by dynamic, ML-driven
entity linking models (Phase M4).
"""

# Known organization aliases mapped to their canonical forms.
KNOWN_ORGS = {
    "trust wallet": "TrustWallet",
    "binance exchange": "Binance",
    "coin base": "Coinbase",
    "binance.us": "BinanceUS",
    "okx exchange": "OKX",
    "crypto.com exchange": "Crypto.com",
    "metamask wallet": "MetaMask",
}

# Known crypto asset aliases mapped to canonical ticker names.
KNOWN_ASSETS = {
    "btc": "Bitcoin",
    "bitcoin": "Bitcoin",
    "eth": "Ethereum",
    "ether": "Ethereum",
    "usdt": "USDT",
    "tether": "USDT",
    "usdc": "USDC",
    "bnb": "BNB",
    "sol": "Solana",
}

# Country and region aliases for future enrichment (Phase M3.5+).
KNOWN_LOCATIONS = {
    "u.s.": "United States",
    "usa": "United States",
    "uk": "United Kingdom",
    "uae": "United Arab Emirates",
}
