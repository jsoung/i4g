"""Audit logging helpers for account list runs."""

from __future__ import annotations

import logging
from typing import List

from i4g.services.factories import build_review_store
from i4g.store.review_store import ReviewStore

from .models import AccountListResult

LOGGER = logging.getLogger(__name__)
_AUDIT_ACTION = "account_list_run"


def _indicator_categories(result: AccountListResult) -> List[str]:
    return sorted({indicator.category for indicator in result.indicators})


def log_account_list_run(
    *,
    actor: str,
    source: str,
    result: AccountListResult,
    store: ReviewStore | None = None,
) -> None:
    """Persist an audit entry describing an account list extraction run."""

    target_store = store or build_review_store()
    try:
        target_store.ensure_placeholder_review(
            result.request_id,
            case_id=f"account-list:{result.request_id}",
        )
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception(
            "Unable to prepare account list audit placeholder for %s",
            result.request_id,
        )
        return

    payload = {
        "source": source,
        "actor": actor,
        "indicator_count": len(result.indicators),
        "source_count": len(result.sources),
        "artifacts": result.artifacts,
        "warnings": result.warnings,
        "generated_at": result.generated_at.isoformat(),
        "categories": _indicator_categories(result),
        "metadata": result.metadata,
    }

    try:
        target_store.log_action(
            result.request_id,
            actor=actor,
            action=_AUDIT_ACTION,
            payload=payload,
        )
    except Exception:  # pragma: no cover - defensive logging
        LOGGER.exception("Failed to record account list audit entry for %s", result.request_id)
