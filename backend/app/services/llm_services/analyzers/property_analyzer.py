"""
Property condition analyzer using OpenAI Vision API
"""
import logging
from typing import Dict, Any, List

from app.services.llm_services.openai_client import OpenAIClient
from app.services.llm_services.prompt_templates import (
    format_property_condition_prompt,
    PROPERTY_ANALYST_SYSTEM
)

logger = logging.getLogger(__name__)


class PropertyConditionAnalyzer:
    """
    Analyze property condition using text data and images
    """

    def __init__(self, llm_client: OpenAIClient = None):
        self.llm = llm_client or OpenAIClient()

    async def analyze(
        self,
        property_data: Dict[str, Any],
        images: List[bytes]
    ) -> Dict[str, Any]:
        """
        Analyze property condition using Vision API

        Args:
            property_data: Property information dictionary
            images: List of image bytes

        Returns:
            Analysis result with scores and insights
        """
        try:
            logger.info(f"Analyzing property condition for {property_data.get('address')}")

            # Format prompt
            prompt = format_property_condition_prompt(
                property_data=property_data,
                image_count=len(images)
            )

            # Call Vision API if images available
            if images and len(images) > 0:
                # Limit to max 15 images for cost optimization
                selected_images = images[:15]

                result = await self.llm.analyze_with_images(
                    prompt=prompt,
                    images=selected_images,
                    system_prompt=PROPERTY_ANALYST_SYSTEM,
                )
            else:
                # Fallback to text-only if no images
                logger.warning("No images available, using text-only analysis")
                result = await self.llm.analyze_text(
                    prompt=prompt,
                    system_prompt=PROPERTY_ANALYST_SYSTEM,
                )

            # Extract analysis from response
            analysis = result['response']

            # Validate response structure
            required_fields = ['overall_score', 'sub_scores', 'reasoning', 'confidence']
            if not all(field in analysis for field in required_fields):
                logger.error(f"Invalid analysis response structure: {analysis}")
                raise ValueError("Analysis response missing required fields")

            # Add metadata
            analysis['llm_cost'] = result.get('cost', 0)
            analysis['tokens_used'] = result.get('usage', {}).get('total_tokens', 0)
            analysis['model'] = result.get('model')

            logger.info(
                f"Property condition analysis complete: "
                f"score={analysis['overall_score']}, cost=${analysis['llm_cost']:.4f}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing property condition: {e}", exc_info=True)
            # Return fallback analysis
            return self._fallback_analysis(property_data)

    def _fallback_analysis(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback analysis when AI analysis fails
        Uses simple rule-based heuristics
        """
        logger.warning("Using fallback analysis for property condition")

        # Simple heuristic based on year built
        year_built = property_data.get('year_built')
        if year_built:
            age = 2024 - int(year_built)
            if age < 5:
                score = 90
            elif age < 15:
                score = 75
            elif age < 30:
                score = 60
            elif age < 50:
                score = 50
            else:
                score = 40
        else:
            score = 60  # Default average

        return {
            'overall_score': score,
            'sub_scores': {
                'exterior': score,
                'interior': score,
                'kitchen_bath': score,
                'systems': score
            },
            'reasoning': 'Analysis based on limited data (AI analysis unavailable)',
            'highlights': [],
            'concerns': ['Unable to perform detailed analysis - limited data'],
            'maintenance_priorities': [],
            'estimated_repair_costs': 'Unknown',
            'confidence': 'low',
            'llm_cost': 0,
            'tokens_used': 0,
            'fallback': True
        }
