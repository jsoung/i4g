"""Shared helpers to normalise ingestion payloads across jobs."""

from __future__ import annotations

from typing import Any, Dict, Tuple


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive cast for unexpected types
        return default


def _extract_text(record: Dict[str, Any], metadata: Dict[str, Any]) -> Tuple[str, str]:
    raw_text = record.get("text")
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text.strip(), "record.text"

    sections = []
    for key in ("summary", "details", "description", "body"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            sections.append(value.strip())

    metadata_text = metadata.get("text")
    if isinstance(metadata_text, str) and metadata_text.strip():
        sections.append(metadata_text.strip())

    text = "\n\n".join(sections)
    return text, "derived" if text else "none"


def _extract_entities(record: Dict[str, Any], metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    entities = record.get("entities")
    if isinstance(entities, dict):
        return entities, "record.entities"

    entities = metadata.get("entities")
    if isinstance(entities, dict):
        return entities, "metadata.entities"

    return {}, "none"


def prepare_ingest_payload(record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build a classification payload compatible with ``IngestPipeline``.

    Returns a tuple of (payload, diagnostics). The diagnostics field surfaces the
    derived classification and confidence values together with source metadata
    that downstream callers can use for logging or job status updates.
    """

    metadata = _as_dict(record.get("metadata"))

    classification = (
        record.get("fraud_type")
        or record.get("classification")
        or metadata.get("classification")
        or metadata.get("suspected_classification")
        or "unclassified"
    )

    confidence = _coerce_float(
        record.get("fraud_confidence")
        or record.get("confidence")
        or metadata.get("fraud_confidence")
        or metadata.get("classification_confidence")
        or metadata.get("confidence")
        or 0.0
    )

    text, text_source = _extract_text(record, metadata)
    entities, entities_source = _extract_entities(record, metadata)

    reasons = record.get("reasons")
    if reasons is None:
        reasons = metadata.get("reasons")

    explanation = record.get("explanation")
    if explanation is None:
        explanation = metadata.get("explanation")

    payload: Dict[str, Any] = {
        "case_id": record.get("case_id") or record.get("intake_id") or record.get("id"),
        "text": text,
        "fraud_type": classification,
        "fraud_confidence": confidence,
        "entities": entities,
        "reasons": reasons,
        "explanation": explanation,
    }

    diagnostics = {
        "classification": classification,
        "confidence": confidence,
        "text_source": text_source,
        "entities_source": entities_source,
    }

    return payload, diagnostics


__all__ = ["prepare_ingest_payload"]
