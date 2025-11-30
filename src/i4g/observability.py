"""Observability helpers for structured logging and lightweight metrics."""

from __future__ import annotations

import json
import logging
import socket
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, MutableMapping

from i4g.settings import Settings, get_settings

try:  # pragma: no cover - optional dependency wiring is environment specific
    from opentelemetry import metrics as otel_metrics  # type: ignore
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
except Exception:  # pragma: no cover - gracefully handle missing OTLP dependencies
    otel_metrics = None
    OTLPMetricExporter = None  # type: ignore
    MeterProvider = None  # type: ignore
    PeriodicExportingMetricReader = None  # type: ignore


_LOGGER = logging.getLogger("i4g.observability")
_METRICS_BACKEND_LOCK = threading.Lock()
_SHARED_METRICS: "_CompositeMetricsBackend | None" = None


class Observability:
    """Emit structured logs and StatsD/OTel-compatible metrics."""

    def __init__(
        self,
        *,
        settings: Settings,
        component: str | None = None,
        metrics_backend: "_CompositeMetricsBackend | None" = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.component = component or "core"
        self._logger = logger or _LOGGER
        self._structured_logging = bool(settings.observability.structured_logging)
        self._metrics = metrics_backend

    def emit_event(self, event: str, **fields: Any) -> None:
        """Emit a structured log if enabled."""

        payload = {
            "event": event,
            "component": self.component,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **_sanitize_dict(fields),
        }
        if self._structured_logging:
            message = json.dumps(payload, default=_serialize)
            self._logger.info(message)
        else:
            self._logger.info("%s | %s", event, payload)

    def increment(self, metric: str, *, value: float = 1.0, tags: Mapping[str, str] | None = None) -> None:
        """Increment a counter-style metric."""

        if not self._metrics:
            return
        self._metrics.increment(metric, value=value, tags=_normalize_tags(tags))

    def record_timing(self, metric: str, value_ms: float, *, tags: Mapping[str, str] | None = None) -> None:
        """Record a timing metric in milliseconds."""

        if not self._metrics:
            return
        self._metrics.record_timing(metric, value_ms=value_ms, tags=_normalize_tags(tags))


def get_observability(*, component: str | None = None, settings: Settings | None = None) -> Observability:
    """Return an :class:`Observability` instance for the requested component."""

    resolved = settings or get_settings()
    backend = _build_shared_metrics_backend(resolved)
    return Observability(settings=resolved, component=component, metrics_backend=backend, logger=_LOGGER)


def reset_observability_cache() -> None:
    """Reset cached metrics backends (used in tests)."""

    global _SHARED_METRICS
    with _METRICS_BACKEND_LOCK:
        _SHARED_METRICS = None


# ---------------------------------------------------------------------------
# Metrics backends
# ---------------------------------------------------------------------------


class _CompositeMetricsBackend:
    """Dispatch metrics to every configured backend."""

    def __init__(self, backends: Iterable["_MetricsBackend"]) -> None:
        self.backends = tuple(backends)

    def increment(self, metric: str, *, value: float, tags: Mapping[str, str] | None) -> None:
        for backend in self.backends:
            backend.increment(metric, value=value, tags=tags)

    def record_timing(self, metric: str, *, value_ms: float, tags: Mapping[str, str] | None) -> None:
        for backend in self.backends:
            backend.record_timing(metric, value_ms=value_ms, tags=tags)


class _MetricsBackend:
    """Interface for metrics backends."""

    def increment(
        self, metric: str, *, value: float, tags: Mapping[str, str] | None
    ) -> None:  # pragma: no cover - interface only
        raise NotImplementedError

    def record_timing(
        self, metric: str, *, value_ms: float, tags: Mapping[str, str] | None
    ) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


@dataclass(slots=True)
class _StatsdBackend(_MetricsBackend):
    """Minimal StatsD client using UDP sockets."""

    host: str
    port: int
    prefix: str

    def __post_init__(self) -> None:
        self._address = (self.host, self.port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def increment(self, metric: str, *, value: float, tags: Mapping[str, str] | None) -> None:
        self._send(metric, value, metric_type="c", tags=tags)

    def record_timing(self, metric: str, *, value_ms: float, tags: Mapping[str, str] | None) -> None:
        self._send(metric, value_ms, metric_type="ms", tags=tags)

    def _send(self, metric: str, value: float, *, metric_type: str, tags: Mapping[str, str] | None) -> None:
        scoped = f"{self.prefix}.{metric}" if self.prefix else metric
        payload = f"{scoped}:{_format_number(value)}|{metric_type}"
        if tags:
            tag_block = ",".join(f"{key}:{val}" for key, val in sorted(tags.items()))
            if tag_block:
                payload = f"{payload}|#{tag_block}"
        try:
            self._socket.sendto(payload.encode("utf-8"), self._address)
        except OSError:  # pragma: no cover - network errors are logged in structured logs
            _LOGGER.debug("StatsD send failed for metric %s", metric, exc_info=True)


class _OtelMetricsBackend(_MetricsBackend):
    """OpenTelemetry metrics exporter hooked to OTLP."""

    def __init__(self, *, endpoint: str, service_name: str) -> None:
        self._supported = bool(otel_metrics and OTLPMetricExporter and MeterProvider)
        self._counters: MutableMapping[str, Any] = {}
        self._histograms: MutableMapping[str, Any] = {}
        self._meter = None
        if not self._supported:
            return
        self._meter = self._build_meter(endpoint=endpoint, service_name=service_name)

    def increment(self, metric: str, *, value: float, tags: Mapping[str, str] | None) -> None:
        if not self._meter:
            return
        instrument = self._counters.get(metric)
        if instrument is None:
            instrument = self._meter.create_counter(metric)
            self._counters[metric] = instrument
        instrument.add(value, attributes=dict(tags or {}))

    def record_timing(self, metric: str, *, value_ms: float, tags: Mapping[str, str] | None) -> None:
        if not self._meter:
            return
        instrument = self._histograms.get(metric)
        if instrument is None:
            instrument = self._meter.create_histogram(metric)
            self._histograms[metric] = instrument
        instrument.record(value_ms, attributes=dict(tags or {}))

    def _build_meter(self, *, endpoint: str, service_name: str) -> Any:  # type: ignore[override]
        if not (
            OTLPMetricExporter and MeterProvider and PeriodicExportingMetricReader and otel_metrics
        ):  # pragma: no cover - guard for missing libs
            return None
        insecure = endpoint.startswith("http://")
        exporter = OTLPMetricExporter(endpoint=endpoint, insecure=insecure)
        reader = PeriodicExportingMetricReader(exporter)
        provider = MeterProvider(metric_readers=[reader])
        otel_metrics.set_meter_provider(provider)
        return otel_metrics.get_meter(service_name or "i4g")


def _build_shared_metrics_backend(settings: Settings) -> _CompositeMetricsBackend | None:
    global _SHARED_METRICS
    with _METRICS_BACKEND_LOCK:
        if _SHARED_METRICS is not None:
            return _SHARED_METRICS
        backends: list[_MetricsBackend] = []
        statsd_host = settings.observability.statsd_host
        if statsd_host:
            backends.append(
                _StatsdBackend(
                    host=statsd_host,
                    port=settings.observability.statsd_port,
                    prefix=settings.observability.statsd_prefix,
                )
            )
        otlp_endpoint = settings.observability.otlp_endpoint
        if otlp_endpoint:
            backends.append(
                _OtelMetricsBackend(
                    endpoint=otlp_endpoint,
                    service_name=settings.observability.service_name,
                )
            )
        if not backends:
            _SHARED_METRICS = None
            return None
        _SHARED_METRICS = _CompositeMetricsBackend(backends)
        return _SHARED_METRICS


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_serialize(item) for item in value)
    if isinstance(value, dict):
        return {str(key): _serialize(val) for key, val in value.items()}
    return str(value)


def _normalize_tags(tags: Mapping[str, str] | None) -> Mapping[str, str] | None:
    if not tags:
        return None
    normalized: dict[str, str] = {}
    for key, value in tags.items():
        if value is None:
            continue
        normalized[str(key)] = str(value)
    return normalized or None


def _format_number(value: float) -> str:
    formatted = f"{value:.6f}"
    formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


def _sanitize_dict(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, Mapping):
            sanitized[str(key)] = _sanitize_dict(value)
        else:
            sanitized[str(key)] = value
    return sanitized


__all__ = ["Observability", "get_observability", "reset_observability_cache"]
