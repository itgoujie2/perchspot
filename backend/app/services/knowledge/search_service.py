"""
Search Service — Hybrid search (KNN + BM25) with RRF fusion

Provides search and context-formatting for LLM augmentation.
Includes entity detection for proper noun queries (e.g., builder names).
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional

from app.services.knowledge.embedding_service import get_embedding_service
from app.services.knowledge.storage_service import get_storage_service

logger = logging.getLogger(__name__)

# Company/builder keywords that indicate entity queries
ENTITY_KEYWORDS = {
    'homes', 'builders', 'construction', 'inc', 'llc', 'corp', 'corporation',
    'group', 'properties', 'realty', 'estates', 'development', 'developments',
    'building', 'builders', 'company', 'co', 'associates', 'partners',
}


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

    def _is_likely_entity(self, query: str) -> bool:
        """
        Detect if query looks like a proper noun/entity.

        Heuristics:
        - Multiple capitalized words (e.g., "MN Custom Homes")
        - Contains company suffixes (Homes, Builders, Construction, Inc, LLC)
        - Single capitalized word that's not a common word
        """
        words = query.split()
        if not words:
            return False

        # Pattern: Multiple capitalized words (2+ words with capitals)
        if len(words) >= 2:
            capitalized = sum(1 for w in words if w and w[0].isupper())
            if capitalized >= 2:
                return True

        # Pattern: Contains company/builder keywords
        query_lower = query.lower()
        if any(kw in query_lower.split() for kw in ENTITY_KEYWORDS):
            return True

        return False

    def _text_contains_entity(self, text: str, entity: str) -> bool:
        """Check if text contains the entity (case-insensitive)."""
        return entity.lower() in text.lower()

    def _entity_search(
        self,
        query: str,
        limit: int,
        categories: Optional[List[str]],
    ) -> List[SearchResult]:
        """
        BM25-only search for entity queries, filtered to results containing the entity.

        Returns empty list if no matching results found (caller should fall back to hybrid).
        """
        sparse_vector = self.embedding_service.embed_query_sparse(query)

        # Run BM25-only search
        if categories:
            bm25_results = []
            for cat in categories:
                scored = self.storage_service.sparse_search(
                    sparse_vector=sparse_vector,
                    limit=limit * 2,  # Over-fetch for filtering
                    category_filter=cat,
                )
                bm25_results.extend(scored)
            bm25_results.sort(key=lambda p: p.score, reverse=True)
        else:
            bm25_results = self.storage_service.sparse_search(
                sparse_vector=sparse_vector,
                limit=limit * 2,
            )

        # Filter to results that actually contain the entity text
        filtered = [
            p for p in bm25_results
            if self._text_contains_entity(p.payload.get("text", ""), query)
        ]

        logger.info(
            f"Entity search for '{query}': "
            f"BM25 returned {len(bm25_results)}, filtered to {len(filtered)}"
        )

        return [
            SearchResult(
                text=p.payload.get("text", ""),
                category=p.payload.get("category", ""),
                score=p.score,
                source_file=p.payload.get("source_file", ""),
            )
            for p in filtered[:limit]
        ]

    def search(
        self,
        query: str,
        limit: int = 10,
        categories: Optional[List[str]] = None,
    ) -> List[SearchResult]:
        """
        Run search with entity boost for proper nouns.

        For entity queries (e.g., "MN Custom Homes"):
        1. Try BM25-only search first
        2. Filter to results containing the entity text
        3. Fall back to hybrid search if no matches

        For non-entity queries: Use hybrid search (dense KNN + sparse BM25 with RRF).

        Args:
            query: Search query text
            limit: Max results to return
            categories: Optional list of categories to filter by

        Returns:
            List of SearchResult sorted by relevance
        """
        is_entity = self._is_likely_entity(query)
        logger.info(f"Query '{query}' detected as entity: {is_entity}")

        # For entity queries, try BM25-only search first
        if is_entity:
            entity_results = self._entity_search(query, limit, categories)
            if entity_results:
                return entity_results
            logger.info(f"No entity matches for '{query}', falling back to hybrid search")

        # Fall back to hybrid search
        return self._hybrid_search(query, limit, categories)

    def _hybrid_search(
        self,
        query: str,
        limit: int,
        categories: Optional[List[str]],
    ) -> List[SearchResult]:
        """
        Original hybrid search (dense KNN + sparse BM25 with RRF fusion).
        """
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
