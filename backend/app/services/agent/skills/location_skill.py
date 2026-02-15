"""
Location Skill - Analyzes location quality, commute, neighborhood, and region
"""
import os
import re
from typing import Dict, Any, List, Optional
import logging

from app.services.agent.skills.base_skill import BaseSkill
from app.services.data_collectors.google_maps_service import google_maps_service

logger = logging.getLogger(__name__)

# Path to hot_areas.md relative to this file
HOT_AREAS_PATH = os.path.join(
    os.path.dirname(__file__),
    '..', '..', '..', '..', '.claude', 'skills', 'location-analysis', 'hot_areas.md'
)


def parse_hot_areas(filepath: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Parse hot_areas.md into {region: [{name, address}, ...]}.
    """
    regions: Dict[str, List[Dict[str, str]]] = {}
    current_region: Optional[str] = None

    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('## '):
                    current_region = line[3:].strip()
                    regions[current_region] = []
                elif line.startswith('- ') and current_region is not None:
                    # Format: "- Name: Address"
                    match = re.match(r'^- (.+?):\s*(.+)$', line)
                    if match:
                        regions[current_region].append({
                            'name': match.group(1).strip(),
                            'address': match.group(2).strip(),
                        })
    except FileNotFoundError:
        logger.warning(f"hot_areas.md not found at {filepath}")

    return regions


def detect_region(address: str, regions: Dict[str, List[Dict[str, str]]]) -> Optional[str]:
    """
    Detect which metro region an address belongs to based on city/state keywords.
    """
    addr_lower = address.lower()

    # More specific sub-regions checked first; order matters for overlapping keywords
    region_keywords = {
        # WA - Eastside
        'Eastside': ['bellevue', 'redmond', 'kirkland', 'sammamish', 'issaquah',
                      'woodinville', 'bothell', 'kenmore', 'mercer island'],
        # WA - Seattle Core
        'Seattle Core': ['seattle', 'shoreline', 'burien', 'tukwila'],
        # WA - North Sound
        'North Sound': ['lynnwood', 'everett', 'edmonds', 'mountlake terrace',
                        'mill creek', 'mukilteo', 'marysville'],
        # WA - South King County
        'South King County': ['kent', 'auburn', 'federal way', 'renton', 'covington',
                              'maple valley', 'enumclaw'],
        # WA - Tacoma
        'Tacoma': ['tacoma', 'lakewood', 'puyallup', 'university place'],
        # CA - San Francisco
        'San Francisco': ['san francisco'],
        # CA - Peninsula & South Bay
        'Peninsula & South Bay': ['palo alto', 'mountain view', 'sunnyvale', 'cupertino',
                                  'santa clara', 'san jose', 'menlo park', 'redwood city',
                                  'san mateo', 'milpitas', 'campbell', 'los gatos',
                                  'saratoga', 'fremont'],
        # CA - East Bay
        'East Bay': ['oakland', 'berkeley', 'hayward', 'walnut creek', 'concord',
                     'pleasanton', 'livermore', 'san ramon', 'dublin'],
        # OR - Portland Core
        'Portland Core': ['portland'],
        # OR - Portland Suburbs
        'Portland Suburbs': ['beaverton', 'hillsboro', 'gresham', 'lake oswego',
                             'tigard', 'tualatin', 'wilsonville'],
    }

    for region in regions:
        keywords = region_keywords.get(region, [])
        for kw in keywords:
            if kw in addr_lower:
                return region

    return None


class LocationSkill(BaseSkill):
    """
    Analyzes location quality using:
    - Neighborhood characteristics
    - Region identification and commute times to hot areas
    - Walkability
    - Nearby amenities
    """

    def __init__(self):
        super().__init__()
        self._hot_areas = parse_hot_areas(os.path.normpath(HOT_AREAS_PATH))

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze location quality.

        Args:
            address: Property address
            **kwargs: Optional params like work_location for commute analysis

        Returns structured analysis with score, reasoning, strengths/concerns.
        """
        try:
            self._reset_cost_tracking()
            self._load_skill()

            work_location = kwargs.get('work_location')

            logger.info(f"LocationSkill: Analyzing location for {address}")

            # Detect region and get commute times to ALL hot areas
            region = detect_region(address, self._hot_areas)
            commute_data: List[Dict[str, Any]] = []

            all_destinations = []
            for r, destinations in self._hot_areas.items():
                for d in destinations:
                    all_destinations.append({**d, "_region": r})

            if all_destinations:
                logger.info(f"LocationSkill: Detected region '{region}', fetching commute times to {len(all_destinations)} hot areas")
                commute_data = await google_maps_service.get_commute_times(address, all_destinations)
                for i, c in enumerate(commute_data):
                    c["sub_region"] = all_destinations[i]["_region"]

            analysis = await self._analyze_location(address, work_location, region, commute_data)

            return analysis

        except Exception as e:
            logger.error(f"LocationSkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    async def _analyze_location(
        self,
        address: str,
        work_location: Optional[str],
        region: Optional[str],
        commute_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze location characteristics with region and commute context."""

        commute_section = ""
        if commute_data:
            lines = []
            for c in commute_data:
                drive = f"{c['drive_minutes']} min" if c.get('drive_minutes') is not None else "N/A"
                transit = f"{c['transit_minutes']} min" if c.get('transit_minutes') is not None else "N/A"
                lines.append(f"  - {c['name']}: drive {drive}, transit {transit}")
            commute_section = f"\nCOMMUTE TO HOT AREAS ({region}):\n" + "\n".join(lines)

        # Build location summary for knowledge filtering
        location_summary = f"""ADDRESS: {address}
REGION: {region or 'Unknown'}
WORK LOCATION: {work_location or 'Not provided'}
{commute_section}"""

        # Query knowledge base with targeted location queries
        knowledge_queries = self._extract_location_queries_preliminary(address, region, commute_data)
        knowledge_context, knowledge_debug = self._run_multi_query_search(
            knowledge_queries, limit_per_query=6, min_score=0.25
        )

        # Filter knowledge using LLM
        filtered_context, filter_debug = await self._filter_location_knowledge(
            knowledge_context, location_summary, max_points=10
        )

        knowledge_section = ""
        if filtered_context:
            knowledge_section = f"""
EXPERT KNOWLEDGE (from knowledge base):
{filtered_context}
"""

        prompt = f"""
{self.skill_data['full_context']}

---

PROPERTY ADDRESS: {address}
WORK LOCATION: {work_location or 'Not provided'}
DETECTED REGION: {region or 'Unknown'}
{commute_section}
{knowledge_section}
---

Using the context guidance above, analyze this property's location quality.

Consider:
1. Neighborhood characteristics (urban/suburban/rural) — identify the specific neighborhood name
2. Accessibility and walkability
3. Commute considerations (use the commute data above if available)
4. General location desirability
5. Region context and proximity to employment centers

CRITICAL FORMATTING RULES:
- Strengths and concerns do NOT need to be equal in count. If location is excellent, you might have 4 strengths and 0-1 concerns. If location has issues, you might have 1 strength and 4 concerns. Be honest.
- NEVER list missing data as a concern. "Work location not provided", "walkability data unavailable" are NOT location deficiencies — they are data limitations. Only list actual location issues.
- Only include genuine strengths and genuine concerns.

Provide your analysis in this JSON format:
{{
    "score": <0-100>,
    "confidence": "<high|medium|low>",
    "reasoning": "<2-3 sentences explaining the score>",
    "strengths": ["<real strength>", ...],
    "concerns": ["<real concern>", ...],
    "details": {{
        "region": "{region or 'Unknown'}",
        "neighborhood": "<identified neighborhood name>",
        "neighborhood_type": "<urban/suburban/rural>",
        "walkability_assessment": "<description>",
        "commute_assessment": "<description>",
        "commute_to_hot_areas": {self._format_commute_json_template(commute_data)},
        "amenities_nearby": ["<amenity 1>", "<amenity 2>"]
    }}
}}

Return ONLY valid JSON, no other text.
"""

        response_text = await self._call_claude(prompt=prompt, max_tokens=2048)
        analysis = self._parse_json_response(response_text)

        # Ensure region and commute data are in the output even if Claude omits them
        details = analysis.setdefault('details', {})
        details.setdefault('region', region or 'Unknown')
        if commute_data and 'commute_to_hot_areas' not in details:
            details['commute_to_hot_areas'] = commute_data

        analysis['raw_data'] = {
            'address': address,
            'work_location': work_location,
            'region': region,
            'commute_data': commute_data,
        }
        analysis['knowledge_debug'] = {
            "queries": knowledge_debug,
            "filter_result": filter_debug,
        }
        analysis['knowledge_queries'] = knowledge_queries
        analysis['cost_summary'] = self.get_cost_summary()

        logger.info(f"LocationSkill: Analysis complete. Score: {analysis.get('score')}, Confidence: {analysis.get('confidence')}, Cost: ${self.total_cost:.6f}")

        return analysis

    def _extract_location_queries_preliminary(
        self,
        address: str,
        region: str | None,
        commute_data: list,
    ) -> list[str]:
        """
        Extract location queries before main analysis (can't use analysis results yet).
        """
        queries = []

        # Region
        if region:
            queries.append(f"{region} housing market")
            queries.append(f"{region} neighborhoods")

        # City from address
        parts = [p.strip() for p in address.split(',')]
        if len(parts) >= 2:
            city = parts[1].strip()
            if city:
                queries.append(f"{city} neighborhood quality")
                queries.append(f"{city} location considerations")

        # Nearby hot areas from commute data (sorted by drive time)
        sorted_commute = sorted(
            [c for c in commute_data if c.get('drive_minutes') is not None],
            key=lambda c: c.get('drive_minutes', 999)
        )
        for c in sorted_commute[:3]:
            name = c.get('name', '')
            if name:
                queries.append(name)

        # Deduplicate
        seen = set()
        unique = []
        for q in queries:
            ql = q.lower().strip()
            if ql and ql not in seen:
                seen.add(ql)
                unique.append(q.strip())

        logger.info(f"LocationSkill: Extracted {len(unique)} preliminary knowledge queries: {unique}")
        return unique

    async def _filter_location_knowledge(
        self,
        knowledge_context: str,
        location_summary: str,
        max_points: int = 10,
    ) -> tuple[str, dict]:
        """
        Use Haiku to filter location knowledge to most relevant points.
        """
        import json
        import re

        if not knowledge_context:
            return "", {"input_points": 0, "output_points": 0, "skipped": "no input"}

        input_points = knowledge_context.count('\n- ')

        if input_points <= max_points:
            return knowledge_context, {
                "input_points": input_points,
                "output_points": input_points,
                "skipped": "under limit",
            }

        # Build numbered list
        all_points = []
        current_category = ""
        for line in knowledge_context.split('\n'):
            line = line.strip()
            if line.startswith('### '):
                current_category = line[4:].strip()
            elif line.startswith('- ') and current_category:
                point_text = line[2:].strip()
                all_points.append({
                    "id": len(all_points) + 1,
                    "category": current_category,
                    "text": point_text,
                })

        points_list = "\n".join([
            f"{p['id']}. [{p['category']}] {p['text']}"
            for p in all_points
        ])

        filter_prompt = f"""You are filtering knowledge points for a location analysis. Select the {max_points} MOST RELEVANT points.

LOCATION CONTEXT:
{location_summary}

AVAILABLE KNOWLEDGE POINTS:
{points_list}

Select the {max_points} most relevant points by returning ONLY their numbers as a JSON array.
Prioritize:
- Neighborhood-specific information
- Commute and transportation insights
- Regional market context
- Walkability and amenity information

Return ONLY a JSON array of numbers, e.g.: [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
No explanation needed."""

        try:
            response = await self._call_claude(
                prompt=filter_prompt,
                max_tokens=200,
                model="claude-3-5-haiku-20241022",
            )

            response_text = response.strip()
            if response_text.startswith('['):
                selected_ids = json.loads(response_text)
            else:
                match = re.search(r'\[[\d,\s]+\]', response_text)
                if match:
                    selected_ids = json.loads(match.group(0))
                else:
                    logger.warning(f"Could not parse location filter response: {response_text}")
                    return knowledge_context, {
                        "input_points": input_points,
                        "output_points": input_points,
                        "skipped": "parse error",
                    }

            from collections import defaultdict
            by_category = defaultdict(list)

            for p in all_points:
                if p["id"] in selected_ids:
                    by_category[p["category"]].append(p["text"])

            sections = []
            for category, texts in sorted(by_category.items()):
                lines = [f"### {category}"]
                for text in texts:
                    lines.append(f"- {text}")
                sections.append("\n".join(lines))

            filtered_context = "\n\n".join(sections)
            output_points = sum(len(texts) for texts in by_category.values())

            logger.info(f"Location knowledge filter: {input_points} -> {output_points} points")

            return filtered_context, {
                "input_points": input_points,
                "output_points": output_points,
                "selected_ids": selected_ids,
            }

        except Exception as e:
            logger.warning(f"Location knowledge filtering failed: {e}, using unfiltered")
            return knowledge_context, {
                "input_points": input_points,
                "output_points": input_points,
                "skipped": f"error: {str(e)}",
            }

    @staticmethod
    def _format_commute_json_template(commute_data: List[Dict[str, Any]]) -> str:
        """Format commute data as a JSON array string for the prompt template."""
        if not commute_data:
            return "[]"
        import json
        return json.dumps([
            {"name": c["name"], "drive_minutes": c.get("drive_minutes"), "transit_minutes": c.get("transit_minutes")}
            for c in commute_data
        ])

    @staticmethod
    def _extract_location_queries(
        address: str,
        region: str | None,
        commute_data: list,
        analysis_result: Dict[str, Any],
    ) -> list[str]:
        """
        Extract meaningful search terms for location knowledge queries.

        Looks for: neighborhood name, region, nearby employers/hot areas,
        school districts, transit corridors, etc.
        """
        queries = []

        # 1. Neighborhood name (from analysis result if Claude identified it)
        details = analysis_result.get('details', {})
        neighborhood = details.get('neighborhood', '')
        if neighborhood and neighborhood.lower() not in ('unknown', 'n/a', ''):
            queries.append(neighborhood)

        # 2. Region
        if region:
            queries.append(f"{region} housing market")

        # 3. City from address
        #    Simple extraction: split by comma, second part is usually city
        parts = [p.strip() for p in address.split(',')]
        if len(parts) >= 2:
            city = parts[1].strip()
            if city:
                queries.append(f"{city} neighborhood quality")

        # 4. Nearby hot areas / employers from commute data (sorted by drive time)
        sorted_commute = sorted(
            [c for c in commute_data if c.get('drive_minutes') is not None],
            key=lambda c: c.get('drive_minutes', 999)
        )
        for c in sorted_commute[:3]:  # top 3 closest
            name = c.get('name', '')
            if name:
                queries.append(name)

        # 5. Walkability / transit context if notable
        neighborhood_type = details.get('neighborhood_type', '')
        if neighborhood_type:
            queries.append(f"{neighborhood_type} neighborhood walkability")

        # Deduplicate
        seen = set()
        unique = []
        for q in queries:
            ql = q.lower().strip()
            if ql and ql not in seen:
                seen.add(ql)
                unique.append(q.strip())

        logger.info(f"LocationSkill: Extracted {len(unique)} knowledge queries: {unique}")
        return unique

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Return error result structure."""
        return {
            'score': 0,
            'confidence': 'low',
            'reasoning': f'Analysis failed: {error_message}',
            'strengths': [],
            'concerns': ['Location analysis could not be completed'],
            'details': {},
            'error': error_message
        }
