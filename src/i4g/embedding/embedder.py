"""
Embedding generation using Ollama local embedding models.
"""

from typing import List

from langchain_ollama import OllamaEmbeddings


def get_embedder(model_name: str = "mxbai-embed-large") -> OllamaEmbeddings:
    """Return an Ollama embedding instance."""
    return OllamaEmbeddings(model=model_name)


def embed_documents(embedder, texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of text chunks."""
    return embedder.embed_documents(texts)
