"""Configuration loader for i4g services using Pydantic settings."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_VAR_NAME = "I4G_ENV"
DEFAULT_ENV = "local"
PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _resolve_env(explicit_env: str | None = None) -> str:
    env = explicit_env or os.getenv(ENV_VAR_NAME) or DEFAULT_ENV
    return env.strip()


def _env_file_candidates(env: str) -> list[Path]:
    return [
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / f".env.{env}",
        PROJECT_ROOT / ".env.local",
    ]


class Settings(BaseSettings):
    """i4g configuration model."""

    env: str = Field(default_factory=lambda: _resolve_env(), validation_alias="ENV")
    project_root: Path = Field(default=PROJECT_ROOT, validation_alias="PROJECT_ROOT")
    data_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "data", validation_alias="DATA_DIR")
    sqlite_path: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data" / "i4g_store.db",
        validation_alias="SQLITE_PATH",
    )
    chroma_dir: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data" / "chroma_store",
        validation_alias="VECTOR_CHROMA_DIR",
    )
    faiss_dir: Path = Field(
        default_factory=lambda: PROJECT_ROOT / "data" / "faiss_store",
        validation_alias="VECTOR_FAISS_DIR",
    )
    vector_backend: Literal["chroma", "faiss", "pgvector", "vertex_ai"] = Field(
        default="chroma",
        validation_alias="VECTOR_BACKEND",
    )
    vector_collection: str = Field(
        default="i4g_vectors",
        validation_alias="VECTOR_COLLECTION",
    )
    embedding_model: str = Field(
        default="nomic-embed-text",
        validation_alias="EMBED_MODEL",
    )
    api_base_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias="API_URL",
    )
    api_key: str = Field(
        default="dev-analyst-token",
        validation_alias="API_KEY",
    )
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias="OLLAMA_BASE_URL",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    env_files: tuple[Path, ...] = Field(default_factory=tuple, exclude=True)

    model_config = SettingsConfigDict(
        env_prefix="I4G_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )


def _load_settings(env: str | None = None) -> Settings:
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
    return _load_settings(env)


def reload_settings(env: str | None = None) -> Settings:
    get_settings.cache_clear()
    return get_settings(env)


__all__ = [
    "Settings",
    "get_settings",
    "reload_settings",
    "PROJECT_ROOT",
    "ENV_VAR_NAME",
]
