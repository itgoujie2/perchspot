"""
School Skill - Analyzes nearby schools quality using Redfin data enriched with GreatSchools details
"""
import json
import re
from typing import Dict, Any, List
import logging

from app.services.agent.skills.base_skill import BaseSkill
from app.services.data_collectors.greatschools_service import greatschools_service

logger = logging.getLogger(__name__)


class SchoolSkill(BaseSkill):
    """
    Analyzes school quality using:
    - School data from Redfin (extracted via property_data)
    - Enriched data from GreatSchools (sub-ratings, test scores, enrollment)
    - Knowledge base context for school district info
    """

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze schools near the property.

        Args:
            address: Property address
            **kwargs: Must include 'property_data' dict with schools list

        Returns structured analysis with score, reasoning, strengths/concerns.
        """
        try:
            self._reset_cost_tracking()
            self._load_skill()

            property_data = kwargs.get('property_data', {})
            if not property_data:
                return self._error_result("No property data provided")

            schools = property_data.get('schools', [])
            logger.info(f"SchoolSkill: Got {len(schools)} schools from property data")

            # Extract city/state from address
            city, state = self._parse_city_state(address)

            # Enrich with GreatSchools data
            if schools and city and state:
                try:
                    schools = await greatschools_service.enrich_schools(schools, city, state)
                    logger.info(f"SchoolSkill: Enrichment complete, {sum(1 for s in schools if s.get('gs_rating') is not None)} schools enriched")
                except Exception as e:
                    logger.warning(f"SchoolSkill: GreatSchools enrichment failed, using Redfin data only: {e}")

            # Knowledge base search for school district context
            knowledge_queries = self._extract_school_queries(schools, city, state)
            knowledge_context, knowledge_debug = self._run_multi_query_search(knowledge_queries, limit_per_query=3)

            # Analyze
            analysis = await self._analyze_schools(address, schools, knowledge_context)

            analysis['raw_data'] = {'schools': schools, 'city': city, 'state': state}
            analysis['knowledge_debug'] = knowledge_debug
            analysis['knowledge_queries'] = knowledge_queries
            analysis['cost_summary'] = self.get_cost_summary()

            logger.info(f"SchoolSkill: Analysis complete. Score: {analysis.get('score')}, Confidence: {analysis.get('confidence')}, Cost: ${self.total_cost:.6f}")
            return analysis

        except Exception as e:
            logger.error(f"SchoolSkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    @staticmethod
    def _parse_city_state(address: str) -> tuple:
        """Extract city and state from address string."""
        parts = [p.strip() for p in address.split(',')]
        city = ""
        state = ""
        if len(parts) >= 2:
            city = parts[-2].strip() if len(parts) >= 3 else parts[0].strip()
        if len(parts) >= 2:
            # Last part is usually "STATE ZIP" or "STATE"
            state_part = parts[-1].strip()
            state_match = re.match(r'^([A-Za-z\s]+)', state_part)
            if state_match:
                state = state_match.group(1).strip()
        return city, state

    @staticmethod
    def _extract_school_queries(schools: List[Dict], city: str, state: str) -> List[str]:
        """Extract knowledge base queries from school data."""
        queries = []

        if city:
            queries.append(f"{city} school district")

        for s in schools[:5]:
            name = s.get('name', '')
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

        logger.info(f"SchoolSkill: Extracted {len(unique)} knowledge queries: {unique}")
        return unique

    async def _analyze_schools(self, address: str, schools: List[Dict], knowledge_context: str) -> Dict[str, Any]:
        """Use Claude to analyze schools with enriched data."""

        if not schools:
            return {
                'score': 0,
                'confidence': 'low',
                'reasoning': 'No school data available',
                'strengths': [],
                'concerns': ['No nearby schools found or data unavailable'],
                'details': {'schools': []},
                'raw_data': {'schools': []}
            }

        # Build detailed school summaries
        school_lines = []
        for s in schools:
            lines = [f"- **{s.get('name', 'Unknown')}**"]
            lines.append(f"  Type: {s.get('type', 'N/A')}, Grades: {s.get('grades', 'N/A')}")
            lines.append(f"  Redfin Rating: {s.get('rating', 'N/A')}/10, Distance: {s.get('distance_miles', 'N/A')} miles")

            # GreatSchools enriched data
            if s.get('gs_rating') is not None:
                lines.append(f"  GreatSchools Summary Rating: {s['gs_rating']}/10")
            if s.get('gs_test_scores_rating') is not None:
                lines.append(f"  Test Scores Rating: {s['gs_test_scores_rating']}/10")
            if s.get('gs_student_progress_rating') is not None:
                lines.append(f"  Student Progress Rating: {s['gs_student_progress_rating']}/10")
            if s.get('gs_equity_rating') is not None:
                lines.append(f"  Equity Rating: {s['gs_equity_rating']}/10")
            if s.get('gs_college_readiness_rating') is not None:
                lines.append(f"  College Readiness Rating: {s['gs_college_readiness_rating']}/10")
            if s.get('gs_enrollment') is not None:
                lines.append(f"  Enrollment: {s['gs_enrollment']} students")
            if s.get('gs_student_teacher_ratio') is not None:
                lines.append(f"  Student-Teacher Ratio: {s['gs_student_teacher_ratio']}:1")
            if s.get('gs_review_count') is not None:
                avg = f" ({s['gs_review_avg']}/5 stars)" if s.get('gs_review_avg') else ""
                lines.append(f"  Parent Reviews: {s['gs_review_count']}{avg}")

            # Test score breakdown
            test_scores = s.get('gs_test_scores', {})
            if test_scores:
                lines.append("  Test Scores by Subject:")
                for subject, scores in test_scores.items():
                    school_pct = scores.get('school_pct', 'N/A')
                    state_avg = scores.get('state_avg_pct', 'N/A')
                    lines.append(f"    {subject}: {school_pct}% proficient (state avg: {state_avg}%)")

            if s.get('gs_url'):
                lines.append(f"  GreatSchools: {s['gs_url']}")

            school_lines.append("\n".join(lines))

        schools_summary = "\n\n".join(school_lines)

        knowledge_section = ""
        if knowledge_context:
            knowledge_section = f"""
EXPERT KNOWLEDGE (from knowledge base):
{knowledge_context}
"""

        prompt = f"""
{self.skill_data['full_context']}

---

PROPERTY ADDRESS: {address}

NEARBY SCHOOLS:
{schools_summary}
{knowledge_section}
---

Using the context guidance above, analyze these schools and provide a comprehensive assessment.

IMPORTANT: Do NOT reduce the score or raise concerns due to missing GreatSchools enrichment data, missing distance data, or any other data gaps. These are data collection limitations, NOT school quality issues. Score based solely on the data that IS available.

Key considerations:
1. GreatSchools sub-ratings meaning:
   - **Test Scores**: Absolute proficiency — what % of students are meeting grade-level standards
   - **Student Progress**: Growth over time — how much students improve year-over-year (a low-rated school with high progress is improving)
   - **Equity**: Gap between subgroups — smaller gaps = more equitable outcomes
   - **College Readiness**: For high schools — AP participation, SAT/ACT scores, graduation rates
2. Compare Redfin ratings vs GreatSchools ratings (they may differ)
3. Note if GreatSchools data is missing for any school (common for private schools)
4. Test score breakdowns vs state averages are more informative than summary ratings
5. Student-teacher ratio and enrollment size

CRITICAL FORMATTING RULES:
- Strengths and concerns do NOT need to be equal in count. If schools are great, you might have 4 strengths and 1 concern. If schools are weak, you might have 1 strength and 4 concerns. Be honest.
- NEVER list missing data as a concern. "No GreatSchools data available" or "distance not provided" are NOT property concerns — they are data collection limitations. Only list actual school quality issues.
- Only mention up to 4 strengths and up to 4 concerns, but you can have fewer of either.

Provide your analysis in this JSON format:
{{
    "score": <0-100>,
    "confidence": "<high|medium|low>",
    "reasoning": "<2-3 sentences explaining the score>",
    "strengths": ["<real strength>", ...],
    "concerns": ["<real concern>", ...],
    "details": {{
        "elementary_rating": <best elementary rating or null>,
        "middle_rating": <best middle rating or null>,
        "high_rating": <best high rating or null>,
        "average_distance": <average miles>,
        "gs_enrichment_count": <number of schools with GS data>,
        "school_breakdown": [
            {{
                "name": "<school name>",
                "rating": <redfin rating>,
                "gs_rating": <greatschools rating or null>,
                "type": "<type>",
                "assessment": "<brief assessment incorporating sub-ratings and test scores>"
            }}
        ]
    }}
}}

Return ONLY valid JSON, no other text.
"""

        response_text = await self._call_claude(prompt=prompt, max_tokens=2048)
        analysis = self._parse_json_response(response_text)

        return analysis

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Return error result structure."""
        return {
            'score': 0,
            'confidence': 'low',
            'reasoning': f'Analysis failed: {error_message}',
            'strengths': [],
            'concerns': ['School analysis could not be completed'],
            'details': {},
            'error': error_message
        }
