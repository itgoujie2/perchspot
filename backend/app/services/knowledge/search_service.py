"""
Search Service — Hybrid search (KNN + BM25) with RRF fusion

Provides search and context-formatting for LLM augmentation.
Includes entity detection for proper noun queries (e.g., builder names).
Supports attribute-based search for property-specific knowledge.
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

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
    priority: str = "medium"  # high, medium, low
    applies_when: List[Dict[str, Any]] = None  # List of condition dicts


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
                priority=p.payload.get("priority", "medium"),
                applies_when=p.payload.get("applies_when", []),
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
                priority=p.payload.get("priority", "medium"),
                applies_when=p.payload.get("applies_when", []),
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

    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        property_data: Dict[str, Any]
    ) -> bool:
        """
        Evaluate a single @applies_when condition against property data.

        Condition format: {"attribute": "year_built", "operator": "<", "value": 1990}

        Supported attributes (with their data paths):
            - year_built: details.year_built
            - has_hoa: hoa.has_hoa
            - hoa_fee: hoa.fee
            - property_type: details.property_type
            - lot_size_sqft: details.lot_size_sqft
            - living_area_sqft: details.living_area_sqft
            - bedrooms: details.bedrooms
            - bathrooms: details.bathrooms
            - stories: details.stories
        """
        # Validate condition is a dict
        if not isinstance(condition, dict):
            return False

        attribute = condition.get("attribute", "")
        operator = condition.get("operator", "=")
        target_value = condition.get("value")

        # Map attributes to their data paths
        attribute_paths = {
            "year_built": ("details", "year_built"),
            "has_hoa": ("hoa", "has_hoa"),
            "hoa_fee": ("hoa", "fee"),
            "property_type": ("details", "property_type"),
            "lot_size_sqft": ("details", "lot_size_sqft"),
            "living_area_sqft": ("details", "living_area_sqft"),
            "bedrooms": ("details", "bedrooms"),
            "bathrooms": ("details", "bathrooms"),
            "stories": ("details", "stories"),
        }

        path = attribute_paths.get(attribute)
        if not path:
            # Unknown attribute, can't evaluate
            return False

        # Navigate to the value in property_data
        current = property_data
        for key in path:
            if not isinstance(current, dict):
                return False
            current = current.get(key)
            if current is None:
                return False

        actual_value = current

        # Evaluate based on operator
        try:
            if operator == "=":
                if isinstance(target_value, bool):
                    return bool(actual_value) == target_value
                elif isinstance(target_value, str):
                    return str(actual_value).lower() == target_value.lower()
                else:
                    return actual_value == target_value
            elif operator == "<":
                return float(actual_value) < float(target_value)
            elif operator == ">":
                return float(actual_value) > float(target_value)
            elif operator == "<=":
                return float(actual_value) <= float(target_value)
            elif operator == ">=":
                return float(actual_value) >= float(target_value)
            elif operator == "contains":
                return str(target_value).lower() in str(actual_value).lower()
            else:
                return False
        except (ValueError, TypeError):
            return False

    def _get_actual_value(
        self,
        attribute: str,
        property_data: Dict[str, Any]
    ) -> Any:
        """Get the actual value from property data for a given attribute."""
        attribute_paths = {
            "year_built": ("details", "year_built"),
            "has_hoa": ("hoa", "has_hoa"),
            "hoa_fee": ("hoa", "fee"),
            "property_type": ("details", "property_type"),
            "lot_size_sqft": ("details", "lot_size_sqft"),
            "living_area_sqft": ("details", "living_area_sqft"),
            "bedrooms": ("details", "bedrooms"),
            "bathrooms": ("details", "bathrooms"),
            "stories": ("details", "stories"),
            "has_pool": ("details", "has_pool"),
            "has_garage": ("details", "has_garage"),
        }

        path = attribute_paths.get(attribute)
        if not path:
            return None

        current = property_data
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None

        return current

    def search_by_attributes(
        self,
        property_data: Dict[str, Any],
        limit: int = 20,
    ) -> List[SearchResult]:
        """
        Find knowledge points that match property attributes via @applies_when tags.

        Scans all knowledge points that have applies_when conditions and returns
        those where ALL conditions match the property data.

        Args:
            property_data: Property data dict with structure:
                {
                    "details": {"year_built": 1985, "property_type": "townhome", ...},
                    "hoa": {"has_hoa": True, "fee": 350, ...},
                    ...
                }
            limit: Maximum results to return

        Returns:
            List of SearchResult sorted by priority (high > medium > low)
        """
        try:
            # Scroll through all points that have applies_when conditions
            # We need to check conditions in Python since Qdrant doesn't support
            # the complex condition evaluation we need
            all_points = []
            offset = None

            while True:
                results, offset = self.storage_service.client.scroll(
                    collection_name=self.storage_service.collection_name,
                    limit=500,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for point in results:
                    applies_when = point.payload.get("applies_when", [])
                    if not applies_when:
                        continue

                    # Check if ALL conditions match
                    all_match = True
                    for condition in applies_when:
                        # Skip invalid conditions (must be dict)
                        if not isinstance(condition, dict):
                            continue
                        if not self._evaluate_condition(condition, property_data):
                            all_match = False
                            break

                    if all_match:
                        all_points.append(SearchResult(
                            text=point.payload.get("text", ""),
                            category=point.payload.get("category", ""),
                            score=1.0,  # Attribute matches are binary
                            source_file=point.payload.get("source_file", ""),
                            priority=point.payload.get("priority", "medium"),
                        ))

                if offset is None:
                    break

            # Sort by priority: high > medium > low
            priority_order = {"high": 0, "medium": 1, "low": 2}
            all_points.sort(key=lambda r: priority_order.get(r.priority, 1))

            logger.info(
                f"Attribute search found {len(all_points)} matching knowledge points "
                f"(returning top {limit})"
            )

            return all_points[:limit]

        except Exception as e:
            logger.warning(f"Attribute-based search failed: {e}")
            return []

    def search_by_attributes_with_details(
        self,
        property_data: Dict[str, Any],
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Find knowledge points that match property attributes, including matched condition details.

        Returns knowledge points with the actual property values that triggered each match,
        suitable for displaying to users in the Property Insights section.

        Args:
            property_data: Property data dict with structure:
                {
                    "details": {"year_built": 1985, "property_type": "townhome", ...},
                    "hoa": {"has_hoa": True, "fee": 350, ...},
                    ...
                }
            limit: Maximum results to return

        Returns:
            List of dicts with structure:
            {
                "text": "Knowledge point text...",
                "category": "Home Age Considerations",
                "priority": "high",
                "matched_conditions": [
                    {"attribute": "year_built", "operator": "<", "value": 1980, "actual_value": 1975}
                ]
            }
        """
        try:
            all_points = []
            offset = None

            while True:
                results, offset = self.storage_service.client.scroll(
                    collection_name=self.storage_service.collection_name,
                    limit=500,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                for point in results:
                    applies_when = point.payload.get("applies_when", [])
                    if not applies_when:
                        continue

                    # Check if ALL conditions match and collect matched conditions
                    all_match = True
                    matched_conditions = []

                    for condition in applies_when:
                        if not isinstance(condition, dict):
                            continue

                        if not self._evaluate_condition(condition, property_data):
                            all_match = False
                            break

                        # Collect the matched condition with actual value
                        actual_value = self._get_actual_value(
                            condition.get("attribute", ""),
                            property_data
                        )
                        matched_conditions.append({
                            "attribute": condition.get("attribute"),
                            "operator": condition.get("operator"),
                            "value": condition.get("value"),
                            "actual_value": actual_value,
                        })

                    if all_match and matched_conditions:
                        all_points.append({
                            "text": point.payload.get("text", ""),
                            "category": point.payload.get("category", ""),
                            "priority": point.payload.get("priority", "medium"),
                            "matched_conditions": matched_conditions,
                        })

                if offset is None:
                    break

            # Sort by priority: high > medium > low
            priority_order = {"high": 0, "medium": 1, "low": 2}
            all_points.sort(key=lambda p: priority_order.get(p.get("priority", "medium"), 1))

            logger.info(
                f"Attribute search with details found {len(all_points)} matching knowledge points "
                f"(returning top {limit})"
            )

            return all_points[:limit]

        except Exception as e:
            logger.warning(f"Attribute-based search with details failed: {e}")
            return []

    def search_by_attributes_for_context(
        self,
        property_data: Dict[str, Any],
        limit: int = 10,
    ) -> str:
        """
        Search by attributes and format results as context for LLM injection.

        Groups results by category for cleaner context.
        Returns empty string if no results.
        """
        results = self.search_by_attributes(property_data, limit=limit)
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
