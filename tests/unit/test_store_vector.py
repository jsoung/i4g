"""
Unit tests for i4g.store.vector and i4g.store.ingest.

These tests verify:
- VectorStore basic add/query/delete operations.
- IngestPipeline integration with StructuredStore and VectorStore.
- Embedding and Chroma components are mocked to avoid heavy dependencies.
"""

from unittest.mock import MagicMock, patch

import pytest

from i4g.store.ingest import IngestPipeline
from i4g.store.schema import ScamRecord
from i4g.store.structured import StructuredStore
from i4g.store.vector import VectorStore


@pytest.fixture
def mock_embeddings(monkeypatch):
    """Mock the OllamaEmbeddings class to avoid model calls."""
    MockEmbeddings = MagicMock()
    instance = MockEmbeddings.return_value
    instance.embed_query.return_value = [0.1, 0.2, 0.3]
    monkeypatch.setattr("i4g.store.vector.OllamaEmbeddings", MockEmbeddings)
    return instance


@pytest.fixture
def mock_chroma(monkeypatch):
    """Mock the Chroma vector store to avoid persistence."""
    MockChroma = MagicMock()
    store_instance = MockChroma.return_value
    store_instance.add_texts.return_value = ["mock-id"]
    store_instance.similarity_search_with_score.return_value = [
        (
            MagicMock(
                page_content="Fake doc",
                metadata={"case_id": "mock-id", "confidence": 0.9},
            ),
            0.05,
        )
    ]
    monkeypatch.setattr("i4g.store.vector.Chroma", MockChroma)
    return store_instance


@pytest.fixture
def mock_faiss(monkeypatch):
    """Mock the FAISS vector store backend."""
    store_instance = MagicMock()
    store_instance.similarity_search_with_score.return_value = []
    store_instance.delete.return_value = None
    store_instance.as_retriever.return_value = MagicMock()
    store_instance.save_local.return_value = None
    store_instance.index.ntotal = 0

    MockFAISS = MagicMock()
    MockFAISS.from_texts.return_value = store_instance
    MockFAISS.load_local.return_value = store_instance

    monkeypatch.setattr("i4g.store.vector.FAISS", MockFAISS)
    return MockFAISS


# ----------------------------------------------------------------------
# VectorStore tests
# ----------------------------------------------------------------------


def test_add_and_query_vectors(tmp_path, mock_embeddings, mock_chroma):
    """Ensure VectorStore can add and query without calling real models."""
    store = VectorStore(persist_dir=str(tmp_path), embedding_model="fake-model")

    rec = ScamRecord(
        case_id="mock-id",
        text="TrustWallet verification fee",
        entities={
            "organizations": ["TrustWallet"],
            "scam_indicators": ["verification fee"],
        },
        classification="crypto_investment",
        confidence=0.9,
    )

    ids = store.add_records([rec])
    assert ids == ["mock-id"]

    results = store.query_similar("TrustWallet")
    assert isinstance(results, list)
    assert results[0]["case_id"] == "mock-id"
    assert "score" in results[0]


def test_delete_record(mock_embeddings, mock_chroma, tmp_path):
    """Deleting a record should call the underlying vector store."""
    store = VectorStore(persist_dir=str(tmp_path), embedding_model="fake-model")
    success = store.delete_record("mock-id")
    assert success is True
    mock_chroma.delete.assert_called_once()


def test_faiss_backend_add_and_query(tmp_path, mock_embeddings, mock_faiss):
    """FAISS backend should initialize via from_texts and allow querying."""
    store = VectorStore(
        persist_dir=str(tmp_path / "faiss"),
        embedding_model="fake-model",
        backend="faiss",
    )

    ids = store.add_texts(["doc content"], metadatas=[{"source": "sample"}], ids=["case-1"])
    assert ids == ["case-1"]
    mock_faiss.from_texts.assert_called_once()

    store.query_similar("query text")
    mock_faiss.from_texts.return_value.similarity_search_with_score.assert_called_once()


# ----------------------------------------------------------------------
# IngestPipeline tests
# ----------------------------------------------------------------------


def test_ingest_pipeline_writes_to_both_stores(tmp_path, mock_embeddings, mock_chroma):
    """Ensure ingest pipeline writes to both structured and vector stores."""
    structured = StructuredStore(str(tmp_path / "test.db"))
    vector = VectorStore(persist_dir=str(tmp_path / "vec"), embedding_model="fake")

    pipeline = IngestPipeline(structured_store=structured, vector_store=vector)

    case = {
        "text": "Hi I'm Anna from TrustWallet. Send 50 USDT to verify.",
        "fraud_type": "crypto_investment",
        "fraud_confidence": 0.91,
        "entities": {"people": [{"value": "Anna"}]},
    }

    result = pipeline.ingest_classified_case(case)
    case_id = result.case_id
    assert isinstance(case_id, str)

    # Check record exists in structured store
    rec = structured.get_by_id(case_id)
    assert rec is not None
    assert rec.classification == "crypto_investment"

    # Check vector store add_texts called
    mock_chroma.add_texts.assert_called_once()


def test_query_similar_cases_returns_formatted(mock_embeddings, mock_chroma, tmp_path):
    """query_similar_cases() should return consistent structure."""
    pipeline = IngestPipeline()
    results = pipeline.query_similar_cases("TrustWallet", top_k=3)
    assert isinstance(results, list)
    assert "case_id" in results[0]
    assert "score" in results[0]
