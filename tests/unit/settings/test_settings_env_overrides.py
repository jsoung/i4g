"""Unit tests covering environment variable overrides for settings."""

from __future__ import annotations

import json

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
