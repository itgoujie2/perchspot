"""
Location Skill - Analyzes location quality, commute, and neighborhood
"""
from typing import Dict, Any
import logging

from app.services.agent.skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)


class LocationSkill(BaseSkill):
    """
    Analyzes location quality using:
    - Neighborhood characteristics
    - Commute times (if user provides work location)
    - Walkability
    - Nearby amenities
    """

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze location quality.

        Args:
            address: Property address
            **kwargs: Optional params like work_location for commute analysis

        Returns structured analysis with score, reasoning, strengths/concerns.
        """
        try:
            # Load skill from SKILL.md
            self._load_skill()

            work_location = kwargs.get('work_location')

            logger.info(f"LocationSkill: Analyzing location for {address}")

            # For now, basic analysis based on address/area
            # TODO: Add Google Places API, commute API, etc.
            analysis = await self._analyze_location(address, work_location)

            return analysis

        except Exception as e:
            logger.error(f"LocationSkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    async def _analyze_location(self, address: str, work_location: str = None) -> Dict[str, Any]:
        """Analyze location characteristics."""

        # Extract city/state from address for basic analysis
        prompt = f"""
{self.skill_data['full_context']}

---

PROPERTY ADDRESS: {address}
WORK LOCATION: {work_location or 'Not provided'}

---

Using the context guidance above, analyze this property's location quality.

Consider:
1. Neighborhood characteristics (urban/suburban/rural)
2. Accessibility and walkability
3. Commute considerations (if work location provided)
4. General location desirability

Provide your analysis in this JSON format:
{{
    "score": <0-100>,
    "confidence": "<high|medium|low>",
    "reasoning": "<2-3 sentences explaining the score>",
    "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
    "concerns": ["<concern 1>", "<concern 2>", "<concern 3>"],
    "details": {{
        "neighborhood_type": "<urban/suburban/rural>",
        "walkability_assessment": "<description>",
        "commute_assessment": "<description if work location provided>",
        "amenities_nearby": ["<amenity 1>", "<amenity 2>"]
    }}
}}

Return ONLY valid JSON, no other text.
"""

        # Call Claude
        response_text = await self._call_claude(prompt=prompt, max_tokens=2048)

        # Parse response
        analysis = self._parse_json_response(response_text)

        # Add raw data
        analysis['raw_data'] = {
            'address': address,
            'work_location': work_location
        }

        logger.info(f"LocationSkill: Analysis complete. Score: {analysis.get('score')}, Confidence: {analysis.get('confidence')}")

        return analysis

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Return error result structure."""
        return {
            'score': 0,
            'confidence': 'low',
            'reasoning': f'Analysis failed: {error_message}',
            'strengths': [],
            'concerns': ['Location analysis could not be completed'],
            'details': {},
            'error': error_message
        }
