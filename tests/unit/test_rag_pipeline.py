"""
Unit test for the RAG pipeline (i4g/rag/pipeline.py).
This test ensures the QA chain is built correctly and the right model + prompt are used.
"""

import pytest
from unittest.mock import patch, MagicMock

import i4g.rag.pipeline as pipeline


@patch("i4g.rag.pipeline.ChatOllama")
@patch("i4g.rag.pipeline.RetrievalQA")
def test_build_qa_chain(mock_retrievalqa, mock_chatollama):
    # Mock the LLM and retriever behavior
    mock_llm = MagicMock()
    mock_chatollama.return_value = mock_llm

    mock_chain = MagicMock()
    mock_retrievalqa.from_chain_type.return_value = mock_chain

    mock_vectorstore = MagicMock()
    mock_retriever = MagicMock()
    mock_vectorstore.as_retriever.return_value = mock_retriever

    # Call the function under test
    result = pipeline.build_qa_chain(mock_vectorstore)

    # --- Assertions ---
    # 1️⃣ Should return the mocked chain object
    assert result == mock_chain

    # 2️⃣ Should instantiate ChatOllama with correct model
    mock_chatollama.assert_called_once_with(model="llama3.1")

    # 3️⃣ Should call RetrievalQA.from_chain_type with expected args
    mock_retrievalqa.from_chain_type.assert_called_once()
    args, kwargs = mock_retrievalqa.from_chain_type.call_args

    assert kwargs["llm"] == mock_llm
    assert kwargs["chain_type"] == "stuff"
    assert kwargs["retriever"] == mock_retriever
    assert "prompt" in kwargs["chain_type_kwargs"]

    # 4️⃣ Verify that the prompt includes the correct intent
    prompt = kwargs["chain_type_kwargs"]["prompt"]
    assert "scam detection assistant" in prompt.template.lower()
    assert "crypto and romance scams" in prompt.template.lower()
