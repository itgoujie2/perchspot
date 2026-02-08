"""
Analysis Orchestrator - Phase 1: Runs skills in parallel

This orchestrator:
1. Loads pre-extracted property data from property_data/ JSON files
2. Runs all analysis skills in parallel, sharing the loaded data
3. Aggregates results
4. Calculates overall score
5. Returns structured results for Phase 2 (conversation)
"""
import asyncio
import json
import re
from pathlib import Path
from typing import Dict, Any
import logging

from app.services.agent.skills import (
    PropertySkill,
    SchoolSkill,
    LocationSkill,
    InvestmentSkill
)

logger = logging.getLogger(__name__)


class AnalysisOrchestrator:
    """
    Orchestrates parallel execution of all analysis skills.
    """

    def __init__(self):
        self.property_skill = PropertySkill()
        self.school_skill = SchoolSkill()
        self.location_skill = LocationSkill()
        self.investment_skill = InvestmentSkill()

    async def analyze_property(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Run full property analysis with all skills in parallel.

        Args:
            address: Property address
            **kwargs: Optional parameters (work_location, etc.)

        Returns:
            {
                'address': str,
                'overall_score': int (0-100),
                'overall_grade': str ('A'-'F'),
                'property': {...},  # Property skill results
                'schools': {...},   # School skill results
                'location': {...},  # Location skill results
                'investment': {...}, # Investment skill results
                'category_weights': {...},
                'analyzed_at': str (ISO timestamp)
            }
        """
        logger.info(f"Starting full property analysis for: {address}")

        try:
            # Load extracted property data once and share across skills
            property_data = kwargs.pop('property_data', None) or self._load_property_data(address)

            # Run all skills in parallel
            property_result, school_result, location_result, investment_result = await asyncio.gather(
                self.property_skill.analyze(address, property_data=property_data, **kwargs),
                self.school_skill.analyze(address, property_data=property_data, **kwargs),
                self.location_skill.analyze(address, property_data=property_data, **kwargs),
                self.investment_skill.analyze(address, property_data=property_data, **kwargs),
                return_exceptions=True
            )

            # Handle exceptions
            def handle_skill_result(result, skill_name):
                if isinstance(result, Exception):
                    logger.error(f"{skill_name} failed: {result}")
                    return {
                        'score': 0,
                        'confidence': 'low',
                        'reasoning': f'{skill_name} analysis failed',
                        'strengths': [],
                        'concerns': [f'{skill_name} could not be completed'],
                        'details': {},
                        'error': str(result)
                    }
                return result

            property_result = handle_skill_result(property_result, 'PropertySkill')
            school_result = handle_skill_result(school_result, 'SchoolSkill')
            location_result = handle_skill_result(location_result, 'LocationSkill')
            investment_result = handle_skill_result(investment_result, 'InvestmentSkill')

            # Calculate overall score with weights
            weights = {
                'property': 0.30,
                'schools': 0.20,
                'location': 0.25,
                'investment': 0.25
            }

            overall_score = int(
                property_result['score'] * weights['property'] +
                school_result['score'] * weights['schools'] +
                location_result['score'] * weights['location'] +
                investment_result['score'] * weights['investment']
            )

            # Calculate grade
            overall_grade = self._calculate_grade(overall_score)

            # Build result
            from datetime import datetime
            result = {
                'address': address,
                'overall_score': overall_score,
                'overall_grade': overall_grade,
                'property': property_result,
                'schools': school_result,
                'location': location_result,
                'investment': investment_result,
                'category_weights': weights,
                'analyzed_at': datetime.utcnow().isoformat() + 'Z'
            }

            logger.info(f"Analysis complete for {address}. Overall score: {overall_score} ({overall_grade})")

            return result

        except Exception as e:
            logger.error(f"Analysis orchestration failed: {e}", exc_info=True)
            raise

    @staticmethod
    def _load_property_data(address: str) -> Dict[str, Any]:
        """Load pre-extracted property data from JSON file."""
        slug = re.sub(r'[^\w\s-]', '', address.lower())
        slug = re.sub(r'[\s-]+', '_', slug)[:50]

        data_dir = Path("/app/property_data")
        if not data_dir.exists():
            data_dir = Path("./property_data")

        json_path = data_dir / f"{slug}.json"
        if not json_path.exists():
            logger.warning(f"Property data not found: {json_path}")
            return {}

        with open(json_path, 'r') as f:
            return json.load(f)

    def _calculate_grade(self, score: int) -> str:
        """Convert score to letter grade."""
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

    def get_summary(self, analysis_result: Dict[str, Any]) -> str:
        """
        Generate a text summary of the analysis.

        Useful for displaying to users or saving to markdown.
        """
        address = analysis_result['address']
        overall_score = analysis_result['overall_score']
        overall_grade = analysis_result['overall_grade']

        property_score = analysis_result['property']['score']
        school_score = analysis_result['schools']['score']
        location_score = analysis_result['location']['score']
        investment_score = analysis_result['investment']['score']

        summary = f"""
# Property Analysis Report

## {address}

### Overall Score: {overall_score}/100 (Grade: {overall_grade})

### Category Scores:
- **Property Condition**: {property_score}/100
- **Schools**: {school_score}/100
- **Location**: {location_score}/100
- **Investment Value**: {investment_score}/100

### Key Findings:

#### Property Strengths:
{chr(10).join('- ' + s for s in analysis_result['property']['strengths'][:3])}

#### Property Concerns:
{chr(10).join('- ' + c for c in analysis_result['property']['concerns'][:3])}

#### Overall Assessment:
{analysis_result['property']['reasoning']}

---
*Analysis completed at: {analysis_result['analyzed_at']}*
"""
        return summary.strip()
