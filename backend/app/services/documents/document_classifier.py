"""
Document Classifier - Auto-detect document type from filename and content
"""
import os
import logging
import re
from pathlib import Path
from typing import Literal, Optional
import anthropic

logger = logging.getLogger(__name__)

DocumentType = Literal["inspection", "hoa", "unknown"]


class DocumentClassifier:
    """
    Classifies uploaded documents as inspection reports or HOA documents.

    Uses a multi-stage approach:
    1. Filename heuristics (fast, no API cost)
    2. Content keyword heuristics (fast, no API cost)
    3. LLM classification (fallback, uses Haiku for low cost)
    """

    # Filename patterns
    INSPECTION_FILENAME_PATTERNS = [
        r'inspect',
        r'home\s*report',
        r'property\s*report',
        r'condition\s*report',
        r'deficiency',
    ]

    HOA_FILENAME_PATTERNS = [
        r'hoa',
        r'homeowner',
        r'association',
        r'ccr',
        r'cc&r',
        r'covenant',
        r'bylaw',
        r'declaration',
        r'reserve\s*study',
        r'budget',
    ]

    # Content keywords (search in first ~2000 chars)
    INSPECTION_KEYWORDS = [
        'inspector', 'inspection', 'deficiency', 'deficiencies',
        'recommend', 'repair', 'condition', 'foundation',
        'roof condition', 'electrical panel', 'hvac', 'plumbing',
        'structural', 'moisture', 'safety hazard', 'termite',
        'water heater', 'furnace', 'crawl space', 'attic',
    ]

    HOA_KEYWORDS = [
        'association', 'homeowner', 'covenant', 'bylaws',
        'assessment', 'dues', 'reserve', 'ccr', 'declaration',
        'architectural', 'common area', 'board of directors',
        'monthly fee', 'annual budget', 'special assessment',
        'rental restriction', 'pet policy', 'litigation',
    ]

    def __init__(self):
        self.claude_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

    def classify(self, filename: str, text_preview: str) -> tuple[DocumentType, float]:
        """
        Classify a document by its filename and text preview.

        Args:
            filename: Original filename of the document
            text_preview: First ~2000 characters of extracted text

        Returns:
            Tuple of (document_type, confidence)
            confidence: 0.0-1.0
        """
        # Stage 1: Filename heuristics
        filename_lower = filename.lower()

        for pattern in self.INSPECTION_FILENAME_PATTERNS:
            if re.search(pattern, filename_lower):
                logger.info(f"Classified as inspection from filename pattern: {pattern}")
                return "inspection", 0.9

        for pattern in self.HOA_FILENAME_PATTERNS:
            if re.search(pattern, filename_lower):
                logger.info(f"Classified as hoa from filename pattern: {pattern}")
                return "hoa", 0.9

        # Stage 2: Content keyword heuristics
        text_lower = text_preview.lower()

        inspection_score = sum(1 for kw in self.INSPECTION_KEYWORDS if kw in text_lower)
        hoa_score = sum(1 for kw in self.HOA_KEYWORDS if kw in text_lower)

        logger.info(f"Keyword scores - inspection: {inspection_score}, hoa: {hoa_score}")

        # Clear winner from keywords
        if inspection_score >= 3 and inspection_score > hoa_score * 2:
            return "inspection", 0.8

        if hoa_score >= 3 and hoa_score > inspection_score * 2:
            return "hoa", 0.8

        # Moderate difference
        if inspection_score >= 2 and inspection_score > hoa_score:
            return "inspection", 0.6

        if hoa_score >= 2 and hoa_score > inspection_score:
            return "hoa", 0.6

        # Stage 3: LLM classification (fallback)
        if len(text_preview.strip()) >= 100:
            return self._classify_with_llm(text_preview)

        return "unknown", 0.3

    def _classify_with_llm(self, text_preview: str) -> tuple[DocumentType, float]:
        """
        Use Haiku to classify document when heuristics are inconclusive.

        Args:
            text_preview: First ~2000 characters of text

        Returns:
            Tuple of (document_type, confidence)
        """
        try:
            prompt = f"""Classify this document as either an INSPECTION report or HOA document.

INSPECTION reports contain: property condition assessments, deficiency lists, repair recommendations, inspector findings, structural/HVAC/plumbing evaluations.

HOA documents contain: homeowner association rules, monthly fees, reserve funds, bylaws, covenants, CC&Rs, architectural guidelines, board meeting minutes.

Document text (first 2000 chars):
---
{text_preview[:2000]}
---

Respond with ONLY one of these exact words:
- INSPECTION
- HOA
- UNKNOWN"""

            response = self.claude_client.messages.create(
                model="claude-haiku-4-20250414",
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}]
            )

            result = response.content[0].text.strip().upper()
            logger.info(f"LLM classification result: {result}")

            if result == "INSPECTION":
                return "inspection", 0.7
            elif result == "HOA":
                return "hoa", 0.7
            else:
                return "unknown", 0.4

        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return "unknown", 0.3


# Global instance
_classifier: Optional[DocumentClassifier] = None


def get_document_classifier() -> DocumentClassifier:
    """Get singleton classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = DocumentClassifier()
    return _classifier
