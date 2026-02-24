"""
LLM Filter Service — Uses Claude to select relevant knowledge points

Stage 2 of two-stage knowledge retrieval:
1. Stage 1 (SearchService.get_broad_candidates): Get 50-100 candidates via hybrid search
2. Stage 2 (this service): LLM selects 10-15 most relevant for the specific property

Uses Claude Haiku for cost efficiency (~$0.003 per analysis).
"""
import logging
import re
from typing import List, Dict, Any, Optional

from anthropic import AsyncAnthropic

from app.config import settings

logger = logging.getLogger(__name__)

# Haiku 4.5 — much better at following complex instructions, still cheap
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

FILTER_PROMPT_TEMPLATE = """You are a strict quality filter selecting the BEST knowledge points for a home buyer evaluating a specific property.

PROPERTY:
{property_summary}

KNOWLEDGE CANDIDATES:
{numbered_candidates}

YOUR TASK: Select EXACTLY 5 to 8 knowledge points — no more, no fewer. Quality over quantity.

SELECTION CRITERIA (include points that):
- Directly relate to THIS property's specific characteristics (age, type, price, features)
- Would help the buyer ask better questions or avoid costly mistakes
- Cover maintenance, inspection, or financial considerations specific to this property

MANDATORY EXCLUSION RULES — violating any of these is an error:
1. NO HOA: If property shows "No HOA" or "Does NOT have: HOA" → EXCLUDE ALL HOA knowledge (reserve funds, special assessments, fees, boards, budgets, transfer fees)
2. NO FLOOD: If climate risks show "minimal/none" → EXCLUDE all flood zone, flood insurance, floodplain knowledge
3. WRONG ERA: If a candidate mentions a specific decade (e.g., "1940s-1950s") and the property's year built is more than 15 years outside that range → EXCLUDE
4. WRONG CITY: If a candidate is about a specific city/neighborhood NOT in the same metro area as this property → EXCLUDE
5. MISSING FEATURES: If the property lists features it does NOT have (e.g., "Does NOT have: pool") → EXCLUDE knowledge about those features
6. WRONG PROPERTY TYPE: Condo tips for single-family homes (and vice versa) → EXCLUDE
7. ENVIRONMENTAL: Generic landfill/superfund/contamination tips with no connection to this property → EXCLUDE
8. DUPLICATES: If two candidates say essentially the same thing in different words → select only ONE

Return ONLY the numbers of selected points, comma-separated. No explanation.
Example: 3, 7, 12, 18, 25"""


class KnowledgeFilterService:
    """Service to filter knowledge candidates using LLM."""

    def __init__(self, client: Optional[AsyncAnthropic] = None):
        self.client = client or AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def filter_relevant_knowledge(
        self,
        property_summary: str,
        candidates: List[Dict[str, Any]],
        max_results: int = 8,
        model: str = DEFAULT_MODEL,
    ) -> List[int]:
        """
        Use LLM to select most relevant knowledge points for a property.

        Args:
            property_summary: Formatted property summary from context_builder
            candidates: List of candidate knowledge points with keys:
                - text: Knowledge point text
                - category: Category name
            max_results: Maximum number of points to select
            model: Claude model to use (default: Haiku for cost)

        Returns:
            List of indices (0-based) of selected candidates

        Raises:
            Returns empty list on any error (graceful fallback)
        """
        if not candidates:
            return []

        try:
            # Format candidates as numbered list
            numbered_candidates = self._format_candidates(candidates)

            # Build prompt
            prompt = FILTER_PROMPT_TEMPLATE.format(
                property_summary=property_summary,
                numbered_candidates=numbered_candidates,
            )

            # Call Claude
            response = await self.client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse response to get indices
            response_text = response.content[0].text.strip()
            selected_indices = self._parse_indices(response_text, len(candidates))

            # Limit to max_results
            selected_indices = selected_indices[:max_results]

            # Log usage for cost tracking
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            logger.info(
                f"LLM filter selected {len(selected_indices)}/{len(candidates)} candidates "
                f"(tokens: {input_tokens} in, {output_tokens} out)"
            )

            return selected_indices

        except Exception as e:
            logger.warning(f"LLM filter failed, returning empty list: {e}")
            return []

    def _format_candidates(self, candidates: List[Dict[str, Any]]) -> str:
        """Format candidates as numbered list for prompt."""
        lines = []
        for i, c in enumerate(candidates):
            category = c.get("category", "General")
            text = c.get("text", "").strip()
            # Truncate long texts to save tokens
            if len(text) > 300:
                text = text[:297] + "..."
            lines.append(f"{i + 1}. [{category}] {text}")
        return "\n".join(lines)

    def _parse_indices(self, response_text: str, num_candidates: int) -> List[int]:
        """
        Parse LLM response to extract selected indices.

        Handles various formats:
        - "1, 5, 8, 12"
        - "1,5,8,12"
        - "1 5 8 12"
        - Mixed with text

        Returns 0-based indices.
        """
        # Extract all numbers from response
        numbers = re.findall(r'\d+', response_text)

        indices = []
        for num_str in numbers:
            try:
                num = int(num_str)
                # Convert 1-based to 0-based and validate range
                if 1 <= num <= num_candidates:
                    idx = num - 1
                    if idx not in indices:  # Avoid duplicates
                        indices.append(idx)
            except ValueError:
                continue

        return indices


# Singleton instance
_instance: Optional[KnowledgeFilterService] = None


def get_filter_service() -> KnowledgeFilterService:
    """Get or create the singleton KnowledgeFilterService."""
    global _instance
    if _instance is None:
        _instance = KnowledgeFilterService()
    return _instance
