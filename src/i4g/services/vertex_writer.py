"""Vertex AI Search writer used by the ingestion pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from google.cloud import discoveryengine_v1beta as discoveryengine
from google.protobuf import json_format

from i4g.services.vertex_documents import VertexDocumentBuilderError, build_vertex_document

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class VertexWriteResult:
    """Summary of a Vertex document upsert."""

    document_id: str
    warnings: List[str] = field(default_factory=list)


class VertexWriterError(RuntimeError):
    """Raised when Vertex ingestion fails despite retries."""


class VertexDocumentWriter:
    """Wraps the DocumentService client with simple upsert helpers."""

    def __init__(
        self,
        *,
        project: str,
        location: str,
        data_store_id: str,
        branch: str = "default_branch",
        default_dataset: Optional[str] = None,
        timeout_seconds: int = 60,
        client: Optional[discoveryengine.DocumentServiceClient] = None,
    ) -> None:
        if not project or not data_store_id:
            raise ValueError("VertexDocumentWriter requires both project and data_store_id")

        self._client = client or discoveryengine.DocumentServiceClient()
        self._parent = self._client.branch_path(
            project=project,
            location=location,
            data_store=data_store_id,
            branch=branch,
        )
        self._timeout = max(timeout_seconds, 1)
        self._default_dataset = default_dataset
        self._reconcile_mode = discoveryengine.ImportDocumentsRequest.ReconciliationMode.INCREMENTAL

    def upsert_record(self, record: Dict[str, Any]) -> VertexWriteResult:
        """Persist a single record to Vertex AI Search via import_documents."""

        try:
            document = build_vertex_document(record, default_dataset=self._default_dataset)
        except VertexDocumentBuilderError as exc:  # pragma: no cover - builder already logged
            raise VertexWriterError(str(exc)) from exc

        request = discoveryengine.ImportDocumentsRequest(
            parent=self._parent,
            inline_source=discoveryengine.ImportDocumentsRequest.InlineSource(documents=[document]),
            reconciliation_mode=self._reconcile_mode,
        )

        try:
            operation = self._client.import_documents(request=request)
            response = operation.result(timeout=self._timeout)
        except Exception as exc:  # pragma: no cover - network/backend failure
            raise VertexWriterError(f"Vertex import failed for document_id={document.id}: {exc}") from exc

        warnings: List[str] = []
        for sample in getattr(response, "error_samples", [])[:3]:
            try:
                warnings.append(json_format.MessageToJson(sample))
            except Exception:
                warnings.append(str(sample))

        if warnings:
            LOGGER.warning("Vertex import completed with warnings for document_id=%s", document.id)

        return VertexWriteResult(document_id=document.id, warnings=warnings)


__all__ = ["VertexDocumentWriter", "VertexWriteResult", "VertexWriterError"]
