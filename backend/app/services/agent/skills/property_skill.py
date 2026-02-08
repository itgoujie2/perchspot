"""
Property Skill - Analyzes property condition from extracted listing data
"""
import json
import re
from pathlib import Path
from typing import Dict, Any
import logging

from app.services.agent.skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)

# Property data directory — matches screenshot_extractor_collector.py output
PROPERTY_DATA_DIR = Path("/app/property_data")
if not PROPERTY_DATA_DIR.exists():
    PROPERTY_DATA_DIR = Path("./property_data")


def _create_slug(address: str) -> str:
    """Create a filename-safe slug from address (mirrors screenshot_extractor_collector)."""
    slug = re.sub(r'[^\w\s-]', '', address.lower())
    slug = re.sub(r'[\s-]+', '_', slug)
    return slug[:50]


class PropertySkill(BaseSkill):
    """
    Analyzes property condition using pre-extracted Redfin data.
    No live scraping — uses JSON files from property_data/ directory.
    """

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze property condition.

        Args:
            address: Property address
            **kwargs: Optional 'property_data' dict to skip file lookup

        Returns structured analysis with score, reasoning, strengths/concerns.
        """
        try:
            self._reset_cost_tracking()
            self._load_skill()

            # Use provided data or load from file
            property_data = kwargs.get('property_data') or self._load_property_data(address)

            if not property_data or 'error' in property_data:
                logger.error(f"PropertySkill: No extracted data for {address}")
                return self._error_result(f"No extracted data found for {address}")

            logger.info(f"PropertySkill: Analyzing property for {address}")

            analysis = await self._analyze_property(address, property_data)
            return analysis

        except Exception as e:
            logger.error(f"PropertySkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    def _load_property_data(self, address: str) -> Dict[str, Any]:
        """Load pre-extracted property data from JSON file."""
        slug = _create_slug(address)
        json_path = PROPERTY_DATA_DIR / f"{slug}.json"

        if not json_path.exists():
            logger.warning(f"Property data not found: {json_path}")
            return {}

        with open(json_path, 'r') as f:
            data = json.load(f)

        logger.info(f"Loaded property data from {json_path}")
        return data

    async def _analyze_property(self, address: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build prompt from extracted data + skill context + knowledge, send to Claude."""

        # Extract sections
        prop = data.get('property', {}) or {}
        pricing = data.get('pricing', {}) or {}
        details = data.get('details', {}) or {}
        features = data.get('features', {}) or {}
        hoa = data.get('hoa', {}) or {}
        taxes = data.get('taxes', {}) or {}
        climate = data.get('climate_risks', {}) or {}
        market = data.get('market_trends', {}) or {}
        images = data.get('images', {}) or {}
        region_info = data.get('region_info', {}) or {}

        # Format price values safely
        def fmt_price(val):
            if val and val != 'N/A':
                try:
                    return f"${int(val):,}"
                except (ValueError, TypeError):
                    return str(val)
            return 'N/A'

        property_summary = f"""
ADDRESS: {address}
STATUS: {prop.get('status', 'N/A')}
MLS: {prop.get('mls_number', 'N/A')}

DESCRIPTION:
{prop.get('description', 'No description available')}

PRICING:
- List Price: {fmt_price(pricing.get('list_price'))}
- Redfin Estimate: {fmt_price(pricing.get('redfin_estimate'))}
- Price/sqft: {fmt_price(pricing.get('price_per_sqft'))}
- Rental Estimate: {fmt_price(pricing.get('rental_estimate'))}/mo

PROPERTY DETAILS:
- Type: {details.get('property_type', 'N/A')}
- Year Built: {details.get('year_built', 'N/A')}
- Bedrooms: {details.get('bedrooms', 'N/A')}
- Bathrooms: {details.get('bathrooms', 'N/A')}
- Living Area: {details.get('living_area_sqft', 'N/A')} sqft
- Lot Size: {details.get('lot_size_sqft', 'N/A')} sqft
- Parking: {details.get('parking', 'N/A')}
- Stories: {details.get('stories', 'N/A')}

FEATURES:
- Interior: {', '.join(features.get('interior', [])) or 'N/A'}
- Exterior: {', '.join(features.get('exterior', [])) or 'N/A'}
- Appliances: {', '.join(features.get('appliances', [])) or 'N/A'}
- Heating/Cooling: {features.get('heating_cooling') or 'N/A'}

HOA:
- Has HOA: {hoa.get('has_hoa', 'N/A')}
- Fee: ${hoa.get('fee', 0)}/{hoa.get('frequency', 'N/A')}

TAXES:
- Annual: {fmt_price(taxes.get('annual_amount'))}

CLIMATE RISKS (for display only — DO NOT factor these into the score or concerns):
- Flood: {climate.get('flood', 'N/A')}
- Fire: {climate.get('fire', 'N/A')}
- Heat: {climate.get('heat', 'N/A')}
- Wind: {climate.get('wind', 'N/A')}
(Note: Climate risk data from listing sites is often exaggerated and unreliable. Show it in the report for reference but do NOT use it to penalize the property score or raise concerns.)

MARKET:
- Market Type: {market.get('market_type', 'N/A')}
- Days on Market: {market.get('days_on_market', 'N/A')}

PHOTOS: {images.get('photo_count', 'N/A')} photos

REGION: {region_info.get('region', 'N/A')}
"""

        # Extract meaningful search terms from property data
        knowledge_queries = self._extract_property_queries(prop, details, features, climate, region_info)
        knowledge_context, knowledge_debug = self._run_multi_query_search(knowledge_queries, limit_per_query=3)

        knowledge_section = ""
        if knowledge_context:
            knowledge_section = f"""
EXPERT KNOWLEDGE (from knowledge base):
{knowledge_context}
"""

        prompt = f"""
{self.skill_data['full_context']}

---

EXTRACTED PROPERTY DATA:
{property_summary}
{knowledge_section}
---

Using the scoring rubric and context above, provide a comprehensive property analysis.

Evaluate:
1. Property type pros/cons for this market
2. Age-related concerns and upcoming maintenance costs
3. Lot size and characteristics assessment
4. Parking adequacy
5. HOA assessment (if applicable)
6. DO NOT factor climate risk data into your score or concerns — the data is unreliable and exaggerated
7. Days on market signal
8. Photo count confidence signal
9. Any red flags from the available data
10. Overall property quality and value proposition

IMPORTANT: The features section (interior, exterior, appliances, heating_cooling) is often empty because it cannot be reliably extracted from listing screenshots. Do NOT penalize the property or raise concerns about missing features/HVAC data — this is a data extraction limitation, not a property deficiency. Focus your analysis on the data that IS available.

CRITICAL FORMATTING RULES:
- Strengths and concerns do NOT need to be equal in count. If the property is excellent, you might have 4 strengths and 1 concern. If it has issues, you might have 1 strength and 4 concerns. Be honest about what you find.
- NEVER list missing data as a concern. "Features data unavailable", "HVAC info not provided", "lot size unknown" are NOT property deficiencies — they are extraction limitations. Only list actual property issues.
- Only include genuine strengths and genuine concerns based on the data that IS available.

Provide your analysis in this JSON format:
{{
    "score": <0-100>,
    "confidence": "<high|medium|low>",
    "reasoning": "<2-3 sentences explaining the score>",
    "strengths": ["<real strength>", ...],
    "concerns": ["<real concern>", ...],
    "details": {{
        "property_type_assessment": "<assessment of property type for this market>",
        "age_assessment": "<age-related analysis with cost estimates>",
        "lot_assessment": "<lot size and characteristics>",
        "parking_assessment": "<parking adequacy>",
        "hoa_assessment": "<HOA analysis if applicable, else 'No HOA'>",
        "maintenance_risk": "<low|medium|high>",
        "missing_data": ["<field 1>", "<field 2>"]
    }}
}}

Return ONLY valid JSON, no other text.
"""

        response_text = await self._call_claude(prompt=prompt, max_tokens=2048)
        analysis = self._parse_json_response(response_text)

        analysis['raw_data'] = {
            'address': address,
            'property_data_keys': list(data.keys()),
            'knowledge_context_used': bool(knowledge_context),
        }
        analysis['knowledge_debug'] = knowledge_debug
        analysis['knowledge_queries'] = knowledge_queries
        analysis['cost_summary'] = self.get_cost_summary()

        logger.info(f"PropertySkill: Analysis complete. Score: {analysis.get('score')}, Confidence: {analysis.get('confidence')}, Cost: ${self.total_cost:.6f}")
        return analysis

    @staticmethod
    def _extract_property_queries(
        prop: Dict[str, Any],
        details: Dict[str, Any],
        features: Dict[str, Any],
        climate: Dict[str, Any],
        region_info: Dict[str, Any],
    ) -> list[str]:
        """
        Extract meaningful search terms from property data for targeted knowledge queries.

        Looks for: builder/developer names, architectural styles, specific features,
        property type, climate concerns, neighborhood, etc.
        """
        queries = []
        description = (prop.get('description') or '').strip()

        # 1. Extract builder/developer names from description
        #    Common patterns: "Built by X", "X Homes", "by X Construction", "X Development"
        builder_patterns = [
            r'(?:built by|by|from|builder[:\s]+)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+(?:Homes?|Construction|Development|Builders?|Properties|Group|LLC|Inc))',
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2}\s+(?:Homes?|Construction|Development|Builders?))',
        ]
        for pat in builder_patterns:
            for match in re.findall(pat, description):
                queries.append(match.strip())
            if queries:
                break  # stop at first pattern that finds something

        # 2. Architectural styles from description
        style_keywords = [
            'farmhouse', 'craftsman', 'colonial', 'victorian', 'mid-century',
            'modern', 'contemporary', 'ranch', 'tudor', 'cape cod', 'bungalow',
            'split-level', 'a-frame', 'mediterranean', 'spanish', 'art deco',
            'prairie', 'dutch colonial', 'georgian', 'townhouse', 'brownstone',
        ]
        desc_lower = description.lower()
        for style in style_keywords:
            if style in desc_lower:
                queries.append(f"{style} home construction quality")

        # 3. Notable features that merit knowledge lookup
        notable_features = [
            'adu', 'accessory dwelling', 'mother-in-law', 'granny flat',
            'solar', 'ev charger', 'heat pump', 'mini split', 'tankless',
            'septic', 'well water', 'propane', 'oil heat',
            'foundation crack', 'knob and tube', 'polybutylene', 'aluminum wiring',
            'asbestos', 'lead paint', 'radon',
        ]
        all_feature_text = desc_lower + ' ' + ' '.join(
            f.lower() for fl in [features.get('interior', []), features.get('exterior', []),
                                  features.get('appliances', [])]
            for f in fl
        ) + ' ' + (features.get('heating_cooling') or '').lower()

        for feat in notable_features:
            if feat in all_feature_text:
                queries.append(feat)

        # 4. Climate risks — skip entirely, data is unreliable

        # 5. Property type + region combo
        prop_type = details.get('property_type', '')
        region = region_info.get('region', '')
        if prop_type and region:
            queries.append(f"{prop_type} in {region}")

        # 6. Specific neighborhood/community names from description
        #    Look for phrases like "in [Name] community", "[Name] neighborhood", "[Name] subdivision"
        community_patterns = [
            r'(?:in|at|of)\s+(?:the\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+(?:community|neighborhood|subdivision|development|village|estates?|heights|ridge|park)',
        ]
        for pat in community_patterns:
            for match in re.findall(pat, description):
                queries.append(match.strip())

        # Deduplicate while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            q_lower = q.lower().strip()
            if q_lower and q_lower not in seen:
                seen.add(q_lower)
                unique_queries.append(q.strip())

        logger.info(f"PropertySkill: Extracted {len(unique_queries)} knowledge queries: {unique_queries}")
        return unique_queries

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
