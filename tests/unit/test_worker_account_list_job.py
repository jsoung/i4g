"""Unit tests for the account list Cloud Run job."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from i4g.services.account_list import AccountListRequest, AccountListResult
from i4g.worker.jobs import account_list as account_job


def _settings(default_formats: list[str] | None = None, max_top_k: int = 250, env: str = "local") -> SimpleNamespace:
    return SimpleNamespace(
        env=env,
        account_list=SimpleNamespace(
            default_formats=default_formats or ["pdf"],
            max_top_k=max_top_k,
        ),
    )


def test_build_request_defaults(monkeypatch):
    reference = datetime(2025, 11, 15, tzinfo=timezone.utc)
    monkeypatch.delenv("I4G_ACCOUNT_JOB__START_TIME", raising=False)
    monkeypatch.delenv("I4G_ACCOUNT_JOB__END_TIME", raising=False)
    monkeypatch.delenv("I4G_ACCOUNT_JOB__WINDOW_DAYS", raising=False)
    monkeypatch.delenv("I4G_ACCOUNT_JOB__OUTPUT_FORMATS", raising=False)

    request = account_job._build_request_from_env(_settings(), now=reference)

    assert request.end_time == reference
    assert request.start_time == reference - timedelta(days=15)
    assert request.output_formats == ["pdf"]
    assert request.include_sources is True


def test_build_request_env_overrides(monkeypatch):
    monkeypatch.setenv("I4G_ACCOUNT_JOB__START_TIME", "2025-11-01T00:00:00Z")
    monkeypatch.setenv("I4G_ACCOUNT_JOB__END_TIME", "2025-11-15T12:00:00+00:00")
    monkeypatch.setenv("I4G_ACCOUNT_JOB__WINDOW_DAYS", "10")
    monkeypatch.setenv("I4G_ACCOUNT_JOB__CATEGORIES", "bank, crypto , payments")
    monkeypatch.setenv("I4G_ACCOUNT_JOB__TOP_K", "999")
    monkeypatch.setenv("I4G_ACCOUNT_JOB__INCLUDE_SOURCES", "false")
    monkeypatch.setenv("I4G_ACCOUNT_JOB__OUTPUT_FORMATS", "csv,pdf")

    request = account_job._build_request_from_env(_settings(default_formats=[], max_top_k=500))

    assert request.start_time == datetime(2025, 11, 1, 0, 0, tzinfo=timezone.utc)
    assert request.end_time == datetime(2025, 11, 15, 12, 0, tzinfo=timezone.utc)
    assert request.categories == ["bank", "crypto", "payments"]
    assert request.top_k == 500  # capped at max_top_k
    assert request.include_sources is False
    assert request.output_formats == ["csv", "pdf"]


def test_main_dry_run_skips_service(monkeypatch):
    now = datetime.now(timezone.utc)
    request = AccountListRequest(
        start_time=now - timedelta(days=1),
        end_time=now,
        categories=["bank"],
        top_k=10,
        include_sources=True,
        output_formats=["pdf"],
    )

    monkeypatch.setenv("I4G_ACCOUNT_JOB__DRY_RUN", "true")
    monkeypatch.setattr(account_job, "get_settings", lambda: _settings())
    monkeypatch.setattr(account_job, "_build_request_from_env", lambda settings: request)

    build_called = SimpleNamespace(value=False)

    def _fake_build_service():
        build_called.value = True
        return MagicMock()

    monkeypatch.setattr(account_job, "_build_service", _fake_build_service)

    assert account_job.main() == 0
    assert build_called.value is False


def test_main_runs_service(monkeypatch):
    now = datetime.now(timezone.utc)
    request = AccountListRequest(
        start_time=now - timedelta(days=1),
        end_time=now,
        categories=["bank"],
        top_k=10,
        include_sources=True,
        output_formats=["pdf"],
    )
    result = AccountListResult(
        request_id="req-1",
        generated_at=now,
        indicators=[],
        sources=[],
        warnings=[],
        metadata={},
        artifacts={"pdf": "gs://bucket/account.pdf"},
    )

    service = MagicMock()
    service.run.return_value = result

    monkeypatch.delenv("I4G_ACCOUNT_JOB__DRY_RUN", raising=False)
    monkeypatch.setattr(account_job, "get_settings", lambda: _settings())
    monkeypatch.setattr(account_job, "_build_request_from_env", lambda settings: request)
    monkeypatch.setattr(account_job, "_build_service", lambda: service)

    log_calls: list[dict[str, object]] = []

    def _capture_log(**kwargs):
        log_calls.append(kwargs)

    monkeypatch.setattr(account_job, "log_account_list_run", _capture_log)

    assert account_job.main() == 0
    service.run.assert_called_once_with(request)
    assert log_calls
    assert log_calls[0]["actor"] == "account_job:local"
    assert log_calls[0]["result"] is result


def test_main_handles_failures(monkeypatch):
    now = datetime.now(timezone.utc)
    request = AccountListRequest(
        start_time=now - timedelta(days=1),
        end_time=now,
        categories=["bank"],
        top_k=10,
        include_sources=True,
        output_formats=["pdf"],
    )

    monkeypatch.setattr(account_job, "get_settings", lambda: _settings())
    monkeypatch.setattr(account_job, "_build_request_from_env", lambda settings: request)

    failing_service = MagicMock()
    failing_service.run.side_effect = RuntimeError("boom")
    monkeypatch.setattr(account_job, "_build_service", lambda: failing_service)

    assert account_job.main() == 1
    failing_service.run.assert_called_once_with(request)


def test_main_invalid_config(monkeypatch):
    monkeypatch.setattr(account_job, "get_settings", lambda: _settings())

    def _raise(_settings):  # pragma: no cover - executed in test only
        raise ValueError("bad config")

    monkeypatch.setattr(account_job, "_build_request_from_env", _raise)

    assert account_job.main() == 1
