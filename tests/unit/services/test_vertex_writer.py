"""Tests for the Vertex document writer."""

from __future__ import annotations

from types import SimpleNamespace

from google.cloud import discoveryengine_v1beta as discoveryengine

from i4g.services.vertex_writer import VertexDocumentWriter, VertexWriterError


class _FakeOperation:
    def __init__(self) -> None:
        self.timeout = None
        self.response = SimpleNamespace(error_samples=[])

    def result(self, timeout: int | None = None):
        self.timeout = timeout
        return self.response


class _FakeClient:
    def __init__(self) -> None:
        self.requests = []

    def branch_path(self, project: str, location: str, data_store: str, branch: str) -> str:
        return f"projects/{project}/locations/{location}/collections/default_collection/dataStores/{data_store}/branches/{branch}"

    def import_documents(self, request: discoveryengine.ImportDocumentsRequest) -> _FakeOperation:
        self.requests.append(request)
        return _FakeOperation()


def test_vertex_writer_upserts_document():
    client = _FakeClient()
    writer = VertexDocumentWriter(
        project="proj",
        location="global",
        data_store_id="store",
        branch="default_branch",
        default_dataset="demo",
        timeout_seconds=5,
        client=client,
    )

    result = writer.upsert_record({"case_id": "case-123", "text": "hello"})

    assert result.document_id == "case-123"
    assert result.warnings == []
    assert len(client.requests) == 1
    inline_docs = client.requests[0].inline_source.documents
    assert len(inline_docs) == 1
    assert inline_docs[0].id == "case-123"


def test_vertex_writer_raises_on_failed_import(monkeypatch):
    class _FailingClient(_FakeClient):
        def import_documents(self, request):  # type: ignore[override]
            raise RuntimeError("boom")

    writer = VertexDocumentWriter(
        project="proj",
        location="global",
        data_store_id="store",
        client=_FailingClient(),
    )

    try:
        writer.upsert_record({"case_id": "case-err", "text": "body"})
    except VertexWriterError as exc:
        assert "case-err" in str(exc)
    else:  # pragma: no cover - defensive guard
        raise AssertionError("VertexWriterError was not raised")
