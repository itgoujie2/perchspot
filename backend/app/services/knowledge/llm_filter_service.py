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

# Haiku is cost-effective for filtering tasks
DEFAULT_MODEL = "claude-3-5-haiku-20241022"

FILTER_PROMPT_TEMPLATE = """You are selecting relevant knowledge points for a home buyer evaluating a specific property.

PROPERTY:
{property_summary}

KNOWLEDGE CANDIDATES:
{numbered_candidates}

Select the 10-15 most relevant knowledge points that would help a buyer evaluate THIS SPECIFIC property. Consider:
- Property age and condition implications (e.g., if it's an older home, include relevant maintenance/inspection tips)
- Location-specific insights if applicable
- Financial considerations for this price point
- Features that need special attention (HOA, specific systems, etc.)
- General home-buying wisdom that applies to this type of purchase

Prioritize knowledge that:
1. Directly relates to a characteristic of this property (age, type, HOA, price range)
2. Would help the buyer ask better questions or make informed decisions
3. Covers potential issues or considerations the buyer might overlook

IMPORTANT - EXCLUDE knowledge that does NOT apply to this property type:
- For condos/apartments: SKIP foundation, roof, exterior siding, flood zone elevation, septic, well water, lot/yard maintenance tips — these are building-level concerns managed by HOA, not the unit buyer
- For single-family homes: SKIP HOA-specific condo rules (unless the home has an HOA)
- For new construction (<5 years): SKIP aging system replacement tips (roof replacement, pipe deterioration, etc.)
- Do NOT include flood zone or natural disaster knowledge UNLESS the property's climate risk data specifically indicates that risk
- Do NOT include knowledge about features the property does NOT have (e.g., pool maintenance for homes without pools)

Return ONLY the numbers of relevant points, comma-separated, with no explanation.
Example: 1, 5, 8, 12, 15, 23, 31"""


class KnowledgeFilterService:
    """Service to filter knowledge candidates using LLM."""

    def __init__(self, client: Optional[AsyncAnthropic] = None):
        self.client = client or AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def filter_relevant_knowledge(
        self,
        property_summary: str,
        candidates: List[Dict[str, Any]],
        max_results: int = 15,
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
