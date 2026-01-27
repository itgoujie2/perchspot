"""
School Skill - Analyzes nearby schools quality and ratings
"""
from typing import Dict, Any, List
import logging

from app.services.agent.skills.base_skill import BaseSkill
from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector

logger = logging.getLogger(__name__)


class SchoolSkill(BaseSkill):
    """
    Analyzes school quality using:
    - School ratings from Redfin
    - Distance to schools
    - School types (elementary, middle, high)
    """

    def __init__(self):
        super().__init__()
        self.redfin_collector = ScreenshotExtractorCollector()
        logger.info("SchoolSkill: Using Screenshot Extractor (Chromium + Claude Vision)")

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze schools near the property.

        Returns structured analysis with score, reasoning, strengths/concerns.
        """
        try:
            # Load skill from SKILL.md
            self._load_skill()

            # Get schools from Redfin (already scraped during property analysis)
            # For now, re-scrape to get schools data
            logger.info(f"SchoolSkill: Getting schools for {address}")
            redfin_result = await self.redfin_collector.scrape_property(address)

            if not redfin_result.get('success'):
                logger.error(f"SchoolSkill: Redfin scraping failed for {address}")
                return self._error_result("Failed to get school data")

            schools = redfin_result.get('schools', [])

            logger.info(f"SchoolSkill: Got {len(schools)} schools")

            # Analyze schools
            analysis = await self._analyze_schools(schools)

            return analysis

        except Exception as e:
            logger.error(f"SchoolSkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    async def _analyze_schools(self, schools: List[Dict]) -> Dict[str, Any]:
        """Use Claude to analyze schools."""

        if not schools:
            return {
                'score': 0,
                'confidence': 'low',
                'reasoning': 'No school data available',
                'strengths': [],
                'concerns': ['No nearby schools found or data unavailable'],
                'details': {'schools': []},
                'raw_data': {'schools': []}
            }

        # Build prompt with skill context (loaded from SKILL.md)
        schools_summary = "\n".join([
            f"- {s.get('name', 'Unknown')}: Rating {s.get('rating', 'N/A')}/10, "
            f"Grades {s.get('grades', 'N/A')}, "
            f"Distance {s.get('distance_miles', 'N/A')} miles, "
            f"Type: {s.get('type', 'N/A')}"
            for s in schools
        ])

        prompt = f"""
{self.skill_data['full_context']}

---

NEARBY SCHOOLS:
{schools_summary}

---

Using the context guidance above, analyze these schools and provide:
1. Overall school quality assessment
2. Breakdown by school level (elementary, middle, high)
3. Key strengths and concerns

Provide your analysis in this JSON format:
{{
    "score": <0-100>,
    "confidence": "<high|medium|low>",
    "reasoning": "<2-3 sentences explaining the score>",
    "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
    "concerns": ["<concern 1>", "<concern 2>", "<concern 3>"],
    "details": {{
        "elementary_rating": <rating or null>,
        "middle_rating": <rating or null>,
        "high_rating": <rating or null>,
        "average_distance": <miles>,
        "school_breakdown": [
            {{
                "name": "<school name>",
                "rating": <rating>,
                "type": "<type>",
                "assessment": "<brief assessment>"
            }}
        ]
    }}
}}

Return ONLY valid JSON, no other text.
"""

        # Call Claude
        response_text = await self._call_claude(prompt=prompt, max_tokens=2048)

        # Parse response
        analysis = self._parse_json_response(response_text)

        # Add raw data
        analysis['raw_data'] = {'schools': schools}

        logger.info(f"SchoolSkill: Analysis complete. Score: {analysis.get('score')}, Confidence: {analysis.get('confidence')}")

        return analysis

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Return error result structure."""
        return {
            'score': 0,
            'confidence': 'low',
            'reasoning': f'Analysis failed: {error_message}',
            'strengths': [],
            'concerns': ['School analysis could not be completed'],
            'details': {},
            'error': error_message
        }
