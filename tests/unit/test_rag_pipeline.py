from unittest.mock import MagicMock

from langchain_core.runnables import Runnable

from i4g.rag.pipeline import build_scam_detection_chain


class DummyDoc:
    def __init__(self, text):
        self.page_content = text


class MockLLM(Runnable):
    """Mock LLM that conforms to the Runnable interface."""

    def invoke(self, input, config=None):
        # LangChain's Runnable interface passes both input and config
        return "Likely a crypto scam."

    def __call__(self, input, config=None):
        # LangChain uses __call__ to invoke Runnables
        return self.invoke(input, config)


def test_scam_detection_chain_basic(monkeypatch):
    """Ensure pipeline composes correctly and produces an output string."""
    # Mock retriever to return dummy documents
    mock_vectorstore = MagicMock()
    mock_retriever = MagicMock()
    mock_vectorstore.as_retriever.return_value = mock_retriever

    def fake_retrieve(_query):
        return [DummyDoc("This looks like a crypto scam.")]

    # Patch retriever | lambda composition to simulate retrieval
    mock_retriever.__or__ = lambda self, fn: lambda _: fake_retrieve(None)
    mock_retriever.__ror__ = mock_retriever.__or__

    # Patch ChatOllama to use MockLLM
    monkeypatch.setattr("i4g.rag.pipeline.ChatOllama", lambda model="llama3.1": MockLLM())

    chain = build_scam_detection_chain(mock_vectorstore)
    response = chain.invoke({"question": "Is this message fraudulent?"})

    assert isinstance(response, str)
    assert "scam" in response.lower()
