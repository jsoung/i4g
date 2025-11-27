"""Cloud Run job entrypoint for scheduled account list extraction."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from i4g.services.account_list import AccountListRequest, AccountListResult, AccountListService
from i4g.settings import Settings, get_settings

LOGGER = logging.getLogger("i4g.worker.jobs.account_list")
_BOOL_TRUE = {"1", "true", "yes", "on"}
_DEFAULT_FORMATS = ["xlsx", "pdf"]


def _configure_logging() -> None:
    level_name = os.getenv("I4G_RUNTIME__LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _parse_datetime(value: str) -> datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = f"{cleaned[:-1]}+00:00"
    timestamp = datetime.fromisoformat(cleaned)
    if timestamp.tzinfo is None:
        return timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _BOOL_TRUE


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - invalid envs are handled by caller
        raise ValueError(f"{name} must be an integer") from exc


def _env_list(name: str) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return []
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _resolve_formats(settings: Settings) -> list[str]:
    formats = _env_list("I4G_ACCOUNT_JOB__OUTPUT_FORMATS")
    if formats:
        return formats
    if settings.account_list.default_formats:
        return [item.lower() for item in settings.account_list.default_formats if item]
    return list(_DEFAULT_FORMATS)


def _build_request_from_env(settings: Settings, *, now: datetime | None = None) -> AccountListRequest:
    reference = now or datetime.now(timezone.utc)

    start_env = os.getenv("I4G_ACCOUNT_JOB__START_TIME")
    end_env = os.getenv("I4G_ACCOUNT_JOB__END_TIME")
    window_days = _env_int("I4G_ACCOUNT_JOB__WINDOW_DAYS", 15)
    if window_days <= 0:
        raise ValueError("I4G_ACCOUNT_JOB__WINDOW_DAYS must be positive")

    end_time = _parse_datetime(end_env) if end_env else reference
    start_time = _parse_datetime(start_env) if start_env else end_time - timedelta(days=window_days)

    categories = _env_list("I4G_ACCOUNT_JOB__CATEGORIES")
    top_k_raw = _env_int("I4G_ACCOUNT_JOB__TOP_K", 200)
    top_k = min(top_k_raw, settings.account_list.max_top_k)
    include_sources = _env_bool("I4G_ACCOUNT_JOB__INCLUDE_SOURCES", True)
    output_formats = _resolve_formats(settings)

    return AccountListRequest(
        start_time=start_time,
        end_time=end_time,
        categories=categories,
        top_k=top_k,
        include_sources=include_sources,
        output_formats=output_formats,
    )


def _build_service() -> AccountListService:
    return AccountListService()


def _log_result_summary(result: AccountListResult) -> None:
    LOGGER.info(
        "Account list run %s completed: indicators=%s sources=%s",
        result.request_id,
        len(result.indicators),
        len(result.sources),
    )
    if result.artifacts:
        LOGGER.info("Artifacts generated: %s", result.artifacts)
    if result.warnings:
        LOGGER.warning("Warnings: %s", "; ".join(result.warnings))


def main() -> int:
    """Entry point executed by the Cloud Run job container."""

    _configure_logging()

    try:
        settings = get_settings()
    except Exception:
        LOGGER.exception("Unable to load settings for account job")
        return 1

    try:
        request = _build_request_from_env(settings)
    except ValueError as exc:
        LOGGER.error("Invalid account job configuration: %s", exc)
        return 1

    dry_run = _env_bool("I4G_ACCOUNT_JOB__DRY_RUN", False)
    LOGGER.info(
        "Starting account list job: top_k=%s window=%s→%s categories=%s formats=%s dry_run=%s",
        request.top_k,
        request.start_time,
        request.end_time,
        request.categories or ["bank", "crypto", "payments"],
        request.output_formats,
        dry_run,
    )

    if dry_run:
        LOGGER.info("Dry run enabled; skipping execution.")
        return 0

    service = _build_service()

    try:
        result = service.run(request)
    except Exception:
        LOGGER.exception("Account list extraction failed")
        return 1

    _log_result_summary(result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
