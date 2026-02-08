"""
Search Service — Hybrid search (KNN + BM25) with RRF fusion

Provides search and context-formatting for LLM augmentation.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

from app.services.knowledge.embedding_service import get_embedding_service
from app.services.knowledge.storage_service import get_storage_service

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result."""
    text: str
    category: str
    score: float
    source_file: str


class SearchService:
    """Hybrid search over the knowledge store."""

    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.storage_service = get_storage_service()

    def search(
        self,
        query: str,
        limit: int = 10,
        categories: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Run hybrid search (dense KNN + sparse BM25 with RRF fusion).

        Args:
            query: Search query text
            limit: Max results to return
            categories: Optional list of categories to filter by

        Returns:
            List of SearchResult sorted by relevance
        """
        # Embed query
        dense_vector = self.embedding_service.embed_query_dense(query)
        sparse_vector = self.embedding_service.embed_query_sparse(query)

        # Search per category if multiple specified, otherwise single search
        all_results = []
        if categories:
            for cat in categories:
                scored = self.storage_service.hybrid_search(
                    dense_vector=dense_vector,
                    sparse_vector=sparse_vector,
                    limit=limit,
                    category_filter=cat,
                )
                all_results.extend(scored)
            # Re-sort by score and limit
            all_results.sort(key=lambda p: p.score, reverse=True)
            all_results = all_results[:limit]
        else:
            all_results = self.storage_service.hybrid_search(
                dense_vector=dense_vector,
                sparse_vector=sparse_vector,
                limit=limit,
            )

        return [
            SearchResult(
                text=p.payload.get("text", ""),
                category=p.payload.get("category", ""),
                score=p.score,
                source_file=p.payload.get("source_file", ""),
            )
            for p in all_results
        ]

    def search_for_context(self, query: str, limit: int = 5) -> str:
        """
        Search and format results as context for LLM injection.

        Groups results by category for cleaner context.
        Returns empty string if no results.
        """
        results = self.search(query, limit=limit)
        if not results:
            return ""

        # Group by category
        by_category = defaultdict(list)
        for r in results:
            by_category[r.category].append(r.text)

        # Format
        sections = []
        for category, texts in by_category.items():
            lines = [f"### {category}"]
            for text in texts:
                lines.append(f"- {text}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)


_instance = None


def get_search_service() -> SearchService:
    """Get or create the singleton SearchService."""
    global _instance
    if _instance is None:
        _instance = SearchService()
    return _instance
