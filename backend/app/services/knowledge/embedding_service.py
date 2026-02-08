"""
Embedding Service — Dense (Qwen3) + Sparse (BM25) embeddings

Lazy-loads models on first use. Thread-safe singleton.
"""
import logging
import threading
from typing import List

from qdrant_client.models import SparseVector

from app.config import settings

logger = logging.getLogger(__name__)

_instance = None
_lock = threading.Lock()


class EmbeddingService:
    """Generates dense and sparse embeddings for text."""

    def __init__(self):
        self._dense_model = None
        self._sparse_model = None
        self._dense_lock = threading.Lock()
        self._sparse_lock = threading.Lock()

    def _load_dense_model(self):
        """Lazy-load Qwen3-Embedding-0.6B via sentence-transformers."""
        if self._dense_model is None:
            with self._dense_lock:
                if self._dense_model is None:
                    from sentence_transformers import SentenceTransformer
                    logger.info(f"Loading dense model: {settings.EMBEDDING_MODEL}")
                    self._dense_model = SentenceTransformer(
                        settings.EMBEDDING_MODEL,
                        trust_remote_code=True,
                    )
                    logger.info("Dense model loaded")

    def _load_sparse_model(self):
        """Lazy-load FastEmbed BM25 sparse model."""
        if self._sparse_model is None:
            with self._sparse_lock:
                if self._sparse_model is None:
                    from fastembed import SparseTextEmbedding
                    logger.info("Loading sparse BM25 model: Qdrant/bm25")
                    self._sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
                    logger.info("Sparse BM25 model loaded")

    def embed_dense(self, texts: List[str]) -> List[List[float]]:
        """Generate dense embeddings for a list of texts (passage mode)."""
        self._load_dense_model()
        embeddings = self._dense_model.encode(texts, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]

    def embed_query_dense(self, query: str) -> List[float]:
        """Generate dense embedding for a query (query mode with instruction)."""
        self._load_dense_model()
        embedding = self._dense_model.encode(
            [query],
            prompt_name="query",
            show_progress_bar=False,
        )
        return embedding[0].tolist()

    def embed_sparse(self, texts: List[str]) -> List[SparseVector]:
        """Generate sparse BM25 vectors for a list of texts."""
        self._load_sparse_model()
        results = list(self._sparse_model.embed(texts))
        return [
            SparseVector(
                indices=emb.indices.tolist(),
                values=emb.values.tolist(),
            )
            for emb in results
        ]

    def embed_query_sparse(self, query: str) -> SparseVector:
        """Generate sparse BM25 vector for a query."""
        self._load_sparse_model()
        results = list(self._sparse_model.query_embed(query))
        emb = results[0]
        return SparseVector(
            indices=emb.indices.tolist(),
            values=emb.values.tolist(),
        )


def get_embedding_service() -> EmbeddingService:
    """Get or create the singleton EmbeddingService."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = EmbeddingService()
    return _instance
