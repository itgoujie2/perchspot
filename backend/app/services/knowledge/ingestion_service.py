"""
Ingestion Service — Parse markdown files and ingest knowledge points

Parses .md files with numbered category headings (## N. Category Name)
and extracts one knowledge point per paragraph.
"""
import logging
import os
import re
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any

from qdrant_client.models import PointStruct

from app.services.knowledge.embedding_service import get_embedding_service
from app.services.knowledge.storage_service import get_storage_service

logger = logging.getLogger(__name__)

BATCH_SIZE = 8  # Smaller batches for better progress visibility


@dataclass
class KnowledgePoint:
    """A single knowledge point extracted from a markdown file."""
    text: str
    category: str
    heading: str
    source_file: str
    point_index: int = 0


class IngestionService:
    """Parses markdown files and ingests knowledge points into Qdrant."""

    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.storage_service = get_storage_service()

    def ingest_markdown(self, file_path: str, source_id: str = None) -> Dict[str, Any]:
        """
        Parse a markdown file and ingest all knowledge points.

        Args:
            file_path: Path to the .md file
            source_id: Optional override for source identifier (defaults to filename)

        Returns:
            Dict with ingestion stats
        """
        if source_id is None:
            source_id = os.path.basename(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        points = self._parse_markdown(content, source_id)
        if not points:
            logger.warning(f"No knowledge points found in: {file_path}")
            return {"status": "ok", "points_ingested": 0, "source_file": source_id}

        logger.info(f"Parsed {len(points)} knowledge points from: {source_id}")

        # Upsert per knowledge point — deterministic IDs based on text content
        # so re-uploading the same point (from any file) overwrites it,
        # and new points are simply added.
        self._batch_embed_and_upsert(points, source_id)

        return {
            "status": "ok",
            "points_ingested": len(points),
            "source_file": source_id,
            "categories": list(set(p.category for p in points)),
        }

    def _parse_markdown(self, content: str, source_file: str) -> List[KnowledgePoint]:
        """
        Parse markdown content into knowledge points.

        Expected formats:
            ## 1. Category Name       (markdown numbered)
            ## Category Name           (markdown unnumbered)
            1. Category Name           (plain numbered)

        Knowledge points are split by:
            1. Empty lines (paragraph boundaries)
            2. Bullet points (- or * at start of line) - each bullet = separate point
        """
        points: List[KnowledgePoint] = []
        current_category = ""
        current_heading = ""
        point_index = 0

        lines = content.split("\n")
        current_paragraph_lines: List[str] = []

        def flush_paragraph():
            """Helper to flush accumulated paragraph lines as a knowledge point."""
            nonlocal point_index
            if current_paragraph_lines and current_category:
                text = " ".join(current_paragraph_lines).strip()
                if text:
                    points.append(KnowledgePoint(
                        text=text,
                        category=current_category,
                        heading=current_heading,
                        source_file=source_file,
                        point_index=point_index,
                    ))
                    point_index += 1
            current_paragraph_lines.clear()

        for line in lines:
            stripped = line.strip()

            # Check for category heading in multiple formats:
            #   ## 1. Category Name | ## Category Name | 1. Category Name
            heading_match = (
                re.match(r'^##\s+(?:\d+\.\s+)?(.+)$', stripped) or
                re.match(r'^\d+\.\s+(.+)$', stripped)
            )
            if heading_match:
                # Flush any accumulated paragraph
                flush_paragraph()
                current_category = heading_match.group(1).strip()
                current_heading = line.strip()
                continue

            # Skip top-level heading (# Title)
            if stripped.startswith("# ") and not stripped.startswith("## "):
                continue

            # Skip separators
            if stripped == "---":
                continue

            # Empty line = paragraph boundary
            if not stripped:
                flush_paragraph()
                continue

            # Check for bullet point (- or * at start)
            bullet_match = re.match(r'^[-*]\s+(.+)$', stripped)
            if bullet_match and current_category:
                # Flush any previous paragraph first
                flush_paragraph()
                # Extract bullet content (remove the - or * prefix)
                bullet_text = bullet_match.group(1).strip()
                if bullet_text:
                    points.append(KnowledgePoint(
                        text=bullet_text,
                        category=current_category,
                        heading=current_heading,
                        source_file=source_file,
                        point_index=point_index,
                    ))
                    point_index += 1
                continue

            # Accumulate regular paragraph lines
            if current_category:
                current_paragraph_lines.append(stripped)

        # Flush final paragraph
        flush_paragraph()

        return points

    def _batch_embed_and_upsert(self, points: List[KnowledgePoint], source_id: str):
        """Embed knowledge points in batches and upsert to Qdrant."""
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i:i + BATCH_SIZE]
            texts = [p.text for p in batch]

            # Generate dense + sparse embeddings
            dense_vectors = self.embedding_service.embed_dense(texts)
            sparse_vectors = self.embedding_service.embed_sparse(texts)

            # Build Qdrant points
            qdrant_points = []
            for j, point in enumerate(batch):
                # Deterministic ID from content — same text always gets the same ID
                point_id = str(uuid.UUID(hashlib.md5(point.text.encode()).hexdigest()))
                qdrant_points.append(
                    PointStruct(
                        id=point_id,
                        vector={
                            "dense": dense_vectors[j],
                            "sparse": sparse_vectors[j],
                        },
                        payload={
                            "text": point.text,
                            "category": point.category,
                            "heading": point.heading,
                            "source_file": point.source_file,
                            "point_index": point.point_index,
                            "ingested_at": datetime.utcnow().isoformat(),
                        },
                    )
                )

            self.storage_service.upsert_points(qdrant_points)
            logger.info(f"Upserted batch {i // BATCH_SIZE + 1}: "
                        f"{len(qdrant_points)} points from {source_id}")


_instance = None


def get_ingestion_service() -> IngestionService:
    """Get or create the singleton IngestionService."""
    global _instance
    if _instance is None:
        _instance = IngestionService()
    return _instance
