"""
Ingestion Service — Parse markdown files and ingest knowledge points

Parses .md files with numbered category headings (## N. Category Name)
and extracts one knowledge point per paragraph.

Supports attribute-based tagging via @applies_when tags:
    @applies_when: year_built<1990
    @applies_when: has_hoa=true
    @priority: high
"""
import logging
import os
import re
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from qdrant_client.models import PointStruct

from app.services.knowledge.embedding_service import get_embedding_service
from app.services.knowledge.storage_service import get_storage_service

logger = logging.getLogger(__name__)

BATCH_SIZE = 8  # Smaller batches for better progress visibility


@dataclass
class AppliesWhenCondition:
    """A single applicability condition parsed from @applies_when tag."""
    attribute: str
    operator: str  # =, <, >, <=, >=, contains
    value: Any  # bool, int, float, or str


@dataclass
class KnowledgePoint:
    """A single knowledge point extracted from a markdown file."""
    text: str
    category: str
    heading: str
    source_file: str
    point_index: int = 0
    applies_when: List[AppliesWhenCondition] = field(default_factory=list)
    priority: str = "medium"  # high, medium, low


class IngestionService:
    """Parses markdown files and ingests knowledge points into Qdrant."""

    # Regex for parsing @applies_when conditions
    # Matches: attribute<value, attribute>value, attribute<=value, attribute>=value,
    #          attribute=value, attribute contains value
    CONDITION_PATTERN = re.compile(
        r'^(\w+)\s*(<=|>=|<|>|=|contains)\s*(.+)$',
        re.IGNORECASE
    )

    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.storage_service = get_storage_service()

    def _parse_condition(self, condition_str: str) -> Optional[AppliesWhenCondition]:
        """
        Parse a single @applies_when condition string.

        Examples:
            "year_built<1990" -> AppliesWhenCondition("year_built", "<", 1990)
            "has_hoa=true" -> AppliesWhenCondition("has_hoa", "=", True)
            "property_type contains condo" -> AppliesWhenCondition("property_type", "contains", "condo")
        """
        condition_str = condition_str.strip()
        match = self.CONDITION_PATTERN.match(condition_str)
        if not match:
            logger.warning(f"Could not parse condition: {condition_str}")
            return None

        attribute = match.group(1).lower()
        operator = match.group(2).lower()
        raw_value = match.group(3).strip()

        # Parse value type
        value: Any
        if raw_value.lower() == 'true':
            value = True
        elif raw_value.lower() == 'false':
            value = False
        else:
            # Try parsing as number
            try:
                if '.' in raw_value:
                    value = float(raw_value)
                else:
                    value = int(raw_value)
            except ValueError:
                # Keep as string
                value = raw_value.lower()

        return AppliesWhenCondition(attribute=attribute, operator=operator, value=value)

    def _extract_tags_from_section(self, lines: List[str]) -> tuple[List[str], List[AppliesWhenCondition], str]:
        """
        Extract @applies_when and @priority tags from the beginning of a section.

        Returns:
            (content_lines, applies_when_conditions, priority)
        """
        applies_when: List[AppliesWhenCondition] = []
        priority = "medium"
        content_lines: List[str] = []
        in_tags = True

        for line in lines:
            stripped = line.strip()

            if in_tags:
                if stripped.startswith('@applies_when:'):
                    condition_str = stripped.replace('@applies_when:', '').strip()
                    parsed = self._parse_condition(condition_str)
                    if parsed:
                        applies_when.append(parsed)
                    continue
                elif stripped.startswith('@priority:'):
                    priority = stripped.replace('@priority:', '').strip().lower()
                    if priority not in ('high', 'medium', 'low'):
                        priority = 'medium'
                    continue
                elif stripped.startswith('@'):
                    # Skip other unknown tags
                    continue
                else:
                    # End of tags section
                    in_tags = False

            if not in_tags and stripped:
                content_lines.append(stripped)

        return content_lines, applies_when, priority

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
            3. --- separators (section boundaries for tags)

        Supports attribute tags at the start of sections:
            @applies_when: year_built<1990
            @applies_when: has_hoa=true
            @priority: high
        """
        points: List[KnowledgePoint] = []
        current_category = ""
        current_heading = ""
        point_index = 0

        # Current section's tags (from @applies_when, @priority)
        current_applies_when: List[AppliesWhenCondition] = []
        current_priority = "medium"

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
                        applies_when=list(current_applies_when),  # Copy current tags
                        priority=current_priority,
                    ))
                    point_index += 1
            current_paragraph_lines.clear()

        i = 0
        while i < len(lines):
            line = lines[i]
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

                # Look ahead for @tags after the heading
                tag_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.startswith('@'):
                        tag_lines.append(next_line)
                        j += 1
                    elif not next_line:
                        # Empty line, might have more tags after
                        j += 1
                    else:
                        break

                if tag_lines:
                    _, current_applies_when, current_priority = self._extract_tags_from_section(tag_lines)
                    i = j - 1  # Skip processed tag lines (will be incremented at end of loop)
                else:
                    # Reset tags for new section without explicit tags
                    current_applies_when = []
                    current_priority = "medium"

                i += 1
                continue

            # Skip top-level heading (# Title)
            if stripped.startswith("# ") and not stripped.startswith("## "):
                i += 1
                continue

            # Separator --- resets section tags and acts as boundary
            if stripped == "---":
                flush_paragraph()
                # Look ahead for @tags after separator
                tag_lines = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.startswith('@'):
                        tag_lines.append(next_line)
                        j += 1
                    elif not next_line:
                        j += 1
                    else:
                        break

                if tag_lines:
                    _, current_applies_when, current_priority = self._extract_tags_from_section(tag_lines)
                    i = j - 1
                else:
                    # Reset to no tags
                    current_applies_when = []
                    current_priority = "medium"

                i += 1
                continue

            # Skip @ tag lines that weren't consumed by heading/separator lookahead
            if stripped.startswith('@'):
                i += 1
                continue

            # Empty line = paragraph boundary
            if not stripped:
                flush_paragraph()
                i += 1
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
                        applies_when=list(current_applies_when),
                        priority=current_priority,
                    ))
                    point_index += 1
                i += 1
                continue

            # Accumulate regular paragraph lines
            if current_category:
                current_paragraph_lines.append(stripped)

            i += 1

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

                # Serialize applies_when conditions for storage
                applies_when_data = [
                    {
                        "attribute": cond.attribute,
                        "operator": cond.operator,
                        "value": cond.value,
                    }
                    for cond in point.applies_when
                ]

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
                            "applies_when": applies_when_data,
                            "priority": point.priority,
                        },
                    )
                )

            self.storage_service.upsert_points(qdrant_points)
            tagged_count = sum(1 for p in batch if p.applies_when)
            logger.info(f"Upserted batch {i // BATCH_SIZE + 1}: "
                        f"{len(qdrant_points)} points from {source_id} "
                        f"({tagged_count} with attribute tags)")


_instance = None


def get_ingestion_service() -> IngestionService:
    """Get or create the singleton IngestionService."""
    global _instance
    if _instance is None:
        _instance = IngestionService()
    return _instance
