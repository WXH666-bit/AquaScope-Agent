"""Lightweight semantic retriever using all-MiniLM-L6-v2 embeddings.

Provides an alternative to TF-IDF for model improvement comparison.
Model size: ~80 MB, no GPU required.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from .vector_store import LocalVectorStore, load_source_records, record_text

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
CACHE_DIR = str(Path(__file__).resolve().parents[3] / "data" / "model_cache")


class SemanticRetriever:
    """Encode queries and documents with MiniLM, score by cosine similarity."""

    def __init__(
        self,
        knowledge_dir: str | Path = "data/knowledge",
        index_dir: str | Path = "data/index",
        vector_db_dir: str | Path | None = None,
    ):
        if vector_db_dir is None:
            vector_db_dir = Path(knowledge_dir).parent / "vector_db"
        store = LocalVectorStore(vector_db_dir)
        if store.exists:
            store.load()
            self.records = store.records
            self.texts = store.texts
        else:
            self.records = load_source_records(knowledge_dir, index_dir)
            self.texts = [record_text(r) for r in self.records]
        self._model: SentenceTransformer | None = None
        self._embeddings: np.ndarray | None = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            print("Loading MiniLM embedding model (~80 MB)...", file=sys.stderr, flush=True)
            self._model = SentenceTransformer(
                MODEL_NAME,
                cache_folder=CACHE_DIR,
            )
        return self._model

    @property
    def embeddings(self) -> np.ndarray:
        if self._embeddings is None:
            print(
                f"Encoding {len(self.texts)} documents...",
                file=sys.stderr,
                flush=True,
            )
            self._embeddings = self.model.encode(
                self.texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=True,
            )
        return self._embeddings

    def search(self, query: str, top_k: int = 7) -> list[dict]:
        if not self.records:
            return []
        query_vec = self.model.encode(
            [query], normalize_embeddings=True
        )[0]
        scores = (self.embeddings @ query_vec).ravel()
        ranked = np.argsort(-scores)
        results = []
        for idx in ranked:
            if scores[idx] <= 0:
                break
            item = dict(self.records[int(idx)])
            item["score"] = round(float(scores[idx]), 4)
            results.append(item)
            if len(results) >= top_k:
                break
        return results
