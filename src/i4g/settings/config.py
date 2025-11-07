"""Configuration loader for i4g services using Pydantic settings."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_VAR_NAME = "I4G_ENV"
DEFAULT_ENV = "local"
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _resolve_env(explicit_env: str | None = None) -> str:
    """Return the active environment name.

    Args:
        explicit_env: Environment value supplied directly by the caller.

    Returns:
        A stripped environment name, falling back to ``DEFAULT_ENV``.
    """

    env = explicit_env or os.getenv(ENV_VAR_NAME) or DEFAULT_ENV
    return env.strip()


def _env_file_candidates(env: str) -> list[Path]:
    """List candidate ``.env`` files used during settings resolution.

    Args:
        env: Active environment name (for example, ``local`` or ``staging``).

    Returns:
        Ordered list of paths that should be considered when loading
        environment variables from disk.
    """

    return [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / f".env.{env}",
        PROJECT_ROOT / ".env.local",
    ]


class RuntimeSettings(BaseModel):
    """Process-level runtime controls."""

    model_config = SettingsConfigDict(extra="ignore")

    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("LOG_LEVEL", "RUNTIME__LOG_LEVEL"),
    )


class APISettings(BaseModel):
    """API endpoint configuration shared by CLI + dashboards."""

    model_config = SettingsConfigDict(extra="ignore")

    base_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias=AliasChoices("API_URL", "API__BASE_URL"),
    )
    key: str = Field(
        default="dev-analyst-token",
        validation_alias=AliasChoices("API_KEY", "API__KEY"),
    )


class IdentitySettings(BaseModel):
    """Identity provider wiring for auth-enabled services."""

    model_config = SettingsConfigDict(extra="ignore")

    provider: Literal["mock", "google_identity", "authentik", "firebase"] = Field(
        default="mock",
        validation_alias=AliasChoices("IDENTITY_PROVIDER", "IDENTITY__PROVIDER"),
    )
    audience: str | None = Field(
        default=None,
        validation_alias=AliasChoices("IDENTITY_AUDIENCE", "IDENTITY__AUDIENCE"),
    )
    issuer: str | None = Field(
        default=None,
        validation_alias=AliasChoices("IDENTITY_ISSUER", "IDENTITY__ISSUER"),
    )
    client_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("IDENTITY_CLIENT_ID", "IDENTITY__CLIENT_ID"),
    )
    disable_auth: bool = Field(
        default=False,
        validation_alias=AliasChoices("IDENTITY_DISABLE_AUTH", "IDENTITY__DISABLE_AUTH"),
    )


class StorageSettings(BaseModel):
    """Structured + blob storage configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    structured_backend: Literal["sqlite", "firestore", "cloudsql"] = Field(
        default="sqlite",
        validation_alias=AliasChoices("STRUCTURED_BACKEND", "STORAGE__STRUCTURED_BACKEND"),
    )
    sqlite_path: Path = Field(
        default=PROJECT_ROOT / "data" / "i4g_store.db",
        validation_alias=AliasChoices("SQLITE_PATH", "STORAGE__SQLITE_PATH"),
    )
    firestore_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FIRESTORE_PROJECT", "STORAGE__FIRESTORE__PROJECT"),
    )
    firestore_collection: str = Field(
        default="cases",
        validation_alias=AliasChoices("FIRESTORE_COLLECTION", "STORAGE__FIRESTORE__COLLECTION"),
    )
    evidence_bucket: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_EVIDENCE_BUCKET", "STORAGE__EVIDENCE_BUCKET"),
    )
    reports_bucket: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STORAGE_REPORTS_BUCKET", "STORAGE__REPORTS_BUCKET"),
    )
    cloudsql_instance: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CLOUDSQL_INSTANCE", "STORAGE__CLOUDSQL__INSTANCE"),
    )
    cloudsql_database: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CLOUDSQL_DATABASE", "STORAGE__CLOUDSQL__DATABASE"),
    )


class VectorSettings(BaseModel):
    """Vector store configuration supporting multiple backends."""

    model_config = SettingsConfigDict(extra="ignore")

    backend: Literal["chroma", "faiss", "pgvector", "vertex_ai"] = Field(
        default="chroma",
        validation_alias=AliasChoices("VECTOR_BACKEND", "VECTOR__BACKEND"),
    )
    collection: str = Field(
        default="i4g_vectors",
        validation_alias=AliasChoices("VECTOR_COLLECTION", "VECTOR__COLLECTION"),
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        validation_alias=AliasChoices("EMBED_MODEL", "VECTOR__EMBED_MODEL"),
    )
    chroma_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "chroma_store",
        validation_alias=AliasChoices("VECTOR_CHROMA_DIR", "VECTOR__CHROMA_DIR"),
    )
    faiss_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "faiss_store",
        validation_alias=AliasChoices("VECTOR_FAISS_DIR", "VECTOR__FAISS_DIR"),
    )
    pgvector_dsn: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VECTOR_PGVECTOR_DSN", "VECTOR__PGVECTOR__DSN"),
    )
    vertex_ai_index: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VECTOR_VERTEX_AI_INDEX", "VECTOR__VERTEX_AI__INDEX"),
    )
    vertex_ai_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VECTOR_VERTEX_AI_PROJECT", "VECTOR__VERTEX_AI__PROJECT"),
    )
    vertex_ai_location: str | None = Field(
        default="us-central1",
        validation_alias=AliasChoices("VECTOR_VERTEX_AI_LOCATION", "VECTOR__VERTEX_AI__LOCATION"),
    )


class LLMSettings(BaseModel):
    """Large language model provider settings."""

    model_config = SettingsConfigDict(extra="ignore")

    provider: Literal["ollama", "vertex_ai", "mock"] = Field(
        default="ollama",
        validation_alias=AliasChoices("LLM_PROVIDER", "LLM__PROVIDER"),
    )
    chat_model: str = Field(
        default="llama3",
        validation_alias=AliasChoices("LLM_CHAT_MODEL", "LLM__CHAT_MODEL"),
    )
    temperature: float = Field(
        default=0.1,
        validation_alias=AliasChoices("LLM_TEMPERATURE", "LLM__TEMPERATURE"),
    )
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "LLM__OLLAMA_BASE_URL"),
    )
    vertex_ai_model: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_VERTEX_AI_MODEL", "LLM__VERTEX_AI__MODEL"),
    )
    vertex_ai_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("LLM_VERTEX_AI_PROJECT", "LLM__VERTEX_AI__PROJECT"),
    )
    vertex_ai_location: str | None = Field(
        default="us-central1",
        validation_alias=AliasChoices("LLM_VERTEX_AI_LOCATION", "LLM__VERTEX_AI__LOCATION"),
    )


class SecretsSettings(BaseModel):
    """Secret resolution strategy (local vs Secret Manager)."""

    model_config = SettingsConfigDict(extra="ignore")

    use_secret_manager: bool = Field(
        default=False,
        validation_alias=AliasChoices("SECRETS_USE_SECRET_MANAGER", "SECRETS__USE_SECRET_MANAGER"),
    )
    project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SECRETS_PROJECT", "SECRETS__PROJECT"),
    )
    local_env_file: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("SECRETS_LOCAL_ENV_FILE", "SECRETS__LOCAL_ENV_FILE"),
    )


class IngestionSettings(BaseModel):
    """Scheduler + job configuration for ingestion workflows."""

    model_config = SettingsConfigDict(extra="ignore")

    enable_scheduled_jobs: bool = Field(
        default=False,
        validation_alias=AliasChoices("INGESTION_ENABLE_SCHEDULED_JOBS", "INGESTION__ENABLE_SCHEDULED_JOBS"),
    )
    default_region: str = Field(
        default="us-central1",
        validation_alias=AliasChoices("INGESTION_DEFAULT_REGION", "INGESTION__DEFAULT_REGION"),
    )
    scheduler_project: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INGESTION_SCHEDULER_PROJECT", "INGESTION__SCHEDULER_PROJECT"),
    )
    default_service_account: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INGESTION_SERVICE_ACCOUNT", "INGESTION__SERVICE_ACCOUNT"),
    )


class ObservabilitySettings(BaseModel):
    """Logging, tracing, and metrics configuration."""

    model_config = SettingsConfigDict(extra="ignore")

    structured_logging: bool = Field(
        default=True,
        validation_alias=AliasChoices("OBS_STRUCTURED_LOGGING", "OBSERVABILITY__STRUCTURED_LOGGING"),
    )
    otlp_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OBS_OTLP_ENDPOINT", "OBSERVABILITY__OTLP_ENDPOINT"),
    )
    trace_sample_rate: float = Field(
        default=0.0,
        validation_alias=AliasChoices("OBS_TRACE_SAMPLE_RATE", "OBSERVABILITY__TRACE_SAMPLE_RATE"),
    )


class Settings(BaseSettings):
    """Top-level configuration model with nested sections for each subsystem."""

    env: str = Field(
        default_factory=lambda: _resolve_env(),
        validation_alias=AliasChoices("ENV", "ENVIRONMENT", "RUNTIME__ENV"),
    )
    project_root: Path = Field(
        default=PROJECT_ROOT,
        validation_alias=AliasChoices("PROJECT_ROOT", "RUNTIME__PROJECT_ROOT"),
    )
    data_dir: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data",
        validation_alias=AliasChoices("DATA_DIR", "RUNTIME__DATA_DIR"),
    )
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    api: APISettings = Field(default_factory=APISettings)
    identity: IdentitySettings = Field(default_factory=IdentitySettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    vector: VectorSettings = Field(default_factory=VectorSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    secrets: SecretsSettings = Field(default_factory=SecretsSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    env_files: tuple[Path, ...] = Field(default_factory=tuple, exclude=True)

    model_config = SettingsConfigDict(
        env_prefix="I4G_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        """Normalize relative paths once the model is initialised."""

        if not self.data_dir.is_absolute():
            object.__setattr__(self, "data_dir", (self.project_root / self.data_dir).resolve())

        storage_updates = {}
        if not self.storage.sqlite_path.is_absolute():
            storage_updates["sqlite_path"] = (self.project_root / self.storage.sqlite_path).resolve()
        if storage_updates:
            object.__setattr__(self, "storage", self.storage.model_copy(update=storage_updates))

        vector_updates = {}
        if not self.vector.chroma_dir.is_absolute():
            vector_updates["chroma_dir"] = (self.project_root / self.vector.chroma_dir).resolve()
        if not self.vector.faiss_dir.is_absolute():
            vector_updates["faiss_dir"] = (self.project_root / self.vector.faiss_dir).resolve()
        if vector_updates:
            object.__setattr__(self, "vector", self.vector.model_copy(update=vector_updates))

        if self.secrets.local_env_file and not self.secrets.local_env_file.is_absolute():
            secrets_update = {"local_env_file": (self.project_root / self.secrets.local_env_file).resolve()}
            object.__setattr__(self, "secrets", self.secrets.model_copy(update=secrets_update))

        return self

    @property
    def log_level(self) -> str:
        """str: Effective logging level for the running process."""

        return self.runtime.log_level

    @property
    def api_base_url(self) -> str:
        """str: Base URL for API calls (used by scripts and dashboards)."""

        return self.api.base_url

    @property
    def api_key(self) -> str:
        """str: Shared API token for simple authenticated endpoints."""

        return self.api.key

    @property
    def sqlite_path(self) -> Path:
        """Path: Filesystem path for the local SQLite database."""

        return self.storage.sqlite_path

    @property
    def vector_backend(self) -> str:
        """str: Name of the configured vector store backend."""

        return self.vector.backend

    @property
    def vector_collection(self) -> str:
        """str: Default collection or index identifier for vector storage."""

        return self.vector.collection

    @property
    def embedding_model(self) -> str:
        """str: Embedding model identifier used for vector generation."""

        return self.vector.embedding_model

    @property
    def chroma_dir(self) -> Path:
        """Path: Directory where Chroma persists its state."""

        return self.vector.chroma_dir

    @property
    def faiss_dir(self) -> Path:
        """Path: Directory where FAISS index artifacts are stored."""

        return self.vector.faiss_dir

    @property
    def ollama_base_url(self) -> str:
        """str: Base URL for the Ollama HTTP API."""

        return self.llm.ollama_base_url


def _load_settings(env: str | None = None) -> Settings:
    """Load settings with optional environment override.

    Args:
        env: Environment name supplied programmatically.

    Returns:
        Fully parsed :class:`Settings` instance with env files applied.
    """

    resolved_env = _resolve_env(env)
    candidate_files = [path for path in _env_file_candidates(resolved_env) if path.exists()]
    return Settings(
        _env_file=[str(path) for path in candidate_files],
        _env_file_encoding="utf-8",
        env=resolved_env,
        env_files=tuple(candidate_files),
    )


@lru_cache(maxsize=1)
def get_settings(env: str | None = None) -> Settings:
    """Return cached settings for the requested environment."""

    return _load_settings(env)


def reload_settings(env: str | None = None) -> Settings:
    """Clear the cached settings and reload from disk."""

    get_settings.cache_clear()
    return get_settings(env)


__all__ = [
    "Settings",
    "get_settings",
    "reload_settings",
    "PROJECT_ROOT",
    "ENV_VAR_NAME",
]
