"""
Manual ad-hoc test for the worker task.

Run manually to simulate the background report generation process:
    poetry run python tests/adhoc/manual_task_demo.py
"""

from i4g.store.review_store import ReviewStore
from i4g.worker.tasks import generate_report_for_case


def main():
    store = ReviewStore()
    review_id = store.enqueue_case("CASE-DEMO", priority="high")
    store.update_status(review_id, status="accepted", notes="Approved for reporting")

    print(f"Queued and accepted review ID: {review_id}")
    doc_id = generate_report_for_case(review_id, store=store)
    print(f"Result: {doc_id}")


if __name__ == "__main__":
    main()
