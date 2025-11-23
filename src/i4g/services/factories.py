"""Factory helpers that instantiate core services based on configuration.

These helpers centralize the logic for honoring the environment-specific
settings declared in :mod:`i4g.settings`. They return the concrete storage or
vector store implementations compatible with the current environment profile,
raising ``NotImplementedError`` when a backend is declared but not yet
implemented.
"""

from __future__ import annotations

from pathlib import Path

from i4g.settings import get_settings
from i4g.storage import EvidenceStorage
from i4g.store.intake_store import IntakeStore
from i4g.store.review_store import ReviewStore
from i4g.store.structured import StructuredStore
from i4g.store.vector import VectorStore


def build_structured_store(db_path: str | Path | None = None) -> StructuredStore:
    """Return a structured-store instance that matches the configured backend.

    Args:
        db_path: Optional path override. When ``None``, the path configured in
            ``settings.storage.sqlite_path`` is used.

    Returns:
        Instantiated :class:`StructuredStore`.

    Raises:
        NotImplementedError: If the configured backend is not yet supported.
    """

    settings = get_settings()
    backend = settings.storage.structured_backend
    if backend == "sqlite":
        return StructuredStore(db_path=db_path)

    if backend == "firestore":
        raise NotImplementedError("Firestore structured backend not implemented yet")

    if backend == "cloudsql":
        raise NotImplementedError("Cloud SQL structured backend not implemented yet")

    raise NotImplementedError(f"Unsupported structured storage backend '{backend}'")


def build_review_store(db_path: str | Path | None = None) -> ReviewStore:
    """Return a :class:`ReviewStore` honoring the structured backend settings."""

    settings = get_settings()
    backend = settings.storage.structured_backend
    if backend == "sqlite":
        return ReviewStore(db_path=db_path)

    if backend == "firestore":
        raise NotImplementedError("Firestore review backend not implemented yet")

    if backend == "cloudsql":
        raise NotImplementedError("Cloud SQL review backend not implemented yet")

    raise NotImplementedError(f"Unsupported review backend '{backend}'")


def build_vector_store(
    *,
    backend: str | None = None,
    persist_dir: str | Path | None = None,
    embedding_model: str | None = None,
    collection_name: str | None = None,
    reset: bool = False,
) -> VectorStore:
    """Return a vector store implementation consistent with current settings.

    Args:
    backend: Explicit backend to use (overrides configured default).
    persist_dir: Optional directory override for the vector backend.
        embedding_model: Embedding model identifier. Defaults to the configured
            ``settings.vector.embedding_model`` when ``None``.
        collection_name: Optional override for the vector collection/index
            name. Defaults to ``settings.vector.collection``.
        reset: Whether to reset any persisted artifacts before instantiation.

    Returns:
    Configured :class:`VectorStore` instance.

    Raises:
        NotImplementedError: If the configured backend lacks an implementation.
    """

    settings = get_settings()
    resolved_backend = (backend or settings.vector.backend).lower()
    model_name = embedding_model or settings.vector.embedding_model
    collection = collection_name or settings.vector.collection

    if resolved_backend in {"chroma", "faiss"}:
        return VectorStore(
            persist_dir=str(persist_dir) if persist_dir is not None else None,
            embedding_model=model_name,
            backend=resolved_backend,
            collection_name=collection,
            reset=reset,
        )

    if resolved_backend == "pgvector":
        raise NotImplementedError("pgvector backend not implemented yet")

    if resolved_backend == "vertex_ai":
        raise NotImplementedError("Vertex AI vector backend not implemented yet")

    raise NotImplementedError(f"Unsupported vector backend '{resolved_backend}'")


def build_intake_store(db_path: str | Path | None = None) -> IntakeStore:
    """Return an :class:`IntakeStore` aligned with the structured backend."""

    settings = get_settings()
    backend = settings.storage.structured_backend
    if backend == "sqlite":
        return IntakeStore(db_path=db_path)

    if backend == "firestore":
        raise NotImplementedError("Firestore intake backend not implemented yet")

    if backend == "cloudsql":
        raise NotImplementedError("Cloud SQL intake backend not implemented yet")

    raise NotImplementedError(f"Unsupported intake storage backend '{backend}'")


def build_evidence_storage(*, local_dir: str | Path | None = None) -> EvidenceStorage:
    """Instantiate the configured evidence storage provider."""

    path = Path(local_dir) if isinstance(local_dir, str) else local_dir
    return EvidenceStorage(local_dir=path)
