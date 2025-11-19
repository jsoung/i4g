"""Evidence storage helpers for intake uploads."""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from i4g.settings import get_settings

try:  # pragma: no cover - optional dependency when running in local mode
    from google.cloud import storage
except ImportError:  # pragma: no cover - local/dev environments may not install GCS client
    storage = None


@dataclass
class StoredAttachment:
    """Metadata describing a persisted intake attachment."""

    attachment_id: str
    file_name: str
    content_type: Optional[str]
    size_bytes: int
    checksum_sha256: str
    storage_uri: str
    backend: str


class EvidenceStorage:
    """Persist evidence artifacts to the configured storage backend."""

    def __init__(self, *, local_dir: Optional[Path] = None) -> None:
        self._settings = get_settings()
        storage_settings = self._settings.storage

        if storage_settings.evidence_bucket:
            if storage is None:
                raise RuntimeError("google-cloud-storage required for GCS evidence backend")
            self._backend = "gcs"
            self._bucket_name = storage_settings.evidence_bucket
            self._client = storage.Client(project=storage_settings.firestore_project)
            self._bucket = self._client.bucket(self._bucket_name)
            self._local_dir = None
        else:
            self._backend = "local"
            base_dir = local_dir or Path(storage_settings.evidence_local_dir)
            try:
                base_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                fallback_dir = Path(os.getenv("I4G_RUNTIME__FALLBACK_DIR", "/tmp/i4g/evidence"))
                fallback_dir.mkdir(parents=True, exist_ok=True)
                base_dir = fallback_dir
            self._local_dir = base_dir
            self._bucket_name = None
            self._client = None
            self._bucket = None

    def save(self, intake_id: str, file_name: str, data: bytes, content_type: Optional[str]) -> StoredAttachment:
        """Persist a single attachment and return metadata."""

        if not file_name:
            file_name = "uploaded_evidence"

        clean_name = os.path.basename(file_name)
        checksum = hashlib.sha256(data).hexdigest()
        size_bytes = len(data)

        if self._backend == "local":
            assert self._local_dir is not None  # mypy safeguard
            intake_dir = self._local_dir / intake_id
            intake_dir.mkdir(parents=True, exist_ok=True)
            path = intake_dir / clean_name
            with path.open("wb") as handle:
                handle.write(data)
            storage_uri = str(path)
        else:
            assert self._bucket is not None  # mypy safeguard
            blob_path = f"intake/{intake_id}/{clean_name}"
            blob = self._bucket.blob(blob_path)
            stream = io.BytesIO(data)
            blob.upload_from_file(stream, rewind=True, content_type=content_type)
            storage_uri = f"gs://{self._bucket_name}/{blob_path}"

        attachment_id = hashlib.sha256(f"{intake_id}:{clean_name}:{checksum}".encode()).hexdigest()
        return StoredAttachment(
            attachment_id=attachment_id,
            file_name=clean_name,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum,
            storage_uri=storage_uri,
            backend=self._backend,
        )
