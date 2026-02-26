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

        # 1. Load relevant property knowledge files based on property data
        file_keys = self._select_property_files(prop, details, features, hoa)
        file_context = self._load_knowledge_files(file_keys)

        # 2. Get attribute-based knowledge (matches @applies_when tags)
        attribute_context, attribute_debug = self._get_attribute_knowledge(data, limit=15)

        # 3. Merge file content + attribute context
        merged_context = self._merge_knowledge_contexts(file_context, attribute_context)

        # 4. Filter combined knowledge using LLM to select most relevant points
        knowledge_context, filter_debug = await self._filter_knowledge_with_llm(
            merged_context, property_summary, max_points=12
        )

        # Combined debug info
        knowledge_debug = {
            "file_keys": file_keys,
            "attribute_matches": attribute_debug,
            "filter_result": filter_debug,
        }

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
        analysis['knowledge_queries'] = file_keys
        analysis['cost_summary'] = self.get_cost_summary()

        logger.info(f"PropertySkill: Analysis complete. Score: {analysis.get('score')}, Confidence: {analysis.get('confidence')}, Cost: ${self.total_cost:.6f}")
        return analysis

    @staticmethod
    def _select_property_files(
        prop: Dict[str, Any],
        details: Dict[str, Any],
        features: Dict[str, Any],
        hoa: Dict[str, Any],
    ) -> list[str]:
        """
        Select relevant knowledge file keys based on property data.

        Always loads property_types. Conditionally loads others based on
        description keywords and property attributes.
        """
        file_keys = ["property_types"]

        # Always include home_age for any property with year_built
        year_built = details.get("year_built")
        if year_built:
            file_keys.append("home_age")

        # HOA
        if hoa.get("has_hoa"):
            file_keys.append("hoa")

        # Check description and features for specific topics
        description = (prop.get("description") or "").lower()
        feature_text = " ".join(
            f for key in ("interior", "exterior", "appliances")
            for f in (features.get(key) or [])
        ).lower()
        combined = f"{description} {feature_text}"

        # Roof keywords
        if any(kw in combined for kw in (
            "roof", "shingle", "asphalt", "metal roof", "tile roof",
            "slate", "gutters", "flashing", "soffit", "fascia",
        )):
            file_keys.append("roof")

        # Foundation keywords
        if any(kw in combined for kw in (
            "foundation", "slab", "crawl space", "crawlspace", "basement",
            "pier", "beam", "footing", "structural",
        )):
            file_keys.append("foundation")

        # Siding/exterior keywords
        if any(kw in combined for kw in (
            "siding", "vinyl", "fiber cement", "hardie", "stucco",
            "brick", "cladding", "wood siding",
        )):
            file_keys.append("siding")

        # HVAC keywords
        if any(kw in combined for kw in (
            "hvac", "furnace", "heat pump", "ductwork", "boiler",
            "radiant", "forced air", "mini split", "central air",
            "air conditioning", "cooling",
        )):
            file_keys.append("hvac")

        # For older homes, always include roof + foundation even if not mentioned
        if year_built and year_built < 1990:
            for key in ("roof", "foundation"):
                if key not in file_keys:
                    file_keys.append(key)

        logger.info(f"PropertySkill: Selected {len(file_keys)} knowledge files: {file_keys}")
        return file_keys

    def _merge_knowledge_contexts(self, semantic_context: str, attribute_context: str) -> str:
        """
        Merge semantic and attribute-based knowledge contexts, avoiding duplicates.

        Both contexts are formatted as:
        ### Category Name
        - Point 1
        - Point 2

        Returns merged context with unique points grouped by category.
        """
        if not semantic_context and not attribute_context:
            return ""
        if not semantic_context:
            return attribute_context
        if not attribute_context:
            return semantic_context

        from collections import defaultdict

        # Parse both contexts into category -> set of points
        by_category = defaultdict(set)

        def parse_context(ctx: str):
            current_category = ""
            for line in ctx.split('\n'):
                line = line.strip()
                if line.startswith('### '):
                    current_category = line[4:].strip()
                elif line.startswith('- ') and current_category:
                    point = line[2:].strip()
                    by_category[current_category].add(point)

        parse_context(semantic_context)
        parse_context(attribute_context)

        # Rebuild merged context
        sections = []
        for category, points in sorted(by_category.items()):
            lines = [f"### {category}"]
            for point in sorted(points):
                lines.append(f"- {point}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    async def _filter_knowledge_with_llm(
        self,
        merged_context: str,
        property_summary: str,
        max_points: int = 12,
    ) -> tuple[str, dict]:
        """
        Use a fast LLM (Haiku) to filter knowledge points to the most relevant ones.

        Args:
            merged_context: Combined semantic + attribute knowledge (markdown format)
            property_summary: Property data summary for context
            max_points: Maximum number of points to keep

        Returns:
            (filtered_context_str, debug_dict)
        """
        if not merged_context:
            return "", {"input_points": 0, "output_points": 0, "skipped": "no input"}

        # Count input points
        input_points = merged_context.count('\n- ')

        # If already under limit, skip filtering
        if input_points <= max_points:
            return merged_context, {
                "input_points": input_points,
                "output_points": input_points,
                "skipped": "under limit",
            }

        # Build numbered list of all points for easier selection
        all_points = []
        current_category = ""
        for line in merged_context.split('\n'):
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

        # Build prompt for Haiku
        points_list = "\n".join([
            f"{p['id']}. [{p['category']}] {p['text']}"
            for p in all_points
        ])

        filter_prompt = f"""You are filtering knowledge points for a property analysis. Select the {max_points} MOST RELEVANT points for this specific property.

PROPERTY CONTEXT:
{property_summary}

AVAILABLE KNOWLEDGE POINTS:
{points_list}

Select the {max_points} most relevant points by returning ONLY their numbers as a JSON array.
Prioritize:
- Points directly applicable to this property's age, type, and features
- Safety and maintenance concerns for properties of this era
- HOA considerations if applicable
- Location/neighborhood-specific info

Return ONLY a JSON array of numbers, e.g.: [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]
No explanation needed."""

        try:
            # Use Haiku for fast filtering
            response = await self._call_claude(
                prompt=filter_prompt,
                max_tokens=200,
                model="claude-3-5-haiku-20241022",
            )

            # Parse selected IDs
            response_text = response.strip()
            if response_text.startswith('['):
                selected_ids = json.loads(response_text)
            else:
                # Try to extract array from response
                match = re.search(r'\[[\d,\s]+\]', response_text)
                if match:
                    selected_ids = json.loads(match.group(0))
                else:
                    logger.warning(f"Could not parse filter response: {response_text}")
                    return merged_context, {
                        "input_points": input_points,
                        "output_points": input_points,
                        "skipped": "parse error",
                    }

            # Build filtered context
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

            logger.info(f"Knowledge filter: {input_points} -> {output_points} points")

            return filtered_context, {
                "input_points": input_points,
                "output_points": output_points,
                "selected_ids": selected_ids,
            }

        except Exception as e:
            logger.warning(f"Knowledge filtering failed: {e}, using unfiltered")
            return merged_context, {
                "input_points": input_points,
                "output_points": input_points,
                "skipped": f"error: {str(e)}",
            }

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
