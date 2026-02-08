"""
Storage Service — Qdrant vector database wrapper

Manages the knowledge collection with dual named vectors (dense + sparse).
Provides hybrid search via Qdrant's prefetch + RRF fusion.
"""
import logging
from typing import List, Optional, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
    PointStruct,
    ScoredPoint,
    SparseVector,
    Filter,
    FilterSelector,
    FieldCondition,
    MatchValue,
    Prefetch,
    FusionQuery,
    Fusion,
)

from app.config import settings

logger = logging.getLogger(__name__)

_instance = None


class StorageService:
    """Qdrant storage wrapper for the knowledge collection."""

    def __init__(self):
        self.client = QdrantClient(url=settings.QDRANT_URL, timeout=30)
        self.collection_name = settings.QDRANT_COLLECTION

    def ensure_collection(self):
        """Create the knowledge collection if it doesn't exist."""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in collections:
            logger.info(f"Collection '{self.collection_name}' already exists")
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(
                    size=settings.EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False),
                ),
            },
        )
        logger.info(f"Created collection '{self.collection_name}' "
                     f"(dense={settings.EMBEDDING_DIM}d + sparse BM25)")

    def upsert_points(self, points: List[PointStruct]):
        """Upsert points into the knowledge collection."""
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )

    def hybrid_search(
        self,
        dense_vector: List[float],
        sparse_vector: SparseVector,
        limit: int = 10,
        category_filter: Optional[str] = None,
    ) -> List[ScoredPoint]:
        """
        Hybrid search using Qdrant's prefetch + RRF fusion.

        Two prefetch queries run in parallel:
        1. Dense KNN (cosine similarity on Qwen3 embeddings)
        2. Sparse BM25 (term matching)

        Results are fused server-side using Reciprocal Rank Fusion.
        """
        search_filter = None
        if category_filter:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category_filter),
                    )
                ]
            )

        prefetch_limit = limit * 3  # Over-fetch for better fusion

        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=prefetch_limit,
                    filter=search_filter,
                ),
                Prefetch(
                    query=sparse_vector,
                    using="sparse",
                    limit=prefetch_limit,
                    filter=search_filter,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
        )

        return results.points

    def delete_by_source(self, source_id: str):
        """Delete all points from a specific source file."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="source_file",
                            match=MatchValue(value=source_id),
                        )
                    ]
                )
            ),
        )
        logger.info(f"Deleted points from source: {source_id}")

    def delete_point(self, point_id: str):
        """Delete a single point by ID."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=[point_id],
        )
        logger.info(f"Deleted point: {point_id}")

    def collection_info(self) -> Dict[str, Any]:
        """Return collection stats."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "collection": self.collection_name,
                "point_count": info.points_count,
                "status": str(info.status),
            }
        except Exception:
            return {
                "collection": self.collection_name,
                "point_count": 0,
                "status": "not_found",
            }

    def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def list_points(
        self,
        limit: int = 100,
        offset: int = 0,
        source_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List all points with optional filtering by source or category.
        Returns points with their payloads (text, category, source_file).
        """
        scroll_filter = None
        conditions = []

        if source_filter:
            conditions.append(
                FieldCondition(
                    key="source_file",
                    match=MatchValue(value=source_filter),
                )
            )

        if category_filter:
            conditions.append(
                FieldCondition(
                    key="category",
                    match=MatchValue(value=category_filter),
                )
            )

        if conditions:
            scroll_filter = Filter(must=conditions)

        # Use scroll to get points with pagination
        results, next_offset = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=scroll_filter,
            limit=limit,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )

        points = []
        for point in results:
            points.append({
                "id": str(point.id),
                "text": point.payload.get("text", ""),
                "category": point.payload.get("category", ""),
                "source_file": point.payload.get("source_file", ""),
            })

        return {
            "points": points,
            "count": len(points),
            "next_offset": next_offset,
        }

    def get_unique_values(self) -> Dict[str, List[str]]:
        """Get unique source files and categories from the collection."""
        sources = set()
        categories = set()

        # Scroll through all points to collect unique values
        offset = None
        while True:
            results, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=offset,
                with_payload=["source_file", "category"],
                with_vectors=False,
            )

            for point in results:
                if point.payload.get("source_file"):
                    sources.add(point.payload["source_file"])
                if point.payload.get("category"):
                    categories.add(point.payload["category"])

            if offset is None:
                break

        return {
            "sources": sorted(list(sources)),
            "categories": sorted(list(categories)),
        }


def get_storage_service() -> StorageService:
    """Get or create the singleton StorageService."""
    global _instance
    if _instance is None:
        _instance = StorageService()
    return _instance
