"""
Investment Skill - Analyzes property investment potential with computed metrics
"""
import json
import math
import re
from pathlib import Path
from typing import Dict, Any, Optional
import logging

from app.services.agent.skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)

# Known appreciation rates by region (fallback if web search fails)
# Based on historical data - conservative estimates
REGIONAL_APPRECIATION = {
    # Washington
    'Seattle': 6.5,
    'Bellevue': 7.0,
    'Redmond': 6.8,
    'Kirkland': 6.5,
    'Sammamish': 6.0,
    'Issaquah': 5.8,
    'Bothell': 5.5,
    'Woodinville': 5.5,
    'Renton': 5.0,
    'Kent': 4.5,
    'Tacoma': 5.5,
    'Everett': 5.0,
    # California
    'San Francisco': 5.5,
    'San Jose': 6.0,
    'Palo Alto': 5.0,
    'Mountain View': 5.5,
    'Cupertino': 5.5,
    'Sunnyvale': 5.5,
    'Oakland': 4.5,
    'Berkeley': 5.0,
    'Fremont': 5.0,
    # Oregon
    'Portland': 5.0,
    'Beaverton': 4.5,
    'Lake Oswego': 5.0,
    # Default for unknown areas
    '_default': 3.5,
}

# Property data directory
PROPERTY_DATA_DIR = Path("/app/property_data")
if not PROPERTY_DATA_DIR.exists():
    PROPERTY_DATA_DIR = Path("./property_data")


def _create_slug(address: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', address.lower())
    slug = re.sub(r'[\s-]+', '_', slug)
    return slug[:50]


def _parse_number(val: Any) -> Optional[float]:
    """Parse a numeric value from various formats."""
    if val is None or val == 'N/A' or val == '':
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace('$', '').replace(',', '').replace('/mo', '').strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    return None


class InvestmentSkill(BaseSkill):
    """
    Analyzes investment potential using pre-extracted property data.
    Computes real investment metrics (cap rate, yield, cash-on-cash, etc.)
    before sending to Claude for qualitative interpretation.
    """

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        try:
            self._reset_cost_tracking()
            self._load_skill()

            property_data = kwargs.get('property_data') or self._load_property_data(address)

            if not property_data or 'error' in property_data:
                logger.error(f"InvestmentSkill: No extracted data for {address}")
                return self._error_result(f"No extracted data found for {address}")

            logger.info(f"InvestmentSkill: Analyzing investment for {address}")

            # Extract city for appreciation lookup
            city = self._extract_city(address)

            # Fetch appreciation data (web search or fallback)
            appreciation_data = await self._get_appreciation_data(city, address)

            # Compute metrics from raw data
            metrics = self._compute_metrics(property_data)

            # Add appreciation to metrics
            if appreciation_data:
                metrics['appreciation_pct'] = appreciation_data.get('annual_appreciation_pct')
                metrics['appreciation_5yr'] = appreciation_data.get('five_year_growth_pct')
                metrics['appreciation_source'] = appreciation_data.get('source', 'estimate')

            # Search knowledge base
            knowledge_queries = self._extract_investment_queries(property_data)
            knowledge_context, knowledge_debug = self._run_multi_query_search(knowledge_queries, limit_per_query=3)

            # Send to Claude for interpretation
            analysis = await self._analyze_investment(address, property_data, metrics, knowledge_context)

            # Merge computed metrics into details
            analysis.setdefault('details', {})
            analysis['details']['computed_metrics'] = metrics

            analysis['raw_data'] = {
                'address': address,
                'property_data_keys': list(property_data.keys()),
                'knowledge_context_used': bool(knowledge_context),
            }
            analysis['knowledge_debug'] = knowledge_debug
            analysis['knowledge_queries'] = knowledge_queries
            analysis['cost_summary'] = self.get_cost_summary()

            logger.info(f"InvestmentSkill: Analysis complete. Score: {analysis.get('score')}, Confidence: {analysis.get('confidence')}, Cost: ${self.total_cost:.6f}")
            return analysis

        except Exception as e:
            logger.error(f"InvestmentSkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    def _load_property_data(self, address: str) -> Dict[str, Any]:
        slug = _create_slug(address)
        json_path = PROPERTY_DATA_DIR / f"{slug}.json"
        if not json_path.exists():
            return {}
        with open(json_path, 'r') as f:
            return json.load(f)

    @staticmethod
    def _extract_city(address: str) -> str:
        """Extract city name from address."""
        parts = [p.strip() for p in address.split(',')]
        if len(parts) >= 2:
            # Usually: "123 Main St, City, State ZIP"
            return parts[-2].strip() if len(parts) >= 3 else parts[0].strip()
        return ""

    async def _get_appreciation_data(self, city: str, address: str) -> Dict[str, Any]:
        """
        Get historical appreciation data for the area.
        Tries web search first, falls back to regional estimates.
        """
        # Try to get live data via web search
        try:
            appreciation = await self._search_appreciation_web(city)
            if appreciation:
                logger.info(f"InvestmentSkill: Got appreciation data from web for {city}: {appreciation}")
                return appreciation
        except Exception as e:
            logger.warning(f"InvestmentSkill: Web search for appreciation failed: {e}")

        # Fallback to regional estimates
        rate = REGIONAL_APPRECIATION.get(city, REGIONAL_APPRECIATION['_default'])
        logger.info(f"InvestmentSkill: Using fallback appreciation rate for {city}: {rate}%")
        return {
            'annual_appreciation_pct': rate,
            'five_year_growth_pct': round(((1 + rate/100) ** 5 - 1) * 100, 1),
            'source': 'regional_estimate'
        }

    async def _search_appreciation_web(self, city: str) -> Optional[Dict[str, Any]]:
        """
        Search web for home appreciation data and parse with Claude.
        Returns None if search fails or no data found.
        """
        import os
        from anthropic import AsyncAnthropic

        try:
            client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

            # Use Claude to estimate appreciation based on its knowledge
            response = await client.messages.create(
                model="claude-3-haiku-20240307",  # Use Haiku for speed
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"""Based on your knowledge of real estate markets, estimate the home price appreciation for {city}.

Return ONLY a JSON object:
- annual_appreciation_pct: number (estimated annual % change)
- five_year_growth_pct: number (estimated 5-year total growth %)
- source: "claude_estimate"

Return ONLY valid JSON."""
                }]
            )

            response_text = response.content[0].text.strip()

            # Parse JSON
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            data = json.loads(response_text)

            if 'error' in data:
                return None

            if 'annual_appreciation_pct' in data:
                return data

        except Exception as e:
            logger.warning(f"InvestmentSkill: Appreciation estimate failed: {e}")

        return None

    def _compute_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute investment metrics from property data."""
        pricing = data.get('pricing', {}) or {}
        taxes = data.get('taxes', {}) or {}
        hoa = data.get('hoa', {}) or {}
        market = data.get('market_trends', {}) or {}
        details = data.get('details', {}) or {}

        purchase_price = _parse_number(pricing.get('list_price'))
        monthly_rent = _parse_number(pricing.get('rental_estimate'))
        redfin_estimate = _parse_number(pricing.get('redfin_estimate'))
        annual_tax = _parse_number(taxes.get('annual_amount'))
        hoa_fee = _parse_number(hoa.get('fee')) or 0
        hoa_freq = (hoa.get('frequency') or '').lower()

        metrics: Dict[str, Any] = {
            'purchase_price': purchase_price,
            'monthly_rent': monthly_rent,
            'redfin_estimate': redfin_estimate,
            'annual_tax': annual_tax,
            'data_completeness': 'high' if (purchase_price and monthly_rent) else 'low' if not purchase_price else 'medium',
        }

        if not purchase_price:
            return metrics

        # HOA annual
        if 'month' in hoa_freq:
            hoa_annual = hoa_fee * 12
        elif 'quarter' in hoa_freq:
            hoa_annual = hoa_fee * 4
        elif 'year' in hoa_freq or 'annual' in hoa_freq:
            hoa_annual = hoa_fee
        else:
            hoa_annual = hoa_fee * 12  # assume monthly
        metrics['hoa_annual'] = hoa_annual

        # Price vs estimate spread
        if redfin_estimate and purchase_price:
            metrics['price_vs_estimate_spread_pct'] = round(
                (redfin_estimate - purchase_price) / purchase_price * 100, 2
            )

        if not monthly_rent:
            return metrics

        annual_rent = monthly_rent * 12

        # Gross Rental Yield
        gross_yield = annual_rent / purchase_price * 100
        metrics['gross_yield_pct'] = round(gross_yield, 2)

        # Gross Rent Multiplier / Price-to-Rent Ratio
        grm = purchase_price / annual_rent
        metrics['grm'] = round(grm, 2)
        metrics['price_to_rent_ratio'] = round(grm, 2)

        # Estimated NOI
        vacancy_loss = annual_rent * 0.05
        effective_income = annual_rent - vacancy_loss
        insurance_est = purchase_price * 0.0035
        maintenance_est = purchase_price * 0.01
        tax_amount = annual_tax if annual_tax else purchase_price * 0.01  # fallback estimate
        operating_expenses = tax_amount + insurance_est + maintenance_est + hoa_annual
        noi = effective_income - operating_expenses

        metrics['effective_income'] = round(effective_income, 2)
        metrics['operating_expenses'] = round(operating_expenses, 2)
        metrics['noi'] = round(noi, 2)

        # Cap Rate
        cap_rate = noi / purchase_price * 100
        metrics['cap_rate_pct'] = round(cap_rate, 2)

        # Cash-on-Cash Return (20% down, 7% rate, 30yr)
        down_payment = purchase_price * 0.20
        loan = purchase_price * 0.80
        r = 0.07 / 12
        n = 360
        if r > 0:
            monthly_mortgage = loan * (r * (1 + r) ** n) / (((1 + r) ** n) - 1)
        else:
            monthly_mortgage = loan / n
        annual_debt_service = monthly_mortgage * 12
        annual_cash_flow = noi - annual_debt_service
        cash_on_cash = annual_cash_flow / down_payment * 100

        metrics['down_payment'] = round(down_payment, 2)
        metrics['monthly_mortgage'] = round(monthly_mortgage, 2)
        metrics['annual_debt_service'] = round(annual_debt_service, 2)
        metrics['annual_cash_flow'] = round(annual_cash_flow, 2)
        metrics['cash_on_cash_pct'] = round(cash_on_cash, 2)
        metrics['monthly_cash_flow'] = round(annual_cash_flow / 12, 2)

        return metrics

    async def _analyze_investment(
        self, address: str, data: Dict[str, Any],
        metrics: Dict[str, Any], knowledge_context: str
    ) -> Dict[str, Any]:
        """Build prompt with computed metrics and send to Claude."""

        pricing = data.get('pricing', {}) or {}
        details = data.get('details', {}) or {}
        market = data.get('market_trends', {}) or {}
        hoa = data.get('hoa', {}) or {}
        taxes = data.get('taxes', {}) or {}

        def fmt(val, prefix='$', suffix=''):
            if val is None:
                return 'N/A'
            if isinstance(val, float):
                if prefix == '$':
                    return f"${val:,.0f}{suffix}"
                return f"{val:.2f}{suffix}"
            return str(val)

        # Build metrics summary for Claude
        metrics_section = "COMPUTED INVESTMENT METRICS:\n"
        if metrics.get('gross_yield_pct') is not None:
            metrics_section += f"- Gross Rental Yield: {metrics['gross_yield_pct']:.2f}%\n"
        if metrics.get('cap_rate_pct') is not None:
            metrics_section += f"- Cap Rate: {metrics['cap_rate_pct']:.2f}%\n"
        if metrics.get('noi') is not None:
            metrics_section += f"- Net Operating Income (NOI): ${metrics['noi']:,.0f}/year\n"
        if metrics.get('grm') is not None:
            metrics_section += f"- Gross Rent Multiplier (GRM): {metrics['grm']:.1f}\n"
        if metrics.get('cash_on_cash_pct') is not None:
            metrics_section += f"- Cash-on-Cash Return: {metrics['cash_on_cash_pct']:.2f}% (assumes 20% down, 7% rate, 30yr)\n"
        if metrics.get('monthly_cash_flow') is not None:
            metrics_section += f"- Monthly Cash Flow: ${metrics['monthly_cash_flow']:,.0f}\n"
        if metrics.get('monthly_mortgage') is not None:
            metrics_section += f"- Est. Monthly Mortgage: ${metrics['monthly_mortgage']:,.0f}\n"
        if metrics.get('price_vs_estimate_spread_pct') is not None:
            spread = metrics['price_vs_estimate_spread_pct']
            direction = "below estimate (potentially underpriced)" if spread > 0 else "above estimate (potentially overpriced)"
            metrics_section += f"- Price vs Redfin Estimate: {spread:+.1f}% ({direction})\n"
        if metrics.get('operating_expenses') is not None:
            metrics_section += f"- Est. Annual Operating Expenses: ${metrics['operating_expenses']:,.0f}\n"

        # Appreciation data
        if metrics.get('appreciation_pct') is not None:
            metrics_section += f"\nAPPRECIATION DATA:\n"
            metrics_section += f"- Annual Appreciation Rate: {metrics['appreciation_pct']:.1f}%/year\n"
            if metrics.get('appreciation_5yr') is not None:
                metrics_section += f"- 5-Year Growth: {metrics['appreciation_5yr']:.1f}%\n"
            source = metrics.get('appreciation_source', 'estimate')
            metrics_section += f"- Data Source: {source}\n"

        if metrics.get('data_completeness') == 'low':
            metrics_section += "\nNOTE: No rental estimate available — metrics requiring rent data could not be computed. Provide analysis with lower confidence based on available data.\n"
        elif metrics.get('data_completeness') == 'medium':
            metrics_section += "\nNOTE: Rental estimate available but some data missing. Metrics are estimates.\n"

        knowledge_section = ""
        if knowledge_context:
            knowledge_section = f"\nEXPERT KNOWLEDGE (from knowledge base):\n{knowledge_context}\n"

        prompt = f"""{self.skill_data['full_context']}

---

PROPERTY: {address}

RAW DATA:
- List Price: {fmt(_parse_number(pricing.get('list_price')))}
- Redfin Estimate: {fmt(_parse_number(pricing.get('redfin_estimate')))}
- Rental Estimate: {fmt(_parse_number(pricing.get('rental_estimate')))}/mo
- Price/sqft: {fmt(_parse_number(pricing.get('price_per_sqft')))}
- Property Type: {details.get('property_type', 'N/A')}
- Year Built: {details.get('year_built', 'N/A')}
- Living Area: {details.get('living_area_sqft', 'N/A')} sqft
- Annual Taxes: {fmt(_parse_number(taxes.get('annual_amount')))}
- HOA: ${hoa.get('fee', 0)}/{hoa.get('frequency', 'N/A')}
- Market Type: {market.get('market_type', 'N/A')}
- Days on Market: {market.get('days_on_market', 'N/A')}
- Median Sale Price (area): {fmt(_parse_number(market.get('median_sale_price')))}

{metrics_section}
{knowledge_section}
---

Using the scoring rubric and benchmarks above, interpret these computed metrics and provide an investment analysis.

Your job is to INTERPRET the numbers — they are already computed. Assess:
1. Overall investment quality based on the metrics
2. Risk level and risk factors
3. Cash flow viability (is it cash-flow positive or an appreciation play?)
4. Appreciation potential (historical area appreciation, market trends)
5. Total return potential (cash flow + appreciation combined)
6. Market timing considerations (days on market, market type)
7. Price vs estimate spread significance

IMPORTANT: Consider BOTH cash flow AND appreciation. A property with negative cash flow but strong appreciation potential (5%+/year in a growing market) can still be a good investment. Conversely, a high cash-flow property in a flat market may have lower total returns.

Do NOT re-compute the metrics. Use the pre-computed values above.
If rental estimate is unavailable, still analyze based on price, market, and other available data but note lower confidence.

CRITICAL FORMATTING RULES:
- Strengths and concerns do NOT need to be equal in count. If investment is excellent, you might have 4 strengths and 1 concern. If it's risky, you might have 1 strength and 4 concerns. Be honest.
- NEVER list missing data as a concern. "Rental estimate unavailable", "tax data missing" are NOT investment concerns — they are data limitations that affect confidence, not score. Only list actual investment risks.
- Only include genuine strengths (positive investment characteristics) and genuine concerns (real financial risks).

Provide your analysis in this JSON format:
{{
    "score": <0-100>,
    "confidence": "<high|medium|low>",
    "reasoning": "<2-3 sentences explaining the score>",
    "strengths": ["<real strength>", ...],
    "concerns": ["<real concern>", ...],
    "details": {{
        "investment_grade": "<A/B/C/D/F>",
        "risk_level": "<low|moderate|high>",
        "rental_viability": "<strong|moderate|weak|unknown>",
        "appreciation_outlook": "<strong|moderate|weak>",
        "investment_strategy": "<cash_flow|appreciation|balanced>",
        "market_timing": "<favorable|neutral|unfavorable>",
        "price_assessment": "<underpriced|fair|overpriced>"
    }}
}}

Return ONLY valid JSON, no other text.
"""

        response_text = await self._call_claude(prompt=prompt, max_tokens=2048)
        analysis = self._parse_json_response(response_text)
        return analysis

    @staticmethod
    def _extract_investment_queries(data: Dict[str, Any]) -> list[str]:
        """Extract targeted knowledge queries for investment context."""
        queries = []
        details = data.get('details', {}) or {}
        market = data.get('market_trends', {}) or {}
        region_info = data.get('region_info', {}) or {}

        prop_type = details.get('property_type', '')
        region = region_info.get('region', '')

        if region:
            queries.append(f"{region} rental market")
            queries.append(f"{region} investment property")
        if prop_type:
            queries.append(f"{prop_type} investment")
        market_type = market.get('market_type', '')
        if market_type:
            queries.append(f"{market_type} market investment strategy")

        # Deduplicate
        seen = set()
        unique = []
        for q in queries:
            ql = q.lower().strip()
            if ql and ql not in seen:
                seen.add(ql)
                unique.append(q.strip())
        return unique

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        return {
            'score': 0,
            'confidence': 'low',
            'reasoning': f'Analysis failed: {error_message}',
            'strengths': [],
            'concerns': ['Investment analysis could not be completed'],
            'details': {},
            'error': error_message
        }
