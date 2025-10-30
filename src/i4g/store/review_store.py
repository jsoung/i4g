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

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


class ReviewStore:
    """Lightweight SQLite-based review queue and audit logger."""

    def __init__(self, db_path: str = "data/i4g_store.db") -> None:
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

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_searches (
                search_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner TEXT,
                params TEXT,
                created_at TEXT,
                favorite INTEGER DEFAULT 0,
                tags TEXT DEFAULT '[]'
            )
            """
        )

        # Ensure favorite and tags columns exist for older schemas
        try:
            cur.execute("ALTER TABLE saved_searches ADD COLUMN favorite INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE saved_searches ADD COLUMN tags TEXT DEFAULT '[]'")
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

    # -------------------------------------------------------------------------
    # Queue management
    # -------------------------------------------------------------------------
    def enqueue_case(self, case_id: str, priority: str = "medium") -> str:
        """Insert a new review queue item and return its review_id."""
        review_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

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
        now = datetime.now(timezone.utc).isoformat()
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
        now = datetime.now(timezone.utc).isoformat()
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

    # -------------------------------------------------------------------------
    # Lookup helpers
    # -------------------------------------------------------------------------
    def get_reviews_by_case(self, case_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Return queue entries for a specific case_id ordered by recency."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM review_queue
                WHERE case_id = ?
                ORDER BY queued_at DESC
                LIMIT ?
                """,
                (case_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_actions(self, action: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Return most recent actions, optionally filtered by action name."""
        with self._connect() as conn:
            if action:
                rows = conn.execute(
                    """
                    SELECT * FROM review_actions
                    WHERE action = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (action, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM review_actions
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        result: List[Dict[str, Any]] = []
        for r in rows:
            payload = r.get("payload") if isinstance(r, dict) else r["payload"]
            try:
                payload = json.loads(payload) if payload else {}
            except Exception:
                payload = {}
            item = dict(r)
            item["payload"] = payload
            result.append(item)
        return result

    # -------------------------------------------------------------------------
    # Saved searches
    # -------------------------------------------------------------------------
    def upsert_saved_search(
        self,
        name: str,
        params: Dict[str, Any],
        owner: Optional[str] = None,
        search_id: Optional[str] = None,
        favorite: bool = False,
        tags: Optional[List[str]] = None,
    ) -> str:
        if search_id:
            params["search_id"] = search_id
        search_id = search_id or params.get("search_id") or f"saved:{uuid.uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(params)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO saved_searches (search_id, name, owner, params, created_at, favorite, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(search_id) DO UPDATE SET
                    name = excluded.name,
                    owner = excluded.owner,
                    params = excluded.params,
                    favorite = excluded.favorite,
                    tags = excluded.tags
                """,
                (search_id, name, owner, payload, now, 1 if favorite else 0, json.dumps(tags or [])),
            )
            # Enforce unique name per owner/shared scope
            dup = conn.execute(
                """
                SELECT search_id, owner FROM saved_searches
                WHERE (owner = ? OR (owner IS NULL AND ? IS NULL))
                  AND LOWER(name) = LOWER(?)
                  AND search_id != ?
                LIMIT 1
                """,
                (owner, owner, name, search_id),
            ).fetchone()
            if dup:
                dup_owner = dup[1] if isinstance(dup, tuple) else dup["owner"]
                raise ValueError(f"duplicate_saved_search:{dup_owner or ''}")
        return search_id
    def clone_saved_search(self, search_id: str, target_owner: Optional[str]) -> str:
        record = self.get_saved_search(search_id)
        if not record:
            raise ValueError("saved_search_not_found")
        new_id = f"saved:{uuid.uuid4()}"
        record["params"]["search_id"] = new_id
        return self.upsert_saved_search(
            name=record["name"],
            params=record["params"],
            owner=target_owner,
            search_id=new_id,
            favorite=record.get("favorite", False),
            tags=record.get("tags") or [],
        )

    def list_saved_searches(self, owner: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if owner:
                rows = conn.execute(
                    """
                    SELECT * FROM saved_searches
                    WHERE owner = ? OR owner IS NULL
                    ORDER BY favorite DESC, created_at DESC
                    LIMIT ?
                    """,
                    (owner, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM saved_searches
                    ORDER BY favorite DESC, created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        results: List[Dict[str, Any]] = []
        for r in rows:
            params = r.get("params") if isinstance(r, dict) else r["params"]
            try:
                params = json.loads(params) if params else {}
            except Exception:
                params = {}
            item = dict(r)
            fav_val = item.get("favorite")
            if fav_val is not None:
                item["favorite"] = bool(fav_val)
            tags_val = item.get("tags")
            if isinstance(tags_val, str):
                try:
                    item["tags"] = json.loads(tags_val)
                except Exception:
                    item["tags"] = []
            item["params"] = params
            results.append(item)
        return results

    def delete_saved_search(self, search_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM saved_searches WHERE search_id = ?", (search_id,))
            return cur.rowcount > 0

    def update_saved_search(
        self,
        search_id: str,
        name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        favorite: Optional[bool] = None,
        tags: Optional[List[str]] = None,
    ) -> bool:
        fields = []
        values: List[Any] = []
        if name is not None:
            fields.append("name = ?")
            values.append(name)
        if params is not None:
            fields.append("params = ?")
            values.append(json.dumps(params))
        if favorite is not None:
            fields.append("favorite = ?")
            values.append(1 if favorite else 0)
        if tags is not None:
            fields.append("tags = ?")
            values.append(json.dumps(tags))
        if not fields:
            return False
        with self._connect() as conn:
            if name is not None:
                owner_row = conn.execute(
                    "SELECT owner FROM saved_searches WHERE search_id = ?",
                    (search_id,),
                ).fetchone()
                if not owner_row:
                    return False
                owner = owner_row[0]
                dup = conn.execute(
                    """
                    SELECT search_id, owner FROM saved_searches
                    WHERE (owner = ? OR (owner IS NULL AND ? IS NULL))
                      AND LOWER(name) = LOWER(?)
                      AND search_id != ?
                    LIMIT 1
                    """,
                    (owner, owner, name, search_id),
                ).fetchone()
                if dup:
                    dup_owner = dup[1] if isinstance(dup, tuple) else dup["owner"]
                    raise ValueError(f"duplicate_saved_search:{dup_owner or ''}")
            values.append(search_id)
            cur = conn.execute(
                f"UPDATE saved_searches SET {', '.join(fields)} WHERE search_id = ?",
                tuple(values),
            )
            return cur.rowcount > 0

    def get_saved_search(self, search_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM saved_searches WHERE search_id = ?", (search_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        params = data.get("params")
        try:
            params = json.loads(params) if params else {}
        except Exception:
            params = {}
        data["params"] = params
        fav_val = data.get("favorite")
        if fav_val is not None:
            data["favorite"] = bool(fav_val)
        tags_val = data.get("tags")
        if isinstance(tags_val, str):
            try:
                data["tags"] = json.loads(tags_val)
            except Exception:
                data["tags"] = []
        return data

    def import_saved_search(self, payload: Dict[str, Any], owner: Optional[str] = None) -> str:
        params = payload.get("params", {}) or {}
        name = payload.get("name")
        if not name:
            raise ValueError("invalid_saved_search")
        favorite = bool(payload.get("favorite", False))
        tags = payload.get("tags") or []
        search_id = payload.get("search_id")
        # Make sure params has no lingering search_id before upserting
        params.pop("search_id", None)
        return self.upsert_saved_search(
            name=name,
            params=params,
            owner=owner,
            search_id=search_id,
            favorite=favorite,
            tags=tags,
        )

    def list_tag_presets(self, owner: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT search_id, owner, tags
                FROM saved_searches
                WHERE tags IS NOT NULL AND tags != '[]'
                  AND (? IS NULL OR owner = ?)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (owner, owner, limit),
            ).fetchall()
        presets = []
        for row in rows:
            tags = row["tags"] if isinstance(row, dict) else row[2]
            try:
                tag_list = json.loads(tags) if tags else []
            except Exception:
                tag_list = []
            presets.append({
                "search_id": row["search_id"] if isinstance(row, dict) else row[0],
                "owner": row["owner"] if isinstance(row, dict) else row[1],
                "tags": tag_list,
            })
        return presets

    def bulk_update_tags(
        self,
        search_ids: Iterable[str],
        add: Optional[List[str]] = None,
        remove: Optional[List[str]] = None,
        replace: Optional[List[str]] = None,
    ) -> int:
        add = [t.strip() for t in (add or []) if t.strip()]
        remove = {t.strip().lower() for t in (remove or []) if t.strip()}
        replace = [t.strip() for t in (replace or []) if t.strip()] if replace is not None else None
        updated = 0
        for search_id in search_ids:
            record = self.get_saved_search(search_id)
            if not record:
                continue
            tags = replace if replace is not None else list(record.get("tags") or [])
            if replace is None:
                tags = [t for t in tags if t.lower() not in remove]
                tags.extend(add)
            # dedupe while preserving order
            seen = set()
            normalized = []
            for tag in tags:
                key = tag.lower()
                if key not in seen:
                    seen.add(key)
                    normalized.append(tag)
            if self.update_saved_search(search_id, tags=normalized):
                updated += 1
        return updated
