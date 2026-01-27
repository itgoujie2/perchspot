"""
Property Quality Assessment Tool

Scrapes detailed property information from Zillow and analyzes physical condition,
features, and overall quality using LLM analysis.
"""
import logging
import re
from typing import Dict, Any, List
from pathlib import Path

from app.services.agent.tools.base_tool import BaseTool
from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector
from app.services.agent.tools.notes_manager import NotesManager

logger = logging.getLogger(__name__)


class AssessPropertyQuality(BaseTool):
    """
    Assess property quality based on physical condition, features, and amenities.

    This tool:
    1. Scrapes ALL property data from Redfin using computer-use (avoids CAPTCHA)
    2. Analyzes using LLM with property quality methodology
    3. Scores on 0-100 scale based on condition, features, and systems
    """

    name = "assess_property_quality"
    description = "Analyze property quality based on condition, features, and physical characteristics"

    def __init__(self):
        super().__init__()
        self.redfin_collector = ScreenshotExtractorCollector()
        self.notes_manager = NotesManager()
        logger.info("AssessPropertyQuality: Using Screenshot Extractor (Chromium + Claude Vision)")

    async def analyze(self, property_data: Dict[str, Any], llm_client: Any) -> Dict[str, Any]:
        """
        Analyze property quality.

        Args:
            property_data: Property data including address
            llm_client: OpenAI client for LLM analysis

        Returns:
            Analysis result with score, grade, findings, and concerns
        """
        try:
            address = property_data.get('address', '')
            logger.info(f"Assessing property quality for: {address}")

            # Scrape ALL data from Redfin (property details + schools)
            logger.info("Fetching ALL property data from Redfin using computer-use...")
            redfin_result = await self.redfin_collector.scrape_property(address)

            if not redfin_result.get('success'):
                error_msg = redfin_result.get('error', 'Unknown error')
                logger.error(f"Redfin scraping failed: {error_msg}")
                raise Exception(f"Failed to scrape Redfin: {error_msg}")

            # Extract data from Redfin result
            redfin_data = redfin_result.get('data', {})
            schools = redfin_result.get('schools', [])
            cost_metrics = redfin_result.get('cost_metrics', {})

            logger.info(f"Successfully scraped from Redfin:")
            logger.info(f"  - Property data: {list(redfin_data.keys())}")
            logger.info(f"  - Schools: {len(schools)}")
            logger.info(f"  - Cost: ${cost_metrics.get('total_cost', 0):.4f}")

            # Combine with existing property_data
            combined_data = {
                **property_data,
                **redfin_data,
                'nearby_schools': schools,
                'schools': schools,  # Both keys for compatibility
                'source': 'redfin',
                'scraping_cost': cost_metrics.get('total_cost', 0)
            }

            logger.info(f"Scraping complete. Extracted fields: {list(combined_data.keys())}")

            # Save raw scraped data to notes file (for reference, not in user-facing report)
            logger.info("Saving raw scraped data to notes file...")
            self.notes_manager.append_raw_scraped_data(address, combined_data, source='redfin')

            # Check if LLM analysis is enabled via environment variable
            if not settings.ENABLE_PROPERTY_LLM_ANALYSIS:
                logger.info("LLM analysis disabled via ENABLE_PROPERTY_LLM_ANALYSIS setting")

                # Return scraped data without LLM analysis (no scraped_data in result)
                result = {
                    'tool_name': self.name,
                    'score': 85,  # Placeholder score
                    'grade': 'B',  # Placeholder grade
                    'confidence': 'high',
                    'key_findings': [
                        f"Scraped {len(combined_data.get('image_urls', []))} property images",
                        f"Found {len(combined_data.get('nearby_schools', []))} nearby schools",
                        f"Property type: {combined_data.get('property_type', 'N/A')}",
                        f"Year built: {combined_data.get('year_built', 'N/A')}",
                        f"Lot size: {combined_data.get('lot_size', 'N/A')}",
                        f"Parking: {combined_data.get('parking', 'N/A')}"
                    ],
                    'concerns': [
                        "LLM analysis disabled (ENABLE_PROPERTY_LLM_ANALYSIS=false)"
                    ],
                    'analysis': f"Data collection complete - LLM analysis disabled. Enable with ENABLE_PROPERTY_LLM_ANALYSIS=true in .env",
                    'data_source': 'redfin'
                }

                logger.info(f"Returning scraped data without LLM analysis (raw data saved to notes)")
                return result

            # LLM Analysis is ENABLED - proceed with full analysis
            logger.info("LLM analysis enabled - proceeding with GPT-4o analysis")

            # Load context methodology
            context = self.load_context("property/property_quality_assessment.md")

            # Build LLM prompt focusing on description and basic stats
            prompt = self._build_analysis_prompt(combined_data, context)

            # Call LLM for analysis
            logger.info("Calling LLM for property quality analysis")
            response = await llm_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional property inspector and real estate analyst. Analyze property quality objectively based on the provided methodology. Focus on analyzing the property description and basic statistics (price per sqft, number of rooms, year built, property type, etc.) to assess overall quality."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=2000,
                temperature=0.3
            )

            response_text = response.choices[0].message.content
            logger.debug(f"LLM response: {response_text[:500]}...")

            # Parse LLM response
            result = self._parse_llm_response(response_text)
            result['tool_name'] = self.name
            result['data_source'] = 'redfin'
            # Note: scraped_data already saved to notes file, don't include in result

            logger.info(f"Property quality assessment complete. Score: {result.get('score', 0)}/100 (raw data in notes)")

            return result

        except Exception as e:
            logger.error(f"Error in property quality assessment: {e}", exc_info=True)
            return self._create_error_result(str(e))

    def _scrape_property_data_from_html(self, soup, html: str) -> Dict[str, Any]:
        """
        Extract basic property data from Zillow HTML using collector's parsing logic.
        """
        try:
            # Use collector's existing extraction strategies
            # Strategy 1: Extract from JSON (most reliable)
            property_data = self.collector._extract_from_json(soup, html)
            logger.info(f"JSON extraction: {list(property_data.keys()) if property_data else 'None'}")

            if property_data and self.collector._is_complete(property_data):
                logger.info("Successfully extracted from JSON")
                return property_data

            # Strategy 2: Multiple CSS selector fallbacks
            html_data = self.collector._extract_from_html_multi(soup)
            logger.info(f"HTML extraction: {list(html_data.keys()) if html_data else 'None'}")

            if html_data and self.collector._is_complete(html_data):
                logger.info("Successfully extracted from HTML selectors")
                return html_data

            # Strategy 3: Regex patterns and merge
            regex_data = self.collector._extract_from_regex(html)
            logger.info(f"Regex extraction: {list(regex_data.keys()) if regex_data else 'None'}")

            combined = self.collector._merge_data(property_data or {}, html_data or {}, regex_data or {})
            logger.info(f"Scraped basic property data: {list(combined.keys())}")

            return combined

        except Exception as e:
            logger.warning(f"Failed to extract property data from HTML: {e}", exc_info=True)
            return {'source': 'zillow'}

    def _extract_detailed_features_from_html(self, soup, html: str) -> Dict[str, Any]:
        """
        Extract detailed features from Zillow Facts & Features section.

        This includes:
        - Interior features (flooring, appliances, etc.)
        - Cooling/Heating systems
        - Room details
        - Special feature tags
        - Property description
        - Nearby schools with ratings and distances
        """
        try:
            features = {}

            # Extract "What's Special" section
            logger.info("Extracting What's Special section...")
            special_section = self._extract_whats_special(soup)
            if special_section:
                features.update(special_section)
            logger.info(f"What's Special complete: {list(special_section.keys()) if special_section else 'None'}")

            # Extract detailed facts from Facts & Features
            logger.info("Extracting Facts & Features...")
            facts = self._extract_facts_and_features(soup)
            if facts:
                features.update(facts)
            logger.info(f"Facts & Features complete: {list(facts.keys()) if facts else 'None'}")

            # Extract nearby schools
            logger.info("Extracting nearby schools...")
            schools = self._extract_nearby_schools(soup, html)
            if schools:
                features['nearby_schools'] = schools
            logger.info(f"Schools complete: {len(schools)} found")

            # Extract days on Zillow
            logger.info("Extracting days on Zillow...")
            days_on_zillow = self._extract_days_on_zillow(html)
            if days_on_zillow:
                features['days_on_zillow'] = days_on_zillow
            logger.info(f"Days on Zillow complete: {days_on_zillow}")

            logger.info(f"Extracted detailed features: {list(features.keys())}")
            return features

        except Exception as e:
            logger.warning(f"Failed to extract detailed features: {e}", exc_info=True)
            return {}

    def _extract_whats_special(self, soup) -> Dict[str, Any]:
        """Extract the 'What's Special' section with tags and description."""
        result = {}

        try:
            # Feature tags (EXTRA STORAGE, WORKSHOP SPACE, etc.)
            # These are often in button or tag elements
            tags = []
            tag_patterns = [
                'button[class*="Tag"]',
                '[class*="special-feature"]',
                '[class*="highlight"]'
            ]

            for pattern in tag_patterns:
                tag_elements = soup.select(pattern)
                for tag in tag_elements[:10]:  # Limit to 10 tags
                    text = tag.get_text(strip=True).upper()
                    if text and len(text) < 50:  # Reasonable tag length
                        tags.append(text)

            if tags:
                result['feature_tags'] = list(set(tags))  # Remove duplicates

            # Property description
            desc_selectors = [
                '[data-testid="description"]',
                '[class*="Text-c11n"][class*="description"]',
                'div[class*="description"]',
                '[class*="propertyDescription"]'
            ]

            for selector in desc_selectors:
                desc_elem = soup.select_one(selector)
                if desc_elem:
                    description = desc_elem.get_text(strip=True)
                    if description and len(description) > 50:  # Valid description
                        result['property_description'] = description
                        break

        except Exception as e:
            logger.debug(f"Error extracting What's Special: {e}")

        return result

    def _extract_facts_and_features(self, soup) -> Dict[str, Any]:
        """Extract structured data from Facts & Features section."""
        result = {}

        try:
            # Find all fact rows/items
            fact_selectors = [
                'li[class*="fact"]',
                '[data-testid*="fact"]',
                'div[class*="fact-item"]',
                'dt, dd'  # Definition lists common in Zillow
            ]

            all_facts = []
            for selector in fact_selectors:
                all_facts.extend(soup.select(selector))

            # Extract key-value pairs
            features_dict = {}

            for fact in all_facts:
                text = fact.get_text(strip=True)

                # Look for common patterns
                if ':' in text:
                    key, value = text.split(':', 1)
                    features_dict[key.strip().lower()] = value.strip()
                elif any(keyword in text.lower() for keyword in ['appliances', 'flooring', 'cooling', 'heating', 'windows']):
                    # Store as-is if contains important keywords
                    features_dict[text.lower()[:30]] = text

            if features_dict:
                result['detailed_features'] = features_dict

            # Extract specific important features
            html_lower = str(soup).lower()

            # Cooling
            if 'central air' in html_lower or 'ac' in html_lower:
                result['has_ac'] = True
            elif 'no cooling' in html_lower or 'cooling: none' in html_lower:
                result['has_ac'] = False

            # Flooring types
            flooring_types = []
            for floor_type in ['hardwood', 'laminate', 'carpet', 'tile', 'vinyl', 'bamboo']:
                if floor_type in html_lower:
                    flooring_types.append(floor_type.capitalize())
            if flooring_types:
                result['flooring_types'] = flooring_types

            # Appliances
            appliances = []
            for appliance in ['dishwasher', 'microwave', 'refrigerator', 'washer', 'dryer', 'stove', 'oven']:
                if appliance in html_lower:
                    appliances.append(appliance.capitalize())
            if appliances:
                result['appliances_included'] = appliances

            # Special features
            if 'fireplace' in html_lower:
                result['has_fireplace'] = True
            if 'deck' in html_lower or 'patio' in html_lower:
                result['has_outdoor_space'] = True
            if 'garage' in html_lower:
                # Try to extract garage size
                garage_match = re.search(r'(\d+)[- ]car garage', html_lower)
                if garage_match:
                    result['garage_spaces'] = int(garage_match.group(1))

        except Exception as e:
            logger.debug(f"Error extracting Facts & Features: {e}")

        return result

    def _extract_days_on_zillow(self, html: str) -> int:
        """Extract days on Zillow from HTML."""
        try:
            match = re.search(r'(\d+)\s+days?\s+on\s+zillow', html, re.IGNORECASE)
            if match:
                return int(match.group(1))
        except Exception as e:
            logger.debug(f"Error extracting days on Zillow: {e}")
        return None

    def _extract_nearby_schools(self, soup, html: str) -> List[Dict[str, Any]]:
        """
        Extract nearby schools from fully-rendered Zillow HTML.

        Now that we use Playwright, the JavaScript-rendered school data is available.

        Returns:
            List of schools with name, rating, grades, distance, and type
        """
        schools = []

        try:
            logger.info("Extracting schools from rendered HTML...")

            # Search for school names - they should now be in the rendered HTML
            # Pattern: "Elizabeth Blackwell Elementary School"
            school_keywords = [
                'Elementary School',
                'Elementary',
                'Middle School',
                'Junior High School',
                'High School'
            ]

            # Find schools by searching for text containing school keywords
            for keyword in school_keywords:
                # Use regex to find school names
                pattern = rf'([A-Z][A-Za-z\s]{2,40}?\s+{re.escape(keyword)})'
                matches = re.findall(pattern, html)

                seen_names = set()
                for school_name in matches:
                    school_name = school_name.strip()

                    # Skip if already found or too short
                    if school_name in seen_names or len(school_name) < 10:
                        continue

                    seen_names.add(school_name)

                    # Find the context around this school name (within 500 chars)
                    school_idx = html.find(school_name)
                    if school_idx == -1:
                        continue

                    context = html[max(0, school_idx-250):school_idx+500]

                    # Extract rating (e.g., "7/10" or rating-7)
                    rating = None
                    rating_match = re.search(r'(?:rating["\s:]+|>)(\d+)(?:/10)?', context, re.IGNORECASE)
                    if rating_match:
                        rating = int(rating_match.group(1))
                        # Ratings should be 1-10
                        if rating > 10:
                            rating = None

                    # Extract distance (e.g., "0.8 mi" or "2.1 mi")
                    distance = None
                    distance_match = re.search(r'([\d.]+)\s*mi', context)
                    if distance_match:
                        distance = float(distance_match.group(1))

                    # Extract grades (e.g., "K-5", "6-8", "9-12")
                    grades = None
                    grades_match = re.search(r'(?:Grades?:?\s*)?([K\d][-–]\d+)', context, re.IGNORECASE)
                    if grades_match:
                        grades = grades_match.group(1)

                    # Determine school type
                    school_type = 'unknown'
                    name_lower = school_name.lower()
                    if 'elementary' in name_lower:
                        school_type = 'elementary'
                    elif 'middle' in name_lower or 'junior' in name_lower:
                        school_type = 'middle'
                    elif 'high' in name_lower:
                        school_type = 'high'

                    schools.append({
                        'name': school_name,
                        'rating': rating,
                        'grades': grades,
                        'distance_miles': distance,
                        'type': school_type,
                        'source': 'zillow_greatschools'
                    })

            # Remove duplicates and limit to reasonable number
            unique_schools = []
            seen = set()
            for school in schools:
                if school['name'] not in seen:
                    seen.add(school['name'])
                    unique_schools.append(school)
                if len(unique_schools) >= 10:  # Limit to 10 schools
                    break

            if unique_schools:
                logger.info(f"Successfully extracted {len(unique_schools)} schools:")
                for school in unique_schools:
                    logger.info(f"  - {school['name']}: {school['rating']}/10, {school['distance_miles']} mi, {school['grades']}")
            else:
                logger.warning("No schools found in rendered HTML")

            return unique_schools

        except Exception as e:
            logger.error(f"Error extracting schools: {e}", exc_info=True)
            return []

    def _build_analysis_prompt(self, data: Dict[str, Any], context: str) -> str:
        """Build the LLM analysis prompt."""

        # Format property data for prompt
        # Format price with commas
        price = data.get('price', 'N/A')
        if isinstance(price, (int, float)):
            price_str = f"${price:,.0f}"
        else:
            price_str = str(price)

        # Format square feet with commas
        sqft = data.get('square_feet', 'N/A')
        if isinstance(sqft, (int, float)):
            sqft_str = f"{sqft:,.0f}"
        else:
            sqft_str = str(sqft)

        property_summary = f"""
**Property Address**: {data.get('address', 'Unknown')}
**Price**: {price_str}
**Bedrooms**: {data.get('bedrooms', 'N/A')}
**Bathrooms**: {data.get('bathrooms', 'N/A')}
**Square Feet**: {sqft_str}
**Year Built**: {data.get('year_built', 'N/A')}
**Property Type**: {data.get('property_type', 'N/A')}
**Days on Zillow**: {data.get('days_on_zillow', 'N/A')}
"""

        # Add description if available
        if data.get('property_description'):
            property_summary += f"\n**Description**:\n{data['property_description'][:500]}\n"

        # Add feature tags
        if data.get('feature_tags'):
            property_summary += f"\n**Special Features**: {', '.join(data['feature_tags'])}\n"

        # Add systems info
        systems_info = []
        if 'has_ac' in data:
            systems_info.append(f"AC: {'Yes' if data['has_ac'] else 'No'}")
        if 'garage_spaces' in data:
            systems_info.append(f"Garage: {data['garage_spaces']}-car")
        if 'has_fireplace' in data:
            systems_info.append("Fireplace: Yes")
        if 'has_outdoor_space' in data:
            systems_info.append("Deck/Patio: Yes")

        if systems_info:
            property_summary += f"\n**Systems & Features**: {', '.join(systems_info)}\n"

        # Add flooring and appliances
        if data.get('flooring_types'):
            property_summary += f"\n**Flooring**: {', '.join(data['flooring_types'])}\n"
        if data.get('appliances_included'):
            property_summary += f"\n**Appliances**: {', '.join(data['appliances_included'])}\n"

        # Add nearby schools
        if data.get('nearby_schools'):
            property_summary += f"\n**Nearby Schools**:\n"
            for school in data['nearby_schools']:
                school_info = f"  - {school['name']}"
                if school.get('rating'):
                    school_info += f" (Rating: {school['rating']}/10)"
                if school.get('grades'):
                    school_info += f" Grades: {school['grades']}"
                if school.get('distance_miles'):
                    school_info += f" Distance: {school['distance_miles']} mi"
                property_summary += school_info + "\n"

        prompt = f"""
{context}

---

# PROPERTY TO ANALYZE

{property_summary}

---

# YOUR TASK

Analyze this property's quality using the methodology above. Provide:

1. **Overall Quality Score**: 0-100
2. **Letter Grade**: A, B, C, D, or F
3. **Confidence Level**: high, medium, or low (based on data completeness)
4. **Key Findings**: List 3-5 positive attributes that add value
5. **Concerns**: List 2-4 items needing attention, updates, or potential issues
6. **Analysis**: 2-3 paragraph explanation of the score

Format your response as:

**SCORE**: [number]
**GRADE**: [letter]
**CONFIDENCE**: [level]

**KEY_FINDINGS**:
- [finding 1]
- [finding 2]
- [finding 3]

**CONCERNS**:
- [concern 1]
- [concern 2]

**ANALYSIS**:
[Your detailed analysis here]
"""

        return prompt

    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured format."""
        result = {
            'score': 0,
            'grade': 'F',
            'confidence': 'low',
            'key_findings': [],
            'concerns': [],
            'analysis': ''
        }

        try:
            # Extract score
            score_match = re.search(r'\*\*SCORE\*\*:?\s*(\d+)', response, re.IGNORECASE)
            if score_match:
                result['score'] = int(score_match.group(1))

            # Extract grade
            grade_match = re.search(r'\*\*GRADE\*\*:?\s*([A-F][+-]?)', response, re.IGNORECASE)
            if grade_match:
                result['grade'] = grade_match.group(1).upper()

            # Extract confidence
            conf_match = re.search(r'\*\*CONFIDENCE\*\*:?\s*(\w+)', response, re.IGNORECASE)
            if conf_match:
                result['confidence'] = conf_match.group(1).lower()

            # Extract key findings
            findings_section = re.search(r'\*\*KEY_FINDINGS\*\*:?(.*?)(?=\*\*CONCERNS\*\*|\*\*ANALYSIS\*\*|$)',
                                        response, re.DOTALL | re.IGNORECASE)
            if findings_section:
                findings_text = findings_section.group(1)
                findings = re.findall(r'-\s*(.+?)(?=\n-|\n\n|$)', findings_text, re.DOTALL)
                result['key_findings'] = [f.strip() for f in findings if f.strip()]

            # Extract concerns
            concerns_section = re.search(r'\*\*CONCERNS\*\*:?(.*?)(?=\*\*ANALYSIS\*\*|$)',
                                        response, re.DOTALL | re.IGNORECASE)
            if concerns_section:
                concerns_text = concerns_section.group(1)
                concerns = re.findall(r'-\s*(.+?)(?=\n-|\n\n|$)', concerns_text, re.DOTALL)
                result['concerns'] = [c.strip() for c in concerns if c.strip()]

            # Extract analysis
            analysis_section = re.search(r'\*\*ANALYSIS\*\*:?(.*?)$', response, re.DOTALL | re.IGNORECASE)
            if analysis_section:
                result['analysis'] = analysis_section.group(1).strip()

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")

        return result

    def _create_error_result(self, error_msg: str) -> Dict[str, Any]:
        """Create error result."""
        return {
            'tool_name': self.name,
            'score': 0,
            'grade': 'F',
            'confidence': 'low',
            'analysis': f"Error during analysis: {error_msg}",
            'key_findings': [],
            'concerns': [f"Analysis failed: {error_msg}"],
            'data_points': {},
            'error': error_msg
        }
