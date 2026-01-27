"""
Property Skill - Analyzes property condition using photos and data
"""
from typing import Dict, Any
import logging

from app.services.agent.skills.base_skill import BaseSkill
from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector

logger = logging.getLogger(__name__)


class PropertySkill(BaseSkill):
    """
    Analyzes property condition using:
    - Redfin property data
    - Photos (vision AI analysis)
    - Property details (age, type, size)
    """

    def __init__(self):
        super().__init__()
        self.redfin_collector = ScreenshotExtractorCollector()
        logger.info("PropertySkill: Using Screenshot Extractor (Chromium + Claude Vision)")

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze property condition.

        Returns structured analysis with score, reasoning, strengths/concerns.
        """
        try:
            # Load skill from SKILL.md
            self._load_skill()

            # Scrape property data from Redfin
            logger.info(f"PropertySkill: Scraping Redfin for {address}")
            redfin_result = await self.redfin_collector.scrape_property(address)

            if not redfin_result.get('success'):
                logger.error(f"PropertySkill: Redfin scraping failed for {address}")
                return self._error_result("Failed to scrape property data")

            property_data = redfin_result.get('data', {})

            # Data is already extracted by ScreenshotExtractorCollector - convert to skill result format
            analysis = self._convert_extracted_data_to_analysis(property_data, address)
            logger.info(f"PropertySkill: Analysis complete. Score: {analysis.get('score')}")
            return analysis

        except Exception as e:
            logger.error(f"PropertySkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    def _convert_extracted_data_to_analysis(self, extracted_data: Dict, address: str) -> Dict[str, Any]:
        """
        Convert ScreenshotExtractorCollector data to PropertySkill analysis format.
        The screenshot collector already analyzed photos with Claude Vision.
        """
        prop = extracted_data.get('property', {})
        pricing = extracted_data.get('pricing', {})
        details = extracted_data.get('details', {})
        features = extracted_data.get('features', {})
        schools = extracted_data.get('schools', [])
        climate = extracted_data.get('climate_risks', {})

        # Calculate a property score based on extracted data
        score = 70  # Base score

        # Year built bonus/penalty
        year_built = details.get('year_built')
        if year_built:
            if year_built >= 2020:
                score += 15
            elif year_built >= 2010:
                score += 10
            elif year_built >= 2000:
                score += 5
            elif year_built < 1980:
                score -= 10

        # School ratings bonus
        if schools:
            avg_rating = sum(s.get('rating', 0) for s in schools) / len(schools)
            if avg_rating >= 8:
                score += 10
            elif avg_rating >= 6:
                score += 5

        # Climate risk penalties
        severe_risks = [k for k, v in climate.items() if v in ['Severe', 'Major']]
        score -= len(severe_risks) * 5

        # Cap score
        score = max(0, min(100, score))

        # Build strengths and concerns
        strengths = []
        concerns = []

        if year_built and year_built >= 2015:
            strengths.append(f"Newer construction ({year_built})")
        if details.get('bedrooms', 0) >= 4:
            strengths.append(f"{details.get('bedrooms')} bedrooms - great for families")
        if details.get('parking'):
            strengths.append(f"Parking: {details.get('parking')}")
        if schools and any(s.get('rating', 0) >= 9 for s in schools):
            strengths.append("Excellent school ratings (9+/10)")

        if severe_risks:
            concerns.append(f"Climate risks: {', '.join(severe_risks)}")
        if pricing.get('price_per_sqft', 0) > 700:
            concerns.append(f"High price per sq ft (${pricing.get('price_per_sqft')})")

        description = prop.get('description', 'No description available')

        return {
            'score': score,
            'confidence': 'high',
            'reasoning': f"Property analysis based on extracted Redfin data. {description[:200]}...",
            'strengths': strengths[:5] if strengths else ['Data extracted successfully'],
            'concerns': concerns[:5] if concerns else ['No major concerns identified'],
            'details': {
                'property_type': details.get('property_type'),
                'year_built': year_built,
                'bedrooms': details.get('bedrooms'),
                'bathrooms': details.get('bathrooms'),
                'living_area_sqft': details.get('living_area_sqft'),
                'lot_size_sqft': details.get('lot_size_sqft'),
                'parking': details.get('parking'),
                'features': features.get('interior', [])[:5],
                'appliances': features.get('appliances', [])
            },
            'raw_data': {
                'property': prop,
                'pricing': pricing,
                'details': details,
                'schools': schools,
                'climate_risks': climate,
                'extraction_metadata': extracted_data.get('_metadata', {})
            }
        }

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Return error result structure."""
        return {
            'score': 0,
            'confidence': 'low',
            'reasoning': f'Analysis failed: {error_message}',
            'strengths': [],
            'concerns': ['Analysis could not be completed'],
            'details': {},
            'error': error_message
        }
