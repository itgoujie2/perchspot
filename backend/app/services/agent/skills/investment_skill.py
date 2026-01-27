"""
Investment Skill - Analyzes property as an investment opportunity
"""
from typing import Dict, Any
import logging

from app.services.agent.skills.base_skill import BaseSkill
from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector

logger = logging.getLogger(__name__)


class InvestmentSkill(BaseSkill):
    """
    Analyzes investment potential using:
    - Property price
    - Market trends
    - Comparable properties
    - Rental potential
    - Appreciation potential
    """

    def __init__(self):
        super().__init__()
        self.redfin_collector = ScreenshotExtractorCollector()
        logger.info("InvestmentSkill: Using Screenshot Extractor (Chromium + Claude Vision)")

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze investment potential.

        Returns structured analysis with score, reasoning, strengths/concerns.
        """
        try:
            # Load skill from SKILL.md
            self._load_skill()

            # Get property data for investment analysis
            logger.info(f"InvestmentSkill: Getting property data for {address}")
            redfin_result = await self.redfin_collector.scrape_property(address)

            if not redfin_result.get('success'):
                logger.error(f"InvestmentSkill: Redfin scraping failed for {address}")
                return self._error_result("Failed to get property data")

            property_data = redfin_result.get('data', {})

            logger.info(f"InvestmentSkill: Analyzing investment potential")

            # Analyze investment potential
            analysis = await self._analyze_investment(property_data)

            return analysis

        except Exception as e:
            logger.error(f"InvestmentSkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    async def _analyze_investment(self, property_data: Dict) -> Dict[str, Any]:
        """Analyze investment potential."""

        # Build prompt with skill context (loaded from SKILL.md)
        prompt = f"""
{self.skill_data['full_context']}

---

PROPERTY DATA:
- Address: {property_data.get('address', 'N/A')}
- Price: {property_data.get('price', 'N/A')}
- Bedrooms: {property_data.get('bedrooms', 'N/A')}
- Bathrooms: {property_data.get('bathrooms', 'N/A')}
- Square Feet: {property_data.get('square_feet', 'N/A')}
- Property Type: {property_data.get('property_type', 'N/A')}
- Days on Market: {property_data.get('days_on_market', 'N/A')}

---

Using the context guidance above, analyze this property's investment potential.

Consider:
1. Price relative to property characteristics
2. Days on market (market demand indicator)
3. Property type and size (rental/appreciation potential)
4. General market conditions in the area

Provide your analysis in this JSON format:
{{
    "score": <0-100>,
    "confidence": "<high|medium|low>",
    "reasoning": "<2-3 sentences explaining the score>",
    "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
    "concerns": ["<concern 1>", "<concern 2>", "<concern 3>"],
    "details": {{
        "price_assessment": "<fair/overpriced/underpriced>",
        "market_demand": "<high/medium/low based on days on market>",
        "rental_potential": "<assessment>",
        "appreciation_potential": "<assessment>"
    }}
}}

Return ONLY valid JSON, no other text.
"""

        # Call Claude
        response_text = await self._call_claude(prompt=prompt, max_tokens=2048)

        # Parse response
        analysis = self._parse_json_response(response_text)

        # Add raw data
        analysis['raw_data'] = {'property_data': property_data}

        logger.info(f"InvestmentSkill: Analysis complete. Score: {analysis.get('score')}, Confidence: {analysis.get('confidence')}")

        return analysis

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Return error result structure."""
        return {
            'score': 0,
            'confidence': 'low',
            'reasoning': f'Analysis failed: {error_message}',
            'strengths': [],
            'concerns': ['Investment analysis could not be completed'],
            'details': {},
            'error': error_message
        }
