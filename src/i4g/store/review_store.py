"""
ReviewStore: Manages the analyst review queue and action logs.

This module provides a lightweight, class-based interface over SQLite for
tracking cases that require analyst review. It is designed to integrate
with the StructuredStore for consistency and to support a future migration
to SQLAlchemy ORM.

Key features:
- Review queue management (enqueue, update status, list)
- Action logging (audit trail)
- Designed for analyst workflow integration (M6)

"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class ReviewStore:
    """Lightweight SQLite-based review queue and audit logger."""

    def __init__(self, db_path: str = "i4g_store.db") -> None:
        """
        Initialize the ReviewStore, creating tables if they do not exist.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._init_tables()

    # -------------------------------------------------------------------------
    # Internal utilities
    # -------------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        """Return a SQLite connection with row factory set to dict."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """Create required tables if they do not exist."""
        conn = self._connect()
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS review_queue (
                review_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL,
                queued_at TEXT NOT NULL,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'queued',
                assigned_to TEXT,
                notes TEXT,
                last_updated TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS review_actions (
                action_id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL,
                actor TEXT,
                action TEXT,
                payload TEXT,
                created_at TEXT,
                FOREIGN KEY (review_id) REFERENCES review_queue (review_id)
            )
            """
        )

        conn.commit()
        conn.close()

    # -------------------------------------------------------------------------
    # Queue management
    # -------------------------------------------------------------------------
    def enqueue_case(self, case_id: str, priority: str = "medium") -> str:
        """Insert a new review queue item and return its review_id."""
        review_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_queue
                    (review_id, case_id, queued_at, priority, status, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (review_id, case_id, now, priority, "queued", now),
            )
        return review_id

    def get_queue(self, status: str = "queued", limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch cases from the queue filtered by status."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM review_queue WHERE status = ? ORDER BY queued_at ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        """Return a single review entry by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_queue WHERE review_id = ?", (review_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_status(
        self, review_id: str, status: str, notes: Optional[str] = None
    ) -> None:
        """Update the status (accepted/rejected/etc.) and optional notes."""
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE review_queue
                SET status = ?, notes = ?, last_updated = ?
                WHERE review_id = ?
                """,
                (status, notes, now, review_id),
            )

    # -------------------------------------------------------------------------
    # Action logging
    # -------------------------------------------------------------------------
    def log_action(
        self,
        review_id: str,
        actor: str,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Insert a review action (for audit trail)."""
        action_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        payload_json = json.dumps(payload or {})

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO review_actions
                    (action_id, review_id, actor, action, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (action_id, review_id, actor, action, payload_json, now),
            )
        return action_id

    def get_actions(self, review_id: str) -> List[Dict[str, Any]]:
        """Return all actions associated with a review."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM review_actions WHERE review_id = ? ORDER BY created_at ASC",
                (review_id,),
            ).fetchall()
        return [dict(r) for r in rows]
