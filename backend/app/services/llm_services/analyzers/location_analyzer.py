"""
Location quality analyzer
"""
import logging
from typing import Dict, Any

from app.config import settings
from app.services.llm_services.openai_client import OpenAIClient
from app.services.llm_services.prompt_templates import (
    format_location_quality_prompt,
    PROPERTY_ANALYST_SYSTEM
)

logger = logging.getLogger(__name__)


class LocationQualityAnalyzer:
    """
    Analyze location quality and amenities
    """

    def __init__(self, llm_client: OpenAIClient = None):
        self.llm = llm_client or OpenAIClient()

    async def analyze(
        self,
        property_data: Dict[str, Any],
        neighborhood_data: Dict[str, Any] = None,
        amenities_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze location quality

        Args:
            property_data: Property information
            neighborhood_data: Neighborhood information (optional)
            amenities_data: Nearby amenities data (optional)

        Returns:
            Analysis result with scores and insights
        """
        try:
            logger.info(f"Analyzing location quality for {property_data.get('address')}")

            # Format data for prompt
            neighborhood_str = self._format_neighborhood_data(neighborhood_data or {})
            amenities_str = self._format_amenities_data(amenities_data or {})

            # Format prompt
            prompt = format_location_quality_prompt(
                property_data=property_data,
                neighborhood_data=neighborhood_str,
                amenities_data=amenities_str
            )

            # Call OpenAI API
            result = await self.llm.analyze_text(
                prompt=prompt,
                system_prompt=PROPERTY_ANALYST_SYSTEM,
                model=settings.LLM_MODEL  # Use GPT-4o for complex analysis
            )

            # Extract analysis
            analysis = result['response']

            # Validate response
            required_fields = ['overall_score', 'reasoning', 'confidence']
            if not all(field in analysis for field in required_fields):
                logger.error(f"Invalid analysis response: {analysis}")
                raise ValueError("Analysis response missing required fields")

            # Add metadata
            analysis['llm_cost'] = result.get('cost', 0)
            analysis['tokens_used'] = result.get('usage', {}).get('total_tokens', 0)
            analysis['model'] = result.get('model')

            logger.info(
                f"Location analysis complete: "
                f"score={analysis['overall_score']}, cost=${analysis['llm_cost']:.4f}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing location quality: {e}", exc_info=True)
            return self._fallback_analysis()

    def _format_neighborhood_data(self, data: Dict[str, Any]) -> str:
        """Format neighborhood data for prompt"""
        if not data:
            return "Limited neighborhood data available"

        formatted = []
        for key, value in data.items():
            formatted.append(f"- {key}: {value}")

        return "\n".join(formatted) if formatted else "No neighborhood data available"

    def _format_amenities_data(self, data: Dict[str, Any]) -> str:
        """Format amenities data for prompt"""
        if not data:
            return "Limited amenities data available"

        formatted = []
        for key, value in data.items():
            if isinstance(value, list):
                formatted.append(f"{key}:")
                for item in value:
                    formatted.append(f"  - {item}")
            else:
                formatted.append(f"- {key}: {value}")

        return "\n".join(formatted) if formatted else "No amenities data available"

    def _fallback_analysis(self) -> Dict[str, Any]:
        """Fallback analysis when AI fails"""
        logger.warning("Using fallback analysis for location quality")

        return {
            'overall_score': 65,  # Average
            'sub_scores': {
                'neighborhood': 65,
                'amenities': 65,
                'transportation': 65,
                'livability': 65
            },
            'reasoning': 'Analysis based on limited data (AI analysis unavailable)',
            'nearby_amenities': [],
            'transit_options': [],
            'strengths': [],
            'limitations': ['Unable to perform detailed analysis - limited data'],
            'confidence': 'low',
            'llm_cost': 0,
            'tokens_used': 0,
            'fallback': True
        }
