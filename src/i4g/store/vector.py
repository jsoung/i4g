"""
Local FAISS vector store management for document embeddings.
"""

from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document


def build_faiss_index(docs: List[Document], embedder) -> FAISS:
    """Create a FAISS index from LangChain Document objects."""
    return FAISS.from_documents(docs, embedder)


def save_index(store: FAISS, path: str = "faiss_index") -> None:
    """Persist FAISS index to disk."""
    store.save_local(path)


def load_index(path: str = "faiss_index", embedder=None) -> FAISS:
    """Load FAISS index from disk."""
    return FAISS.load_local(path, embedder, allow_dangerous_deserialization=True)
