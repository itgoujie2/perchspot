"""
Main scoring engine - combines LLM and rule-based scoring
"""
import logging
from typing import Dict, Any
from decimal import Decimal

from app.config import settings

logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    Calculate overall property score from analysis results

    Uses weighted average of 4 categories:
    - Property Condition: 30%
    - Location Quality: 25%
    - Schools: 20%
    - Investment Value: 25%
    """

    # Category weights from settings
    WEIGHTS = {
        'property_condition': settings.WEIGHT_PROPERTY_CONDITION,
        'location_quality': settings.WEIGHT_LOCATION_QUALITY,
        'schools': settings.WEIGHT_SCHOOLS,
        'investment_value': settings.WEIGHT_INVESTMENT_VALUE,
    }

    def calculate_overall_score(
        self,
        property_condition_score: float,
        location_quality_score: float,
        schools_score: float,
        investment_value_score: float
    ) -> Dict[str, Any]:
        """
        Calculate weighted overall score and grade

        Args:
            property_condition_score: Score 0-100
            location_quality_score: Score 0-100
            schools_score: Score 0-100
            investment_value_score: Score 0-100

        Returns:
            Dictionary with overall score, grade, and breakdown
        """
        logger.info("Calculating overall property score")

        # Validate scores
        scores = {
            'property_condition': self._validate_score(property_condition_score),
            'location_quality': self._validate_score(location_quality_score),
            'schools': self._validate_score(schools_score),
            'investment_value': self._validate_score(investment_value_score),
        }

        # Calculate weighted average
        overall_score = sum(
            scores[category] * weight
            for category, weight in self.WEIGHTS.items()
        )

        # Round to 1 decimal place
        overall_score = round(overall_score, 1)

        # Calculate letter grade
        grade = self.score_to_grade(overall_score)

        # Calculate confidence
        confidence = self._calculate_confidence(scores)

        result = {
            'overall_score': Decimal(str(overall_score)),
            'overall_grade': grade,
            'confidence_level': confidence,
            'category_scores': {
                'property_condition': Decimal(str(scores['property_condition'])),
                'location_quality': Decimal(str(scores['location_quality'])),
                'schools': Decimal(str(scores['schools'])),
                'investment_value': Decimal(str(scores['investment_value'])),
            },
            'weights_used': self.WEIGHTS
        }

        logger.info(
            f"Overall score calculated: {overall_score}/100 ({grade}), "
            f"confidence: {confidence}"
        )

        return result

    @staticmethod
    def score_to_grade(score: float) -> str:
        """
        Convert numeric score to letter grade

        Args:
            score: Score 0-100

        Returns:
            Letter grade A-F
        """
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'

    @staticmethod
    def grade_to_description(grade: str) -> str:
        """Get description for grade"""
        descriptions = {
            'A': 'Excellent - Outstanding property with minimal concerns',
            'B': 'Very Good - Strong property with minor considerations',
            'C': 'Good - Solid property with some areas for improvement',
            'D': 'Fair - Acceptable property with notable concerns',
            'F': 'Poor - Property with significant issues'
        }
        return descriptions.get(grade, 'Unknown')

    def _validate_score(self, score: float) -> float:
        """Ensure score is in valid range 0-100"""
        if score < 0:
            logger.warning(f"Score {score} below 0, clamping to 0")
            return 0.0
        elif score > 100:
            logger.warning(f"Score {score} above 100, clamping to 100")
            return 100.0
        return float(score)

    def _calculate_confidence(self, scores: Dict[str, float]) -> str:
        """
        Calculate overall confidence level

        Args:
            scores: Dictionary of category scores

        Returns:
            Confidence level: 'high', 'medium', or 'low'
        """
        # If all scores are in reasonable range (not defaults), confidence is higher
        # If any scores are at common default values (50, 65), lower confidence

        default_values = {50, 65}  # Common fallback scores
        defaults_count = sum(1 for score in scores.values() if score in default_values)

        if defaults_count == 0:
            return 'high'
        elif defaults_count <= 1:
            return 'medium'
        else:
            return 'low'

    def get_score_interpretation(self, overall_score: float) -> Dict[str, str]:
        """
        Get human-readable interpretation of score

        Args:
            overall_score: Score 0-100

        Returns:
            Dictionary with interpretation details
        """
        if overall_score >= 90:
            return {
                'summary': 'Outstanding Property',
                'description': 'This property scores exceptionally well across all categories. It represents an excellent opportunity.',
                'recommendation': 'Highly recommended - Move quickly if interested'
            }
        elif overall_score >= 80:
            return {
                'summary': 'Excellent Property',
                'description': 'This property performs very well in most categories with only minor considerations.',
                'recommendation': 'Strongly recommended - Schedule viewing soon'
            }
        elif overall_score >= 70:
            return {
                'summary': 'Good Property',
                'description': 'This property is solid overall with some areas that could be improved.',
                'recommendation': 'Recommended - Worth considering seriously'
            }
        elif overall_score >= 60:
            return {
                'summary': 'Fair Property',
                'description': 'This property meets basic standards but has notable areas of concern.',
                'recommendation': 'Consider carefully - Weigh pros and cons'
            }
        else:
            return {
                'summary': 'Below Average Property',
                'description': 'This property has significant concerns across multiple categories.',
                'recommendation': 'Proceed with caution - Consider alternatives'
            }
