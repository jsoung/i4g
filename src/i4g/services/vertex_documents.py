"""Helpers to build Vertex AI Search documents from ingestion payloads."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

try:  # pragma: no cover - import guard for optional dependency
    from google.cloud import discoveryengine_v1beta as discoveryengine
except ImportError:  # pragma: no cover
    discoveryengine = None  # type: ignore[assignment]


class VertexDocumentBuilderError(RuntimeError):
    """Raised when a Vertex document cannot be constructed."""


def build_vertex_document(
    record: Dict[str, Any], *, default_dataset: Optional[str] = None
) -> "discoveryengine.Document":
    """Convert a normalized ingestion payload into a Vertex document."""

    if discoveryengine is None:  # pragma: no cover - dependency guard
        raise VertexDocumentBuilderError(
            "google-cloud-discoveryengine is not installed. Install it to enable Vertex fan-out.",
        )

    struct_payload = dict(record)
    case_id = struct_payload.get("case_id")
    if not case_id:
        raise VertexDocumentBuilderError("Vertex documents require a case_id field.")

    dataset = struct_payload.get("dataset") or default_dataset or "unknown"
    struct_payload["dataset"] = dataset

    text = struct_payload.get("text", "") or ""
    struct_payload.setdefault("content", text)

    document = discoveryengine.Document()
    document.id = str(case_id)
    document.struct_data = struct_payload
    document.content = discoveryengine.Document.Content(
        raw_bytes=text.encode("utf-8"),
        mime_type="text/plain",
    )
    document.json_data = json.dumps(struct_payload, ensure_ascii=False)
    return document


__all__ = ["VertexDocumentBuilderError", "build_vertex_document"]
