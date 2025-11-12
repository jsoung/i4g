"""Cloud Run job entrypoint for batch report generation."""

from __future__ import annotations

import logging
import os
import sys
from typing import List

from i4g.services.factories import build_review_store
from i4g.worker.tasks import generate_report_for_case

LOGGER = logging.getLogger("i4g.worker.jobs.report")


def _configure_logging() -> None:
    level_name = os.getenv("I4G_RUNTIME__LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _resolve_review_ids(limit: int) -> List[str]:
    explicit = os.getenv("I4G_REPORT__REVIEW_IDS")
    if explicit:
        return [value.strip() for value in explicit.split(",") if value.strip()]

    target_status = os.getenv("I4G_REPORT__TARGET_STATUS", "accepted")
    store = build_review_store()
    queue = store.get_queue(status=target_status, limit=limit)
    return [item["review_id"] for item in queue]


def main() -> int:
    """Entry point executed by the Cloud Run job container."""

    _configure_logging()

    batch_limit = int(os.getenv("I4G_REPORT__BATCH_LIMIT", "25") or 25)
    dry_run = os.getenv("I4G_REPORT__DRY_RUN", "false").lower() in {"1", "true", "yes", "on"}

    LOGGER.info("Starting report job: batch_limit=%s dry_run=%s", batch_limit, dry_run)

    review_ids = _resolve_review_ids(limit=batch_limit)
    if not review_ids:
        LOGGER.info("No review IDs resolved; nothing to do")
        return 0

    LOGGER.info("Resolved %s review ID(s) for processing", len(review_ids))

    store = build_review_store()
    successes = 0
    failures = 0

    for review_id in review_ids:
        if dry_run:
            LOGGER.info("Dry run enabled; would generate report for %s", review_id)
            successes += 1
            continue
        result = generate_report_for_case(review_id, store=store)
        if result.startswith("error:"):
            failures += 1
            LOGGER.error("Report generation failed for %s: %s", review_id, result)
        else:
            successes += 1
            LOGGER.info("Report generated for %s → %s", review_id, result)

    LOGGER.info("Report batch complete: successes=%s failures=%s", successes, failures)

    return 0 if failures == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
