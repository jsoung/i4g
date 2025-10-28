"""
Background worker tasks for i4g.

This module defines asynchronous and manual worker functions that perform
post-review operations such as report generation and export.
"""

import logging
from typing import Optional

from i4g.reports.generator import ReportGenerator
from i4g.store.review_store import ReviewStore

logger = logging.getLogger(__name__)


def generate_report_for_case(
    review_id: str,
    store: Optional[ReviewStore] = None,
) -> str:
    """Generate and export a report for a specific accepted review case.

    Args:
        review_id: Unique ID of the review record.
        store: Optional ReviewStore instance; creates new if omitted.

    Returns:
        The local path of the created report, or "error:<message>" on failure.
    """
    store = store or ReviewStore()

    case = store.get_review(review_id)
    if not case:
        logger.error("No such review ID: %s", review_id)
        return "error:review_not_found"

    if case.get("status") != "accepted":
        logger.warning("Review %s is not marked accepted; skipping", review_id)
        return "error:not_accepted"

    try:
        generator = ReportGenerator()
        report_result = generator.generate_report(
            case_id=case.get("case_id")
        )

        report_path = report_result.get("report_path")
        if not report_path:
            raise Exception("Report generated but no local path returned.")

        store.log_action(review_id, actor="worker", action="report_generated", payload={"report_path": report_path})
        logger.info("Generated and exported report for %s → %s", review_id, report_path)
        return report_path
    except Exception as exc:
        logger.exception("Report generation/export failed for %s", review_id)
        store.log_action(review_id, actor="worker", action="error", payload={"error": str(exc)})
        return f"error:{exc}"