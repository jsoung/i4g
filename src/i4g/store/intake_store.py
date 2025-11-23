"""SQLite-backed intake storage for i4g."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from i4g.settings import get_settings

SETTINGS = get_settings()


class IntakeStore:
    """Persist victim intake records, attachments, and job status metadata."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        resolved = Path(db_path) if db_path else Path(SETTINGS.storage.sqlite_path)
        if not resolved.is_absolute():
            resolved = (Path(SETTINGS.project_root) / resolved).resolve()
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            fallback = Path(os.getenv("I4G_RUNTIME__FALLBACK_DIR", "/tmp/i4g/sqlite")) / "intake.db"
            fallback.parent.mkdir(parents=True, exist_ok=True)
            resolved = fallback
        self.db_path = resolved
        self._init_tables()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS intake_records (
                    intake_id TEXT PRIMARY KEY,
                    reporter_name TEXT,
                    contact_email TEXT,
                    contact_phone TEXT,
                    contact_handle TEXT,
                    preferred_contact TEXT,
                    incident_date TEXT,
                    loss_amount REAL,
                    summary TEXT,
                    details TEXT,
                    status TEXT,
                    submitted_by TEXT,
                    source TEXT,
                    case_id TEXT,
                    review_id TEXT,
                    job_id TEXT,
                    job_status TEXT,
                    job_message TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS intake_attachments (
                    attachment_id TEXT PRIMARY KEY,
                    intake_id TEXT NOT NULL,
                    file_name TEXT,
                    content_type TEXT,
                    size_bytes INTEGER,
                    checksum_sha256 TEXT,
                    storage_uri TEXT,
                    storage_backend TEXT,
                    created_at TEXT,
                    FOREIGN KEY (intake_id) REFERENCES intake_records (intake_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS intake_jobs (
                    job_id TEXT PRIMARY KEY,
                    intake_id TEXT NOT NULL,
                    status TEXT,
                    message TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (intake_id) REFERENCES intake_records (intake_id)
                )
                """
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Intake CRUD
    # ------------------------------------------------------------------
    def create_intake(
        self,
        *,
        reporter_name: str,
        summary: str,
        details: str,
        submitted_by: str,
        contact_email: str | None = None,
        contact_phone: str | None = None,
        contact_handle: str | None = None,
        preferred_contact: str | None = None,
        incident_date: str | None = None,
        loss_amount: float | None = None,
        source: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        intake_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO intake_records (
                    intake_id,
                    reporter_name,
                    contact_email,
                    contact_phone,
                    contact_handle,
                    preferred_contact,
                    incident_date,
                    loss_amount,
                    summary,
                    details,
                    status,
                    submitted_by,
                    source,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    intake_id,
                    reporter_name,
                    contact_email,
                    contact_phone,
                    contact_handle,
                    preferred_contact,
                    incident_date,
                    loss_amount,
                    summary,
                    details,
                    "received",
                    submitted_by,
                    source,
                    json.dumps(metadata or {}),
                    now,
                    now,
                ),
            )
        return intake_id

    def update_intake_status(self, intake_id: str, status: str, message: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE intake_records
                SET status = ?, job_message = COALESCE(?, job_message), updated_at = ?
                WHERE intake_id = ?
                """,
                (status, message, now, intake_id),
            )

    def attach_case(self, intake_id: str, *, case_id: Optional[str], review_id: Optional[str]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE intake_records
                SET case_id = COALESCE(?, case_id), review_id = COALESCE(?, review_id), updated_at = ?
                WHERE intake_id = ?
                """,
                (case_id, review_id, now, intake_id),
            )

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------
    def add_attachment(
        self,
        intake_id: str,
        *,
        file_name: str,
        content_type: Optional[str],
        size_bytes: int,
        checksum_sha256: str,
        storage_uri: str,
        storage_backend: str,
    ) -> str:
        attachment_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO intake_attachments (
                    attachment_id,
                    intake_id,
                    file_name,
                    content_type,
                    size_bytes,
                    checksum_sha256,
                    storage_uri,
                    storage_backend,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment_id,
                    intake_id,
                    file_name,
                    content_type,
                    size_bytes,
                    checksum_sha256,
                    storage_uri,
                    storage_backend,
                    created_at,
                ),
            )
        return attachment_id

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------
    def create_job(
        self,
        intake_id: str,
        *,
        status: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO intake_jobs (
                    job_id,
                    intake_id,
                    status,
                    message,
                    metadata,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, intake_id, status, message, json.dumps(metadata or {}), now, now),
            )
            conn.execute(
                """
                UPDATE intake_records
                SET job_id = ?, job_status = ?, job_message = ?, updated_at = ?
                WHERE intake_id = ?
                """,
                (job_id, status, message, now, intake_id),
            )
        return job_id

    def update_job_status(
        self,
        job_id: str,
        *,
        status: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE intake_jobs
                SET status = ?, message = ?, metadata = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, message, json.dumps(metadata or {}), now, job_id),
            )
            if result.rowcount == 0:
                return False
            conn.execute(
                """
                UPDATE intake_records
                SET job_status = ?, job_message = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (status, message, now, job_id),
            )
        return True

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------
    def get_intake(self, intake_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM intake_records WHERE intake_id = ?", (intake_id,)).fetchone()
            if not row:
                return None
            attachments = conn.execute(
                "SELECT * FROM intake_attachments WHERE intake_id = ? ORDER BY created_at ASC",
                (intake_id,),
            ).fetchall()
            job = None
            if row["job_id"]:
                job = conn.execute("SELECT * FROM intake_jobs WHERE job_id = ?", (row["job_id"],)).fetchone()
        record = dict(row)
        record["metadata"] = json.loads(record.get("metadata") or "{}")
        record["attachments"] = [dict(a) for a in attachments]
        if job:
            job_dict = dict(job)
            job_dict["metadata"] = json.loads(job_dict.get("metadata") or "{}")
            record["job"] = job_dict
        else:
            record["job"] = None
        return record

    def list_intakes(self, limit: int = 25) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM intake_records ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["metadata"] = json.loads(data.get("metadata") or "{}")
            results.append(data)
        return results

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM intake_jobs WHERE job_id = ?", (job_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["metadata"] = json.loads(data.get("metadata") or "{}")
        return data
