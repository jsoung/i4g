"""Unit tests covering environment variable overrides for settings."""

from __future__ import annotations

import json
import textwrap

from i4g.settings.config import reload_settings


def _clear_env(monkeypatch: object, *names: str) -> None:
    """Remove env vars for every alias and prefixed variant."""

    for name in names:
        monkeypatch.delenv(name, raising=False)
        if name.startswith("I4G_"):
            monkeypatch.delenv(name.removeprefix("I4G_"), raising=False)
        else:
            monkeypatch.delenv(f"I4G_{name}", raising=False)


def _set_env(monkeypatch: object, name: str, value: str) -> None:
    """Set both prefixed and unprefixed aliases for reliability."""

    monkeypatch.setenv(name, value)


def test_llm_provider_env_override(monkeypatch: object) -> None:
    """Ensure the llm.provider value follows environment overrides."""

    _clear_env(monkeypatch, "I4G_LLM__PROVIDER", "I4G_LLM_PROVIDER", "LLM__PROVIDER", "LLM_PROVIDER")

    default_settings = reload_settings(env="dev")
    assert default_settings.llm.provider == "ollama"

    _set_env(monkeypatch, "I4G_LLM__PROVIDER", "mock")
    overridden_settings = reload_settings(env="dev")
    assert overridden_settings.llm.provider == "mock"


def test_account_list_env_overrides(monkeypatch: object) -> None:
    """Verify account list settings respect header/require_api_key/default format env vars."""

    _clear_env(
        monkeypatch,
        "I4G_ACCOUNT_LIST__HEADER_NAME",
        "I4G_ACCOUNT_LIST_HEADER_NAME",
        "ACCOUNT_LIST__HEADER_NAME",
        "ACCOUNT_LIST_HEADER_NAME",
        "I4G_ACCOUNT_LIST__REQUIRE_API_KEY",
        "I4G_ACCOUNT_LIST_REQUIRE_API_KEY",
        "ACCOUNT_LIST__REQUIRE_API_KEY",
        "ACCOUNT_LIST_REQUIRE_API_KEY",
        "I4G_ACCOUNT_LIST__DEFAULT_FORMATS",
        "I4G_ACCOUNT_LIST_DEFAULT_FORMATS",
        "ACCOUNT_LIST__DEFAULT_FORMATS",
        "ACCOUNT_LIST_DEFAULT_FORMATS",
    )

    default_settings = reload_settings(env="dev")
    assert default_settings.account_list.header_name == "X-ACCOUNTLIST-KEY"
    assert default_settings.account_list.require_api_key is True
    assert default_settings.account_list.default_formats == []

    _set_env(monkeypatch, "I4G_ACCOUNT_LIST__HEADER_NAME", "X-ACCOUNT-LIST-OVERRIDE")
    _set_env(monkeypatch, "I4G_ACCOUNT_LIST__REQUIRE_API_KEY", "false")
    _set_env(monkeypatch, "I4G_ACCOUNT_LIST__DEFAULT_FORMATS", json.dumps(["pdf", "xlsx"]))

    overridden_settings = reload_settings(env="dev")
    assert overridden_settings.account_list.header_name == "X-ACCOUNT-LIST-OVERRIDE"
    assert overridden_settings.account_list.require_api_key is False
    assert overridden_settings.account_list.default_formats == ["pdf", "xlsx"]


def test_ingestion_sql_toggle_env_overrides(monkeypatch: object) -> None:
    """Ensure ingestion fan-out toggles respect environment overrides."""

    _clear_env(
        monkeypatch,
        "I4G_INGEST__ENABLE_SQL",
        "I4G_INGEST__ENABLE_FIRESTORE",
        "I4G_INGEST__ENABLE_VERTEX",
        "I4G_INGEST__DEFAULT_DATASET",
        "I4G_INGEST__MAX_RETRIES",
        "I4G_INGEST__RETRY_DELAY_SECONDS",
        "I4G_INGESTION__RETRY_DELAY_SECONDS",
    )

    default_settings = reload_settings(env="dev")
    assert default_settings.ingestion.enable_sql is True
    assert default_settings.ingestion.enable_firestore is False
    assert default_settings.ingestion.enable_vertex is False
    assert default_settings.ingestion.enable_vector_store is True
    assert default_settings.ingestion.default_dataset == "unknown"
    assert default_settings.ingestion.max_retries == 3
    assert default_settings.ingestion.retry_delay_seconds == 60

    _set_env(monkeypatch, "I4G_INGEST__ENABLE_SQL", "false")
    _set_env(monkeypatch, "I4G_INGEST__ENABLE_FIRESTORE", "true")
    _set_env(monkeypatch, "I4G_INGEST__ENABLE_VERTEX", "true")
    _set_env(monkeypatch, "I4G_INGEST__DEFAULT_DATASET", "account_list")
    _set_env(monkeypatch, "I4G_INGEST__MAX_RETRIES", "5")
    _set_env(monkeypatch, "I4G_INGEST__ENABLE_VECTOR", "false")
    _set_env(monkeypatch, "I4G_INGESTION__RETRY_DELAY_SECONDS", "120")

    overridden = reload_settings(env="dev")
    assert overridden.ingestion.enable_sql is False
    assert overridden.ingestion.enable_firestore is True
    assert overridden.ingestion.enable_vertex is True
    assert overridden.ingestion.enable_vector_store is False
    assert overridden.ingestion.default_dataset == "account_list"
    assert overridden.ingestion.max_retries == 5
    assert overridden.ingestion.retry_delay_seconds == 120


def test_settings_file_override(tmp_path, monkeypatch: object) -> None:
    """Ensure TOML config files populate settings without manual env vars."""

    _clear_env(
        monkeypatch,
        "I4G_STORAGE__FIRESTORE_PROJECT",
        "I4G_INGEST__DEFAULT_DATASET",
        "I4G_INGEST__ENABLE_FIRESTORE",
        "I4G_ENV",
    )
    _set_env(monkeypatch, "I4G_ENV", "dev")

    settings_file = tmp_path / "settings.local.toml"
    settings_file.write_text(
        textwrap.dedent(
            """
            env = "dev"

            [storage]
            firestore_project = "i4g-dev"

            [ingestion]
            default_dataset = "toml_dataset"
            enable_firestore = true
            """
        ).strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("I4G_SETTINGS_FILE", str(settings_file))
    settings_from_file = reload_settings()
    assert settings_from_file.storage.firestore_project == "i4g-dev"
    assert settings_from_file.ingestion.default_dataset == "toml_dataset"
    assert settings_from_file.ingestion.enable_firestore is True
    assert settings_file in settings_from_file.config_files

    _set_env(monkeypatch, "I4G_INGEST__DEFAULT_DATASET", "env_dataset")
    env_override = reload_settings()
    assert env_override.ingestion.default_dataset == "env_dataset"
