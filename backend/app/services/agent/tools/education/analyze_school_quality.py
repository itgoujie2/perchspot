"""
Analyzes school quality using GreatSchools ratings and methodology.
"""

import json
import logging
from typing import Dict, Any
from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class AnalyzeSchoolQuality(BaseTool):
    """
    Analyzes school quality based on GreatSchools ratings and methodology.

    Context: education/greatschools_methodology.md
    Input: School data with ratings, distances, and types
    Output: Comprehensive school quality analysis with scores
    """

    def __init__(self):
        super().__init__()
        # Load context on initialization
        self.load_context("education/greatschools_methodology.md")

    async def analyze(self, data: Dict[str, Any], llm_client: Any) -> Dict[str, Any]:
        """
        Analyze school quality using GreatSchools methodology.

        Expected data structure:
        {
            "address": "123 Main St, City, State",
            "schools": [
                {
                    "name": "Lincoln Elementary",
                    "type": "elementary",
                    "rating": 8,
                    "distance_miles": 0.3,
                    "student_progress_rating": 7,
                    "test_score_rating": 8,
                    "enrollment": 450
                },
                ...
            ]
        }
        """
        try:
            # Extract school data
            schools = data.get("schools", [])

            if not schools:
                return {
                    "score": 0,
                    "grade": "F",
                    "confidence": "low",
                    "analysis": "No school data available for this address.",
                    "key_findings": [],
                    "concerns": ["No schools found in the area"],
                    "data_points": {}
                }

            # Create LLM instruction
            instruction = """
Analyze the school quality for this property address using the GreatSchools methodology provided in the context.

Consider:
1. Overall GreatSchools ratings (1-10 scale) for elementary, middle, and high schools
2. Student Progress ratings (most important indicator)
3. Distance to schools (walking distance is premium for elementary)
4. How ratings compare to state/district averages
5. Impact on home value based on school quality

Provide a comprehensive analysis that helps buyers understand:
- Quality of assigned schools
- Educational opportunities for children
- Home value premium or discount due to schools
- Any concerns or red flags
- Comparison to typical expectations

Calculate an overall school quality score (0-100) based on:
- School ratings (weighted by type: elementary 40%, middle 30%, high 30%)
- Distance considerations (closer = better, especially for elementary)
- Student progress ratings (given highest weight per methodology)

Use the interpretation framework from the context to grade schools and assess impact.
"""

            # Create prompt with context
            prompt = self.create_llm_prompt(instruction, data)

            # Call LLM for analysis (OpenAI format)
            response = await llm_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            response_text = response.choices[0].message.content

            # Try to extract JSON from response
            result = self._parse_llm_response(response_text)

            # Add raw school data
            result["raw_data"] = {
                "schools": schools,
                "school_count": len(schools)
            }

            # Calculate school type breakdown
            school_types = {}
            for school in schools:
                school_type = school.get("type", "unknown")
                if school_type not in school_types:
                    school_types[school_type] = []
                school_types[school_type].append({
                    "name": school.get("name"),
                    "rating": school.get("rating"),
                    "distance": school.get("distance_miles")
                })

            result["data_points"]["school_breakdown"] = school_types

            return result

        except Exception as e:
            logger.error(f"Error in school quality analysis: {e}")
            raise

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response to extract JSON result."""
        try:
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                return result
            else:
                # If no JSON found, create structured response
                return {
                    "score": 50,
                    "grade": "C",
                    "confidence": "low",
                    "analysis": response_text,
                    "key_findings": ["Analysis completed but structured data unavailable"],
                    "concerns": [],
                    "data_points": {}
                }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from LLM response: {e}")
            return {
                "score": 50,
                "grade": "C",
                "confidence": "low",
                "analysis": response_text,
                "key_findings": ["Analysis completed but structured data unavailable"],
                "concerns": [],
                "data_points": {}
            }
