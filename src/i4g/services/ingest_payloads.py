"""Shared helpers to normalise ingestion payloads across jobs."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):  # pragma: no cover - defensive cast for unexpected types
        return default


def _normalise_string_list(value: Any) -> List[str]:
    result: List[str] = []
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            result.append(stripped)
        return result
    if isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    result.append(stripped)
    return result


def _normalise_indicator_ids(value: Any) -> List[str]:
    result: List[str] = []

    def _append(candidate: str | None) -> None:
        if candidate:
            stripped = candidate.strip()
            if stripped:
                result.append(stripped)

    if isinstance(value, str):
        _append(value)
        return result

    if isinstance(value, (list, tuple, set)):
        for item in value:
            if isinstance(item, str):
                _append(item)
            elif isinstance(item, dict):
                _append(item.get("indicator_id") or item.get("id") or item.get("value") or item.get("number"))
    elif isinstance(value, dict):
        _append(value.get("indicator_id") or value.get("id") or value.get("value") or value.get("number"))

    return result


def _extract_summary(record: Dict[str, Any], metadata: Dict[str, Any]) -> str | None:
    summary = record.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    meta_summary = metadata.get("summary")
    if isinstance(meta_summary, str) and meta_summary.strip():
        return meta_summary.strip()
    return None


def _extract_tags(record: Dict[str, Any], metadata: Dict[str, Any]) -> List[str]:
    for candidate in (record.get("tags"), metadata.get("tags")):
        tags = _normalise_string_list(candidate)
        if tags:
            return tags
    return []


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


def _extract_categories(record: Dict[str, Any], metadata: Dict[str, Any]) -> List[str]:
    for candidate in (record.get("categories"), record.get("category"), metadata.get("categories")):
        categories = _normalise_string_list(candidate)
        if categories:
            return categories

    tags = _normalise_string_list(record.get("tags") or metadata.get("tags"))
    return tags


def _extract_indicator_ids(record: Dict[str, Any], metadata: Dict[str, Any]) -> List[str]:
    for candidate in (
        record.get("indicator_ids"),
        metadata.get("indicator_ids"),
        metadata.get("indicators"),
    ):
        indicator_ids = _normalise_indicator_ids(candidate)
        if indicator_ids:
            return indicator_ids
    return []


def prepare_ingest_payload(
    record: Dict[str, Any],
    *,
    default_dataset: str | None = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
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

    dataset = record.get("dataset") or metadata.get("dataset") or default_dataset
    categories = _extract_categories(record, metadata)
    indicator_ids = _extract_indicator_ids(record, metadata)
    summary = _extract_summary(record, metadata)
    tags = _extract_tags(record, metadata)
    structured_fields = record.get("structured_fields") or metadata.get("structured_fields")
    channel = record.get("channel") or metadata.get("channel")
    timestamp = record.get("timestamp") or metadata.get("timestamp")
    risk_level = record.get("risk_level") or metadata.get("risk_level")
    language = record.get("language") or metadata.get("language")
    label = record.get("ground_truth_label") or metadata.get("ground_truth_label")
    source_type = record.get("source_type") or metadata.get("source_type")
    document_id = record.get("document_id") or metadata.get("document_id")
    document_title = record.get("document_title") or metadata.get("document_title")
    source_url = record.get("source_url") or metadata.get("source_url")

    payload: Dict[str, Any] = {
        "case_id": record.get("case_id") or record.get("intake_id") or record.get("id"),
        "text": text,
        "fraud_type": classification,
        "fraud_confidence": confidence,
        "entities": entities,
        "reasons": reasons,
        "explanation": explanation,
    }

    if dataset:
        payload["dataset"] = dataset
    if categories:
        payload["categories"] = categories
        payload.setdefault("category", categories[0])
    if indicator_ids:
        payload["indicator_ids"] = indicator_ids
    if summary:
        payload["summary"] = summary
    if channel:
        payload["channel"] = channel
    if timestamp:
        payload["timestamp"] = timestamp
    if tags:
        payload["tags"] = tags
    if structured_fields:
        payload["structured_fields"] = structured_fields
    if metadata:
        payload["metadata"] = metadata
    if risk_level:
        payload["risk_level"] = risk_level
    if language:
        payload["language"] = language
    if label:
        payload["ground_truth_label"] = label
    if source_type:
        payload["source_type"] = source_type
    if document_id:
        payload["document_id"] = document_id
    if document_title:
        payload["document_title"] = document_title
    if source_url:
        payload["source_url"] = source_url

    diagnostics = {
        "classification": classification,
        "confidence": confidence,
        "text_source": text_source,
        "entities_source": entities_source,
    }

    return payload, diagnostics


__all__ = ["prepare_ingest_payload"]
