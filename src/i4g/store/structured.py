"""SQLite-backed structured storage layer for i4g.

This module provides a small, dependency-free wrapper around sqlite3 for
persisting ScamRecord objects. It stores JSON fields for `entities`, `embedding`,
and `metadata` and exposes simple CRUD / search operations.

Note:
- Uses SQLite JSON1 functions when available for simple JSON lookups.
- Designed for local development; production can switch to Postgres by
  implementing compatible methods.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from i4g.settings import get_settings
from i4g.store.schema import ScamRecord

SETTINGS = get_settings()


def _ensure_dir_for_db(db_path: str | Path) -> None:
    """Ensure parent directory for the DB file exists."""
    p = Path(db_path)
    if p.parent:
        p.parent.mkdir(parents=True, exist_ok=True)


class StructuredStore:
    """Simple SQLite store for ScamRecord objects.

    This class intentionally keeps the surface area small and explicit so it
    is easy to test and to replace with another backend later.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize the StructuredStore.

        Args:
            db_path: Path to the SQLite file.
        """
        resolved_path = Path(db_path) if db_path else Path(SETTINGS.storage.sqlite_path)
        if not resolved_path.is_absolute():
            resolved_path = (Path(SETTINGS.project_root) / resolved_path).resolve()
        _ensure_dir_for_db(resolved_path)
        self.db_path = str(resolved_path)
        self._conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        # enable returning rows as dict-like
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        try:
            self._conn.close()
        except Exception:
            pass

    def _ensure_table(self) -> None:
        """Create the records table if it doesn't exist."""
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS scam_records (
                case_id TEXT PRIMARY KEY,
                text TEXT,
                entities TEXT,         -- JSON
                classification TEXT,
                confidence REAL,
                created_at TEXT,
                embedding TEXT,        -- JSON array
                metadata TEXT          -- JSON
            )
            """
        )
        # index for quick filtering by classification/confidence
        cur.execute("CREATE INDEX IF NOT EXISTS idx_classification ON scam_records (classification)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_confidence ON scam_records (confidence)")
        self._conn.commit()

    def upsert_record(self, record: ScamRecord) -> None:
        """Insert or update a ScamRecord.

        Args:
            record: ScamRecord instance to persist.
        """
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO scam_records (case_id, text, entities, classification, confidence, created_at, embedding, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                text=excluded.text,
                entities=excluded.entities,
                classification=excluded.classification,
                confidence=excluded.confidence,
                created_at=excluded.created_at,
                embedding=excluded.embedding,
                metadata=excluded.metadata
            """,
            (
                record.case_id,
                record.text,
                json.dumps(record.entities),
                record.classification,
                float(record.confidence),
                record.created_at.isoformat(),
                json.dumps(record.embedding) if record.embedding is not None else None,
                json.dumps(record.metadata) if record.metadata is not None else None,
            ),
        )
        self._conn.commit()

    def get_by_id(self, case_id: str) -> Optional[ScamRecord]:
        """Retrieve a record by case_id.

        Args:
            case_id: The unique case identifier.

        Returns:
            ScamRecord instance or None if not found.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM scam_records WHERE case_id = ?", (case_id,))
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def _row_to_record(self, row: sqlite3.Row) -> ScamRecord:
        """Convert a sqlite3.Row to ScamRecord."""
        entities = {}
        try:
            entities = json.loads(row["entities"]) if row["entities"] else {}
        except Exception:
            entities = {}

        embedding = None
        try:
            embedding = json.loads(row["embedding"]) if row["embedding"] else None
        except Exception:
            embedding = None

        metadata = {}
        try:
            metadata = json.loads(row["metadata"]) if row["metadata"] else None
        except Exception:
            metadata = None

        created_at = row["created_at"]
        try:
            created_at = datetime.fromisoformat(created_at) if isinstance(created_at, str) else created_at
        except Exception:
            created_at = datetime.utcnow()

        return ScamRecord(
            case_id=row["case_id"],
            text=row["text"],
            entities=entities,
            classification=row["classification"],
            confidence=(float(row["confidence"]) if row["confidence"] is not None else 0.0),
            created_at=created_at,
            embedding=embedding,
            metadata=metadata,
        )

    def list_recent(self, limit: int = 50) -> List[ScamRecord]:
        """List the most recent records ordered by created_at descending.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of ScamRecord objects.
        """
        cur = self._conn.cursor()
        cur.execute("SELECT * FROM scam_records ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [self._row_to_record(r) for r in rows]

    def search_by_field(self, field: str, value: Any, top_k: int = 50) -> List[ScamRecord]:
        """Search records by a top-level field or inside the JSON entities.

        Supported fields:
          - case_id
          - classification
          - confidence (accepts numeric or comparison string like '>0.8')
          - any key inside entities JSON (uses json_extract if available)

        Args:
            field: Field name to query.
            value: Value to match (string or number).
            top_k: Maximum number of results to return.

        Returns:
            List of ScamRecord objects matching the query.
        """
        cur = self._conn.cursor()

        # Special-case numeric comparison for confidence (e.g., '>0.8' or '<0.5')
        if field == "confidence" and isinstance(value, str) and value.startswith((">", "<", ">=", "<=")):
            op = value[0]
            num = float(value[1:])
            if value.startswith(">="):
                op = ">="
                num = float(value[2:])
            elif value.startswith("<="):
                op = "<="
                num = float(value[2:])
            cur.execute(
                f"SELECT * FROM scam_records WHERE confidence {op} ? ORDER BY confidence DESC LIMIT ?",
                (num, top_k),
            )
            rows = cur.fetchall()
            return [self._row_to_record(r) for r in rows]

        # Simple equality on case_id or classification
        if field in ("case_id", "classification"):
            cur.execute(f"SELECT * FROM scam_records WHERE {field} = ? LIMIT ?", (value, top_k))
            rows = cur.fetchall()
            return [self._row_to_record(r) for r in rows]

        if field == "dataset":
            return self._search_by_dataset(value, top_k)

        # Try JSON extraction (works if SQLite built with JSON1)
        try:
            # json_extract returns NULL when path not found
            # value match attempts a simple substring match inside the JSON array element strings
            sql = f"""
            SELECT * FROM scam_records
            WHERE json_extract(entities, '$.{field}') IS NOT NULL
              AND json_extract(entities, '$.{field}') != '[]'
            LIMIT ?
            """
            cur.execute(sql, (top_k,))
            rows = cur.fetchall()
            # Optionally filter rows by value inclusion if a specific value is requested
            if isinstance(value, str):
                filtered = []
                for r in rows:
                    ents = json.loads(r["entities"]) if r["entities"] else {}
                    if field in ents and any(value.lower() in str(x).lower() for x in ents[field]):
                        filtered.append(r)
                return [self._row_to_record(r) for r in filtered[:top_k]]
            return [self._row_to_record(r) for r in rows]
        except sqlite3.OperationalError:
            # If json_extract is not available, fallback to loading all rows and filtering in Python
            cur.execute("SELECT * FROM scam_records LIMIT ?", (top_k,))
            rows = cur.fetchall()
            results = []
            for r in rows:
                ents = {}
                try:
                    ents = json.loads(r["entities"]) if r["entities"] else {}
                except Exception:
                    ents = {}
                if field in ents and any(value.lower() in str(x).lower() for x in ents[field]):
                    results.append(self._row_to_record(r))
                    if len(results) >= top_k:
                        break
            return results

    def search_text(self, query: str, top_k: int = 50, offset: int = 0) -> List[ScamRecord]:
        """Run a simple case-insensitive substring search against the text column."""

        if not query:
            return []

        tokens = [token.strip() for token in query.split() if token.strip()]
        if tokens:
            pattern = "%" + "%".join(tokens) + "%"
        else:
            pattern = f"%{query.strip()}%"

        pattern = pattern.lower()
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT * FROM scam_records
            WHERE lower(text) LIKE ?
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (pattern, top_k, offset),
        )
        rows = cur.fetchall()
        return [self._row_to_record(r) for r in rows]

    def delete_by_id(self, case_id: str) -> bool:
        """Delete a record by case_id.

        Args:
            case_id: The case id to delete.

        Returns:
            True if a row was deleted, False otherwise.
        """
        cur = self._conn.cursor()
        cur.execute("DELETE FROM scam_records WHERE case_id = ?", (case_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def _search_by_dataset(self, dataset: Any, top_k: int) -> List[ScamRecord]:
        """Return records whose metadata.dataset matches the requested dataset."""

        if dataset is None:
            return []
        target = str(dataset).strip().lower()
        if not target:
            return []

        cur = self._conn.cursor()
        cur.execute("SELECT * FROM scam_records WHERE metadata IS NOT NULL")
        rows = cur.fetchall()
        results: List[ScamRecord] = []
        for row in rows:
            metadata = {}
            try:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            except Exception:
                metadata = {}
            dataset_value = metadata.get("dataset") or metadata.get("source")
            if dataset_value and str(dataset_value).strip().lower() == target:
                results.append(self._row_to_record(row))
                if len(results) >= top_k:
                    break
        return results
