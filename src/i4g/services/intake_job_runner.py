"""Helpers to execute intake ingestion jobs."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, Protocol

from i4g.services.ingest_payloads import prepare_ingest_payload
from i4g.store.ingest import IngestPipeline


@dataclass
class IntakeJobResult:
    """Result returned by an intake job runner."""

    case_id: str
    message: str = "Ingestion completed"
    metadata: Dict[str, Any] = field(default_factory=dict)


class IntakeJobRunner(Protocol):
    """Protocol describing how to execute an intake ingestion job."""

    name: str

    def run(self, intake: Dict[str, Any]) -> IntakeJobResult:  # pragma: no cover - Protocol
        ...


def _coerce_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


class LocalPipelineIntakeJobRunner:
    """Run intake ingestion by invoking the local IngestPipeline directly."""

    name = "local_pipeline"

    def __init__(
        self,
        *,
        pipeline_factory: type[IngestPipeline] | None = None,
        enable_vector: bool | None = None,
    ) -> None:
        self._pipeline_factory = pipeline_factory or IngestPipeline
        env_override = _coerce_bool(os.getenv("I4G_INGEST__ENABLE_VECTOR"))
        self._enable_vector = enable_vector if enable_vector is not None else env_override

    def run(self, intake: Dict[str, Any]) -> IntakeJobResult:
        kwargs: Dict[str, Any] = {}
        if self._enable_vector is not None:
            kwargs["enable_vector"] = self._enable_vector

        pipeline = self._pipeline_factory(**kwargs)

        payload, diagnostics = prepare_ingest_payload(intake)

        ingest_result = pipeline.ingest_classified_case(payload)
        result_metadata = {
            "classification": diagnostics["classification"],
            "confidence": diagnostics["confidence"],
            "text_source": diagnostics["text_source"],
            "entities_source": diagnostics["entities_source"],
            "runner": self.name,
        }
        return IntakeJobResult(case_id=ingest_result.case_id, metadata=result_metadata)


__all__ = ["IntakeJobResult", "IntakeJobRunner", "LocalPipelineIntakeJobRunner"]
