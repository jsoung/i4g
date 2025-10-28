"""
Unit tests for ReviewStore.

These tests use an in-memory or temporary SQLite database to ensure
isolation and reproducibility. They verify queue management and
action logging behaviors.
"""

import sqlite3
from i4g.store.review_store import ReviewStore


def test_table_initialization(tmp_path):
    """Verify tables are created properly on initialization."""
    db_path = tmp_path / "test_review_store.db"
    store = ReviewStore(str(db_path))

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {t[0] for t in cur.fetchall()}

    assert {"review_queue", "review_actions"}.issubset(tables)


def test_enqueue_and_retrieve_case(tmp_path):
    """Test inserting a case and retrieving it from the queue."""
    db_path = tmp_path / "review_test.db"
    store = ReviewStore(str(db_path))

    review_id = store.enqueue_case("CASE123", priority="high")
    assert isinstance(review_id, str)

    queue = store.get_queue()
    assert len(queue) == 1
    assert queue[0]["case_id"] == "CASE123"
    assert queue[0]["priority"] == "high"

    retrieved = store.get_review(review_id)
    assert retrieved is not None
    assert retrieved["review_id"] == review_id


def test_update_status_and_notes(tmp_path):
    """Test updating review status and notes."""
    db_path = tmp_path / "update_test.db"
    store = ReviewStore(str(db_path))

    review_id = store.enqueue_case("CASE999")
    store.update_status(review_id, status="in_review", notes="Initial check")

    updated = store.get_review(review_id)
    assert updated["status"] == "in_review"
    assert "Initial check" in updated["notes"]


def test_action_logging_and_retrieval(tmp_path):
    """Test logging actions and retrieving them."""
    db_path = tmp_path / "actions_test.db"
    store = ReviewStore(str(db_path))

    review_id = store.enqueue_case("CASE_ACTION")
    action_id = store.log_action(
        review_id,
        actor="analyst_1",
        action="claimed",
        payload={"note": "Claimed for review"},
    )

    assert isinstance(action_id, str)

    actions = store.get_actions(review_id)
    assert len(actions) == 1
    assert actions[0]["actor"] == "analyst_1"
    assert "Claimed for review" in actions[0]["payload"]


def test_queue_and_actions_integration(tmp_path):
    """Ensure actions correspond to existing queue entries."""
    db_path = tmp_path / "integration_test.db"
    store = ReviewStore(str(db_path))

    review_id = store.enqueue_case("CASE_INTEGRATION")
    store.log_action(review_id, actor="analyst_2", action="accepted")

    case = store.get_review(review_id)
    actions = store.get_actions(review_id)

    assert case["case_id"] == "CASE_INTEGRATION"
    assert len(actions) == 1
    assert actions[0]["review_id"] == review_id
