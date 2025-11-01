#!/usr/bin/env python3
"""
synthesize_review_cases.py
--------------------------
Populate the local ReviewStore with synthetic queue entries so the analyst
dashboard has data to display.

Usage:
    python tests/adhoc/synthesize_review_cases.py \
        --queued 5 --in-review 2 --accepted 1 --rejected 1 --reset
"""

from __future__ import annotations

import argparse
import random
from typing import Dict, Iterable, List, Tuple
from uuid import uuid4

from i4g.store.review_store import ReviewStore

CASE_TEMPLATES: List[Dict[str, str]] = [
    {
        "code": "CRYPTO",
        "priority": "high",
        "summary": "TrustWallet verification request flagged by classifier.",
    },
    {
        "code": "ROMANCE",
        "priority": "medium",
        "summary": "Romance scam escalation asking the victim for travel funds.",
    },
    {
        "code": "INVEST",
        "priority": "high",
        "summary": "Telegram pump-and-dump group directing victims to unknown token.",
    },
    {
        "code": "SUPPORT",
        "priority": "low",
        "summary": "Customer-support impersonation featuring fake Coinbase help desk.",
    },
]

STATUS_NOTES: Dict[str, List[str]] = {
    "queued": [
        "Auto-triage pending analyst assignment.",
        "Classifier confidence above threshold; needs verification.",
    ],
    "in_review": [
        "Analyst assigned; reviewing blockchain transfers.",
        "Review in progress; awaiting victim callback.",
    ],
    "accepted": [
        "Validated as active scam. Prepare evidence package.",
        "Confirmed scam; escalate to coordination team.",
    ],
    "rejected": [
        "Duplicate of existing case. Closing out.",
        "False positive triggered by mislabeled keywords.",
    ],
}


def _reset_store(store: ReviewStore) -> None:
    with store._connect() as conn:
        conn.execute("DELETE FROM review_actions")
        conn.execute("DELETE FROM review_queue")
        conn.commit()


def _status_plan(args: argparse.Namespace) -> List[str]:
    plan: List[str] = []
    for status, count in [
        ("queued", args.queued),
        ("in_review", args.in_review),
        ("accepted", args.accepted),
        ("rejected", args.rejected),
    ]:
        plan.extend([status] * max(count, 0))
    random.shuffle(plan)
    return plan


def _seed_case(store: ReviewStore, target_status: str) -> Tuple[str, str]:
    template = random.choice(CASE_TEMPLATES)
    case_id = f"{template['code']}-{uuid4().hex[:8].upper()}"
    review_id = store.enqueue_case(case_id=case_id, priority=template["priority"])

    summary = template["summary"]
    note_suffix = random.choice(STATUS_NOTES[target_status])
    note = f"{summary} {note_suffix}"

    store.update_status(review_id, status=target_status, notes=note)
    store.log_action(
        review_id=review_id,
        actor="synthetic_seed",
        action="status_set",
        payload={"status": target_status, "summary": summary},
    )
    return review_id, case_id


def synthesize_cases(store: ReviewStore, plan: Iterable[str]) -> None:
    created = []
    for status in plan:
        review_id, case_id = _seed_case(store, status)
        created.append((review_id, status, case_id))

    if not created:
        print("No cases requested; nothing to do.")
        return

    print(f"✅ Seeded {len(created)} review case(s):")
    for review_id, status, case_id in created:
        print(f"   • {review_id} ({status}) – {case_id}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed the ReviewStore with synthetic review cases.")
    parser.add_argument("--queued", type=int, default=5, help="Number of cases left in queued state.")
    parser.add_argument("--in-review", type=int, default=2, help="Number of cases marked in_review.")
    parser.add_argument("--accepted", type=int, default=1, help="Number of accepted cases.")
    parser.add_argument("--rejected", type=int, default=1, help="Number of rejected cases.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing review queue entries before seeding new data.",
    )
    parser.add_argument(
        "--db-path",
        default="data/i4g_store.db",
        help="Optional path to the ReviewStore SQLite DB (defaults to data/i4g_store.db).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    store = ReviewStore(db_path=args.db_path)

    if args.reset:
        _reset_store(store)
        print("🧹 Cleared existing review queue records.")

    plan = _status_plan(args)
    synthesize_cases(store, plan)


if __name__ == "__main__":
    main()
