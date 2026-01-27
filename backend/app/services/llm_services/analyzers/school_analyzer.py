"""
School quality analyzer
"""
import logging
from typing import Dict, Any, List

from app.config import settings
from app.services.llm_services.openai_client import OpenAIClient
from app.services.llm_services.prompt_templates import (
    format_school_analysis_prompt,
    EDUCATION_ANALYST_SYSTEM
)

logger = logging.getLogger(__name__)


class SchoolAnalyzer:
    """
    Analyze school quality and accessibility
    """

    def __init__(self, llm_client: OpenAIClient = None):
        self.llm = llm_client or OpenAIClient()

    async def analyze(
        self,
        property_data: Dict[str, Any],
        schools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze school quality

        Args:
            property_data: Property information
            schools: List of nearby schools with ratings

        Returns:
            Analysis result with scores and insights
        """
        try:
            logger.info(f"Analyzing schools for {property_data.get('address')}")

            # If no schools data, use rule-based fallback
            if not schools:
                logger.warning("No schools data available")
                return self._fallback_analysis()

            # Format schools data for prompt
            schools_str = self._format_schools_data(schools)

            # Format prompt
            prompt = format_school_analysis_prompt(
                property_data=property_data,
                schools_data=schools_str
            )

            # Call OpenAI API with cheaper model (gpt-4o-mini) for simpler analysis
            result = await self.llm.analyze_text(
                prompt=prompt,
                system_prompt=EDUCATION_ANALYST_SYSTEM,
                model=settings.LLM_CHEAP_MODEL  # Use cheaper model for cost savings
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
                f"School analysis complete: "
                f"score={analysis['overall_score']}, cost=${analysis['llm_cost']:.4f}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing schools: {e}", exc_info=True)
            # Try rule-based analysis
            return self._rule_based_analysis(schools)

    def _format_schools_data(self, schools: List[Dict[str, Any]]) -> str:
        """Format schools data for prompt"""
        if not schools:
            return "No schools data available"

        formatted = []
        for school in schools:
            school_str = f"""
School: {school.get('name', 'Unknown')}
Type: {school.get('school_type', 'Unknown')}
Rating: {school.get('rating', 'N/A')}/10
Distance: {school.get('distance_miles', 'N/A')} miles
Address: {school.get('address', 'N/A')}
"""
            formatted.append(school_str.strip())

        return "\n\n".join(formatted)

    def _rule_based_analysis(self, schools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Rule-based school analysis when AI fails

        Calculate score based on:
        - Average school ratings
        - Distance to schools
        - Availability of all school levels
        """
        logger.info("Using rule-based school analysis")

        if not schools:
            return self._fallback_analysis()

        # Calculate average rating
        ratings = [s.get('rating', 0) for s in schools if s.get('rating')]
        avg_rating = sum(ratings) / len(ratings) if ratings else 5.0

        # Normalize to 0-100 scale
        score = (avg_rating / 10) * 100

        # Bonus for having all school types within reasonable distance
        school_types = set(s.get('school_type') for s in schools)
        if 'elementary' in school_types:
            score += 5
        if 'middle' in school_types:
            score += 5
        if 'high' in school_types:
            score += 5

        # Penalty for distance (prefer schools within 3 miles)
        avg_distance = sum(s.get('distance_miles', 5) for s in schools) / len(schools)
        if avg_distance < 1:
            score += 10
        elif avg_distance < 2:
            score += 5
        elif avg_distance > 5:
            score -= 10

        # Cap at 100
        score = min(100, max(0, score))

        return {
            'overall_score': round(score, 1),
            'schools': schools,
            'reasoning': f'Average school rating: {avg_rating:.1f}/10. {len(schools)} schools within range.',
            'highlights': [f'{len(ratings)} schools found with ratings'],
            'concerns': [] if avg_rating >= 7 else ['School ratings below average'],
            'recommendation': self._get_recommendation(score),
            'confidence': 'medium',
            'llm_cost': 0,
            'tokens_used': 0,
            'rule_based': True
        }

    def _get_recommendation(self, score: float) -> str:
        """Get recommendation based on score"""
        if score >= 80:
            return "Excellent schools - highly recommended for families"
        elif score >= 70:
            return "Good schools - suitable for families"
        elif score >= 60:
            return "Adequate schools - consider visiting to assess fit"
        else:
            return "Below average schools - families may want to explore private or charter options"

    def _fallback_analysis(self) -> Dict[str, Any]:
        """Fallback when no data available"""
        logger.warning("Using fallback analysis for schools")

        return {
            'overall_score': 50,  # Unknown/average
            'schools': [],
            'reasoning': 'No school data available for analysis',
            'highlights': [],
            'concerns': ['School data not available'],
            'recommendation': 'Research schools independently before making decision',
            'confidence': 'low',
            'llm_cost': 0,
            'tokens_used': 0,
            'fallback': True
        }
