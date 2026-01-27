"""
Analyzes crime risk using NeighborhoodScout methodology.
"""

import json
import logging
from typing import Dict, Any
from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class AnalyzeCrimeRisk(BaseTool):
    """
    Analyzes crime risk based on NeighborhoodScout methodology.

    Context: neighborhood/crime_risk_assessment.md
    Input: Crime statistics and risk ratings
    Output: Comprehensive crime risk analysis with safety assessment
    """

    def __init__(self):
        super().__init__()
        # Load context on initialization
        self.load_context("neighborhood/crime_risk_assessment.md")

    async def analyze(self, data: Dict[str, Any], llm_client: Any) -> Dict[str, Any]:
        """
        Analyze crime risk using NeighborhoodScout methodology.

        Expected data structure:
        {
            "address": "123 Main St, City, State",
            "crime_data": {
                "overall_crime_risk": 65,  # 1-100 scale (100 = safest)
                "violent_crime_risk": 70,
                "property_crime_risk": 60,
                "crime_rate_per_1000": 18.5,
                "victim_chance": "1 in 54",
                "city_average": 45,
                "national_average": 50,
                "trend": "improving",  # improving/stable/declining
                "crime_types": {
                    "burglary": 3.2,
                    "larceny": 8.5,
                    "vehicle_theft": 2.1,
                    "assault": 2.5,
                    "robbery": 1.2
                }
            }
        }
        """
        try:
            # Extract crime data
            crime_data = data.get("crime_data", {})

            if not crime_data or "overall_crime_risk" not in crime_data:
                return {
                    "score": 0,
                    "grade": "F",
                    "confidence": "low",
                    "analysis": "No crime data available for this address.",
                    "key_findings": [],
                    "concerns": ["No crime statistics available"],
                    "data_points": {}
                }

            # Create LLM instruction
            instruction = """
Analyze the crime risk for this property address using the NeighborhoodScout methodology provided in the context.

Consider:
1. Overall crime risk rating (1-100 scale, where 100 is safest)
2. Violent crime vs. property crime breakdown
3. Comparison to city and national averages
4. Crime trends (improving, stable, or declining)
5. Specific crime types and their prevalence
6. Impact on home value (high crime can reduce values 10-30%)

Provide a comprehensive analysis that helps buyers understand:
- Overall safety level for the neighborhood
- Specific crime concerns to be aware of
- How it compares to other neighborhoods
- Impact on livability and property values
- Recommendations for different buyer profiles (families, young professionals, investors)

Calculate an overall crime safety score (0-100) that reflects:
- The NeighborhoodScout crime risk rating (primary factor)
- Trend direction (improving adds points, declining reduces points)
- Violent vs. property crime balance (violent crime weighted more heavily)
- Comparison to averages (better than average adds points)

Use the safety categories and interpretation framework from the context.
Red flags: Risk below 30, declining trends, violent crime spikes
Positive indicators: Risk above 75, improving trends, below city average
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

            # Add raw crime data
            result["raw_data"] = crime_data

            # Add specific crime metrics to data points
            result["data_points"]["crime_risk_rating"] = crime_data.get("overall_crime_risk")
            result["data_points"]["violent_crime_risk"] = crime_data.get("violent_crime_risk")
            result["data_points"]["property_crime_risk"] = crime_data.get("property_crime_risk")
            result["data_points"]["vs_city_average"] = crime_data.get("overall_crime_risk", 0) - crime_data.get("city_average", 0)
            result["data_points"]["vs_national_average"] = crime_data.get("overall_crime_risk", 0) - crime_data.get("national_average", 0)
            result["data_points"]["trend"] = crime_data.get("trend", "unknown")

            return result

        except Exception as e:
            logger.error(f"Error in crime risk analysis: {e}")
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
