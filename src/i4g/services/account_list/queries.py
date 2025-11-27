"""Indicator query catalog and helper accessors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable


@dataclass(frozen=True)
class IndicatorQuery:
    """Definition for a financial indicator prompt/query pair."""

    slug: str
    display_name: str
    indicator_type: str
    query: str
    system_message: str
    enabled: bool = True
    max_documents: int = 50


_BANK_MESSAGE = """
You are an AI assistant designed to extract bank account information from a set of documents.
Identify explicit mentions of banks, account types (checking, savings, routing, other), and the
associated numbers exactly as they appear (include masked characters). Output a JSON list of
objects with the keys "item" (bank name), "type" (account type), and "number" (captured number).
Return an empty list if nothing is found and never add explanations outside the JSON list.
""".strip()

_CRYPTO_MESSAGE = """
You are an AI assistant designed to extract cryptocurrency wallet information from chat logs and
intake forms. Detect coin type when stated or infer from wallet shape. Output a JSON list where
each object includes "item" (coin or token name), "type" = "cryptocurrency", and "number"
(wallet address). Return an empty list when no addresses are present. Never fabricate data.
""".strip()

_PAYMENTS_MESSAGE = """
You are an AI assistant designed to extract payment processor accounts and card numbers.
Capture payment services (PayPal, Venmo, Cash App, etc.) or card issuers (Visa, Mastercard, Amex).
Output a JSON list with "item" (service or issuer), "type" (payment_service, credit, debit,
prepaid, or other), and "number" (identifier, handle, or masked card number). Include only
explicitly provided values.
""".strip()

_DEFAULT_QUERIES: Dict[str, IndicatorQuery] = {
    "bank": IndicatorQuery(
        slug="bank",
        display_name="Bank Accounts",
        indicator_type="bank_account",
        query="bank account routing checking savings transfer wire statement",
        system_message=_BANK_MESSAGE,
    ),
    "crypto": IndicatorQuery(
        slug="crypto",
        display_name="Cryptocurrency",
        indicator_type="crypto_wallet",
        query="crypto bitcoin btc ethereum eth wallet address blockchain hash",
        system_message=_CRYPTO_MESSAGE,
    ),
    "payments": IndicatorQuery(
        slug="payments",
        display_name="Payment Handles",
        indicator_type="payment_handle",
        query="payment paypal venmo cash app zelle stripe square card number",
        system_message=_PAYMENTS_MESSAGE,
    ),
}


def list_indicator_queries() -> Iterable[IndicatorQuery]:
    """Return all enabled indicator queries."""

    return [query for query in _DEFAULT_QUERIES.values() if query.enabled]


def get_indicator_query(slug: str) -> IndicatorQuery:
    """Fetch a query definition by slug.

    Args:
        slug: Category key requested by callers.

    Returns:
        IndicatorQuery matching the slug.

    Raises:
        KeyError: If the slug is not registered as an indicator query.
    """

    key = slug.lower().strip()
    if key not in _DEFAULT_QUERIES:
        raise KeyError(f"Unknown indicator category: {slug}")
    return _DEFAULT_QUERIES[key]
