"""Vector storage and retrieval for i4g.

This module provides a unified API for semantic embedding management.
Default backend: Chroma (persistent, simple to deploy).
Optional backend: FAISS (for large-scale or offline embedding search).

The design goal is to enable vector similarity search on scam case text,
supporting hybrid retrieval (structured + semantic) in later milestones.
"""

from __future__ import annotations

import os
from typing import List, Dict, Optional, Any
from uuid import uuid4
from dataclasses import asdict
import numpy as np
import json

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from i4g.store.schema import ScamRecord


DEFAULT_VECTOR_DIR = "data/chroma_store"
DEFAULT_MODEL_NAME = "nomic-embed-text"


class VectorStore:
    """Abstraction layer for vector storage and retrieval."""

    def __init__(
        self,
        persist_dir: str = DEFAULT_VECTOR_DIR,
        embedding_model: str = DEFAULT_MODEL_NAME,
    ) -> None:
        """Initialize the vector store.

        Args:
            persist_dir: Directory where the Chroma DB will persist data.
            embedding_model: Model name used for embedding generation.
        """
        os.makedirs(persist_dir, exist_ok=True)
        self.persist_dir = persist_dir
        self.embedding_model_name = embedding_model
        self.embeddings = OllamaEmbeddings(model=embedding_model)
        self.store = Chroma(
            collection_name="i4g_vectors",
            embedding_function=self.embeddings,
            persist_directory=persist_dir,
        )

    # ------------------------------------------------------------------
    # Core CRUD methods
    # ------------------------------------------------------------------

    def add_records(self, records: List[ScamRecord]) -> List[str]:
        """Add records and their embeddings to the vector store.

        Args:
            records: List of ScamRecord objects.

        Returns:
            List of record IDs added.
        """
        texts = [rec.text for rec in records]
        raw_metadatas = [rec.to_dict() for rec in records]
        
        sanitized_metadatas = []
        for meta in raw_metadatas:
            sanitized_meta = {
                k: json.dumps(v) if isinstance(v, (dict, list)) else v
                for k, v in meta.items()
            }
            sanitized_metadatas.append(sanitized_meta)

        ids = [rec.case_id or str(uuid4()) for rec in records]
        self.store.add_texts(texts=texts, metadatas=sanitized_metadatas, ids=ids)
        return ids

    def query_similar(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Perform semantic similarity search.

        Args:
            query_text: The input text or phrase to search for.
            top_k: Number of most similar results to return.

        Returns:
            List of dictionaries with `case_id`, `score`, and `metadata`.
        """
        results = self.store.similarity_search_with_score(query_text, k=top_k)
        formatted = []
        for doc, score in results:
            meta = doc.metadata or {}
            formatted.append(
                {
                    "case_id": meta.get("case_id", None),
                    "score": float(score),
                    "classification": meta.get("classification"),
                    "confidence": meta.get("confidence"),
                    "text": doc.page_content,
                }
            )
        return formatted

    def delete_record(self, case_id: str) -> bool:
        """Delete a record by ID from the vector store."""
        try:
            self.store.delete(ids=[case_id])
            return True
        except Exception:
            return False

    def list_collections(self) -> List[str]:
        """Return list of available vector collections."""
        try:
            return [self.store._collection.name]
        except Exception:
            return []

    def count(self) -> int:
        """Return the number of stored embeddings."""
        try:
            return self.store._collection.count()
        except Exception:
            return 0
