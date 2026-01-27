"""
Analyzes walkability, transit, and bike scores for property locations.
"""

import json
import logging
from typing import Dict, Any
from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class AnalyzeWalkability(BaseTool):
    """
    Analyzes walkability, transit access, and bike infrastructure.

    Context: location_commute/walkability_scores.md
    Input: Walk Score, Transit Score, Bike Score, and nearby amenities
    Output: Comprehensive mobility and accessibility analysis
    """

    def __init__(self):
        super().__init__()
        # Load context on initialization
        self.load_context("location_commute/walkability_scores.md")

    async def analyze(self, data: Dict[str, Any], llm_client: Any) -> Dict[str, Any]:
        """
        Analyze walkability and mobility using Walk Score methodology.

        Expected data structure:
        {
            "address": "123 Main St, City, State",
            "walkability_data": {
                "walk_score": 85,
                "transit_score": 92,
                "bike_score": 78,
                "description": "Very Walkable"
            },
            "nearby_amenities": {
                "grocery_stores": [
                    {"name": "Whole Foods", "distance_miles": 0.3},
                    {"name": "Safeway", "distance_miles": 0.5}
                ],
                "restaurants": [
                    {"name": "Local Bistro", "distance_miles": 0.2},
                    # ... more restaurants
                ],
                "parks": [
                    {"name": "Central Park", "distance_miles": 0.2}
                ],
                "schools": [
                    {"name": "Lincoln Elementary", "distance_miles": 0.4}
                ],
                "coffee_shops": [
                    {"name": "Starbucks", "distance_miles": 0.1}
                ]
            },
            "transit_options": [
                {
                    "type": "subway",
                    "line": "Red Line",
                    "stop": "Main St Station",
                    "distance_miles": 0.2,
                    "frequency_minutes": 6
                },
                {
                    "type": "bus",
                    "route": "Route 45",
                    "stop": "Main & Oak",
                    "distance_miles": 0.1,
                    "frequency_minutes": 15
                }
            ],
            "bike_infrastructure": {
                "has_bike_lanes": True,
                "protected_lanes": True,
                "bike_paths_nearby": ["Bay Trail", "Creek Path"],
                "bike_share_stations": 2,
                "terrain": "flat"
            },
            "area_type": "urban"  # urban, suburban, rural
        }
        """
        try:
            # Extract walkability data
            walkability_data = data.get("walkability_data", {})
            nearby_amenities = data.get("nearby_amenities", {})
            transit_options = data.get("transit_options", [])
            bike_infrastructure = data.get("bike_infrastructure", {})
            area_type = data.get("area_type", "unknown")

            if not walkability_data or "walk_score" not in walkability_data:
                return {
                    "score": 0,
                    "grade": "F",
                    "confidence": "low",
                    "analysis": "No walkability data available for this address.",
                    "key_findings": [],
                    "concerns": ["No Walk Score or transit data available"],
                    "data_points": {}
                }

            # Create LLM instruction
            instruction = """
Analyze the walkability, transit access, and bike infrastructure for this property using the methodology provided in the context.

Consider:
1. Walk Score (0-100 scale) and what it means for daily life
2. Transit Score and quality of public transportation
3. Bike Score and cycling infrastructure
4. Specific nearby amenities and their distances
5. Transit options (frequency, type, accessibility)
6. Impact on home value and lifestyle
7. Comparison to area type expectations (urban/suburban/rural)

Provide comprehensive analysis covering:

**Walkability Assessment:**
- Interpret Walk Score using the scale from context (90-100 = Walker's Paradise, etc.)
- Identify key amenities within walking distance
- Assess daily errands feasibility without a car
- Note any critical missing amenities (food deserts, etc.)

**Transit Accessibility:**
- Interpret Transit Score using the scale from context
- Evaluate transit type quality (rail > bus in most cases)
- Assess service frequency and convenience
- Calculate typical commute flexibility

**Bike Infrastructure:**
- Interpret Bike Score using the scale from context
- Evaluate bike lane quality (protected vs painted)
- Note terrain challenges (hills)
- Assess bike share and parking availability

**Lifestyle Fit:**
- Best suited for which buyer profiles? (urban professionals, families, retirees)
- Car dependency level
- Transportation cost savings potential
- Impact on property value (high walkability can add 5-20% in urban areas)

**Context Comparison:**
- How do scores compare to expectations for area type?
- Urban areas: Walk 70+, Transit 60+ expected
- Suburban: Walk 40-60, Transit 20-40 typical
- Are scores above or below typical for this location type?

Calculate an overall mobility score (0-100) based on:
- Walk Score (weighted 40%)
- Transit Score (weighted 35%)
- Bike Score (weighted 25%)
- Adjust based on area type expectations
- Premium for "15-minute neighborhood" (all essentials within 15 min walk)

Use the interpretation framework and buyer profile guidance from the context.
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

            # Add walkability metrics to data points
            result["data_points"]["walk_score"] = walkability_data.get("walk_score")
            result["data_points"]["transit_score"] = walkability_data.get("transit_score")
            result["data_points"]["bike_score"] = walkability_data.get("bike_score")

            # Count amenities
            amenity_counts = {}
            for category, items in nearby_amenities.items():
                if isinstance(items, list):
                    amenity_counts[f"{category}_count"] = len(items)

                    # Find closest in each category
                    if items:
                        closest = min(items, key=lambda x: x.get("distance_miles", 999))
                        amenity_counts[f"closest_{category}"] = f"{closest.get('name')} ({closest.get('distance_miles')}mi)"

            result["data_points"]["amenities"] = amenity_counts
            result["data_points"]["transit_options_count"] = len(transit_options)

            # Check for 15-minute neighborhood
            grocery_nearby = any(
                item.get("distance_miles", 999) <= 0.3
                for item in nearby_amenities.get("grocery_stores", [])
            )
            result["data_points"]["is_15min_neighborhood"] = grocery_nearby and walkability_data.get("walk_score", 0) >= 80

            # Add raw data
            result["raw_data"] = {
                "walkability_data": walkability_data,
                "nearby_amenities": nearby_amenities,
                "transit_options": transit_options,
                "bike_infrastructure": bike_infrastructure
            }

            return result

        except Exception as e:
            logger.error(f"Error in walkability analysis: {e}")
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
