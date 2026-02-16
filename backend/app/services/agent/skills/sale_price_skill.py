"""
Sale Price Prediction Skill - Predicts likely final sale price range

Considers:
- Property characteristics
- Days on market (key signal)
- Market conditions (buyer's vs seller's)
- Mortgage rate environment (fetched from web)
- Seasonal factors
- Comparables and neighborhood pricing
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging
import httpx
from bs4 import BeautifulSoup

from app.services.agent.skills.base_skill import BaseSkill
from app.config import settings

logger = logging.getLogger(__name__)

# Cache for mortgage rates (avoid hitting web on every request)
_mortgage_rate_cache: Dict[str, Tuple[float, datetime]] = {}
MORTGAGE_RATE_CACHE_HOURS = 4  # Refresh every 4 hours


async def _fetch_mortgage_rate_from_web() -> Optional[float]:
    """
    Fetch current best mortgage rates from the web.
    Returns the best available 30-year fixed rate for well-qualified buyers.
    """
    try:
        async with httpx.AsyncClient(
            headers={'User-Agent': settings.USER_AGENT},
            timeout=10.0,
            follow_redirects=True
        ) as client:
            # Try Bankrate's mortgage rates page
            response = await client.get('https://www.bankrate.com/mortgages/current-interest-rates/')

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')

                # Look for 30-year fixed rate - Bankrate shows rates in specific elements
                # Try multiple selectors as page structure may change
                rate_text = None

                # Try finding rate in common patterns
                for selector in [
                    '[data-testid="30-year-fixed-rate"]',
                    '.rate-value',
                    'td:contains("30-year fixed")',
                ]:
                    elem = soup.select_one(selector)
                    if elem:
                        rate_text = elem.get_text(strip=True)
                        break

                # Also try regex pattern matching in page text
                if not rate_text:
                    # Look for patterns like "6.25%" or "6.5%" near "30-year"
                    text = soup.get_text()
                    match = re.search(r'30[- ]?year[^%]*?(\d+\.?\d*)\s*%', text, re.IGNORECASE)
                    if match:
                        rate_text = match.group(1)

                if rate_text:
                    # Clean and parse
                    rate_str = re.sub(r'[^\d.]', '', rate_text)
                    if rate_str:
                        rate = float(rate_str)
                        if 3.0 <= rate <= 12.0:  # Sanity check
                            logger.info(f"Fetched mortgage rate from web: {rate}%")
                            return rate

            # Try alternative source: Freddie Mac PMMS (Primary Mortgage Market Survey)
            # This is the authoritative source but updates weekly
            response = await client.get('https://www.freddiemac.com/pmms')
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                # Look for 30-year rate
                rate_elem = soup.select_one('.rate-30yr, .pmms-rate')
                if rate_elem:
                    rate_text = rate_elem.get_text(strip=True)
                    rate_str = re.sub(r'[^\d.]', '', rate_text)
                    if rate_str:
                        rate = float(rate_str)
                        if 3.0 <= rate <= 12.0:
                            logger.info(f"Fetched mortgage rate from Freddie Mac: {rate}%")
                            return rate

    except Exception as e:
        logger.warning(f"Failed to fetch mortgage rate from web: {e}")

    return None


async def get_current_mortgage_rate() -> Tuple[float, str]:
    """
    Get current mortgage rate with caching.
    Returns (rate, source) tuple.
    """
    cache_key = "30yr_fixed"

    # Check cache
    if cache_key in _mortgage_rate_cache:
        cached_rate, cached_time = _mortgage_rate_cache[cache_key]
        hours_old = (datetime.now() - cached_time).total_seconds() / 3600
        if hours_old < MORTGAGE_RATE_CACHE_HOURS:
            logger.debug(f"Using cached mortgage rate: {cached_rate}% ({hours_old:.1f}h old)")
            return cached_rate, "cached_web"

    # Fetch from web
    rate = await _fetch_mortgage_rate_from_web()
    if rate:
        _mortgage_rate_cache[cache_key] = (rate, datetime.now())
        return rate, "web_fetch"

    # Fall back to reasonable default for well-qualified buyers
    # As of early 2026, rates are typically 6-7%
    logger.info("Using fallback mortgage rate: 6.5%")
    return 6.5, "fallback"

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
        cleaned = val.replace('$', '').replace(',', '').replace('/mo', '').replace('%', '').strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    return None


def _get_current_month() -> int:
    """Get current month (1-12)."""
    return datetime.now().month


def _get_season(month: int) -> str:
    """Map month to season."""
    if month in [3, 4, 5]:
        return "spring"
    elif month in [6, 7, 8]:
        return "summer"
    elif month in [9, 10, 11]:
        return "fall"
    else:
        return "winter"


class SalePriceSkill(BaseSkill):
    """
    Predicts the likely final sale price for a property.

    Uses pre-computed baseline metrics and market data, then sends to
    Claude for interpretation and range prediction.
    """

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        try:
            self._reset_cost_tracking()
            self._load_skill()

            property_data = kwargs.get('property_data') or self._load_property_data(address)

            if not property_data or 'error' in property_data:
                logger.error(f"SalePriceSkill: No extracted data for {address}")
                return self._error_result(f"No extracted data found for {address}")

            logger.info(f"SalePriceSkill: Analyzing sale price for {address}")

            # Compute baseline and metrics
            baseline_metrics = self._compute_baseline_metrics(property_data)

            # Get market context from knowledge base
            knowledge_queries = self._extract_market_queries(property_data)
            knowledge_context, knowledge_debug = self._run_multi_query_search(
                knowledge_queries, limit_per_query=3
            )

            # Fetch real-time market conditions (mortgage rates, market type)
            market_snapshot = await self._fetch_market_conditions(property_data)

            # Send to Claude for prediction
            analysis = await self._predict_sale_price(
                address, property_data, baseline_metrics, market_snapshot, knowledge_context
            )

            # Merge baseline metrics into details
            analysis.setdefault('details', {})
            analysis['details']['baseline_used'] = baseline_metrics.get('baseline_source')
            analysis['details']['baseline_value'] = baseline_metrics.get('baseline')
            analysis['details']['dom'] = baseline_metrics.get('dom')

            analysis['market_snapshot'] = market_snapshot
            analysis['raw_data'] = {
                'address': address,
                'property_data_keys': list(property_data.keys()),
                'knowledge_context_used': bool(knowledge_context),
            }
            analysis['knowledge_debug'] = knowledge_debug
            analysis['knowledge_queries'] = knowledge_queries
            analysis['cost_summary'] = self.get_cost_summary()

            logger.info(
                f"SalePriceSkill: Analysis complete. Score: {analysis.get('score')}, "
                f"Confidence: {analysis.get('confidence')}, Cost: ${self.total_cost:.6f}"
            )
            return analysis

        except Exception as e:
            logger.error(f"SalePriceSkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    def _load_property_data(self, address: str) -> Dict[str, Any]:
        slug = _create_slug(address)
        json_path = PROPERTY_DATA_DIR / f"{slug}.json"
        if not json_path.exists():
            return {}
        with open(json_path, 'r') as f:
            return json.load(f)

    def _compute_baseline_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute baseline price and related metrics."""
        pricing = data.get('pricing', {}) or {}
        market = data.get('market_trends', {}) or {}
        details = data.get('details', {}) or {}

        redfin_estimate = _parse_number(pricing.get('redfin_estimate'))
        list_price = _parse_number(pricing.get('list_price'))
        rental_estimate = _parse_number(pricing.get('rental_estimate'))
        median_price = _parse_number(market.get('median_sale_price'))

        # Days on market
        dom = _parse_number(market.get('days_on_market'))

        # Determine baseline
        # Key insight: For new listings (low DOM), list price is the market test.
        # Redfin estimates are often conservative, especially for luxury properties.
        baseline = None
        baseline_source = None

        if list_price and redfin_estimate:
            spread_pct = (list_price - redfin_estimate) / list_price * 100

            # For new listings (DOM < 14), trust list price more - market hasn't rejected it
            if dom is not None and dom < 14:
                # Use weighted average favoring list price for new listings
                baseline = list_price * 0.7 + redfin_estimate * 0.3
                baseline_source = 'weighted_new_listing'
            # For luxury properties where Redfin often underestimates
            elif list_price > 1_500_000 and spread_pct > 5:
                # Redfin tends to undervalue luxury - use weighted average
                baseline = list_price * 0.6 + redfin_estimate * 0.4
                baseline_source = 'weighted_luxury'
            # If list price is much higher than Redfin (>10%), likely overpriced
            elif spread_pct > 10:
                baseline = redfin_estimate
                baseline_source = 'redfin_estimate'
            # Normal case: prices are close, use Redfin
            else:
                baseline = redfin_estimate
                baseline_source = 'redfin_estimate'
        elif list_price:
            baseline = list_price
            baseline_source = 'list_price'
        elif redfin_estimate:
            baseline = redfin_estimate
            baseline_source = 'redfin_estimate'
        elif median_price:
            # Derive from neighborhood median using sqft ratio
            sqft = _parse_number(details.get('living_area_sqft'))
            avg_sqft = 1800  # Assume average for area
            if sqft:
                baseline = median_price * (sqft / avg_sqft)
            else:
                baseline = median_price
            baseline_source = 'derived_from_median'

        metrics = {
            'baseline': baseline,
            'baseline_source': baseline_source,
            'list_price': list_price,
            'redfin_estimate': redfin_estimate,
            'rental_estimate': rental_estimate,
            'median_sale_price': median_price,
            'dom': dom,
            'sqft': _parse_number(details.get('living_area_sqft')),
            'year_built': details.get('year_built'),
            'bedrooms': details.get('bedrooms'),
            'bathrooms': details.get('bathrooms'),
        }

        # Price vs estimate spread
        if redfin_estimate and list_price:
            metrics['list_vs_estimate_pct'] = round(
                (redfin_estimate - list_price) / list_price * 100, 2
            )

        return metrics

    async def _fetch_market_conditions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch real-time market conditions using Claude.

        Returns market snapshot with mortgage rate, market type, season.
        """
        market = data.get('market_trends', {}) or {}
        location = data.get('location', {}) or {}
        region_info = data.get('region_info', {}) or {}

        # Extract city/region for context
        city = region_info.get('city', '')
        state = region_info.get('state', '')
        region = region_info.get('region', '')

        if not city and not region:
            # Try to extract from address
            prop = data.get('property', {}) or {}
            addr = prop.get('address', {}) or {}
            city = addr.get('city', '')
            state = addr.get('state', '')

        # Get market type from extracted data if available
        market_type = market.get('market_type', '')

        # Get current season
        month = _get_current_month()
        season = _get_season(month)

        # Fetch mortgage rate from web (with caching)
        mortgage_rate, rate_source = await get_current_mortgage_rate()
        logger.info(f"Mortgage rate: {mortgage_rate}% (source: {rate_source})")

        # Use Claude only for local market conditions (not mortgage rate)
        try:
            prompt = f"""Based on your knowledge of current real estate market conditions (as of early 2026), provide market data for {city}, {state if state else region}.

Return ONLY a JSON object with these fields:
- market_type: string ("seller's", "buyer's", or "balanced")
- local_yoy_trend: string (e.g., "prices up 3% YoY" or "prices flat YoY")
- rate_direction: string ("rising", "falling", or "stable")

Return ONLY valid JSON, no explanation."""

            response = await self._call_claude(
                prompt=prompt,
                max_tokens=150,
                model="claude-3-haiku-20240307"  # Use Haiku for speed/cost
            )

            # Parse response
            response_text = response.strip()
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            market_data = json.loads(response_text)

            return {
                'mortgage_rate': mortgage_rate,
                'mortgage_rate_source': rate_source,
                'market_type': market_data.get('market_type', market_type or 'balanced'),
                'season': season,
                'local_trend': market_data.get('local_yoy_trend', 'unknown'),
                'rate_direction': market_data.get('rate_direction', 'stable'),
                'source': 'web_and_claude'
            }

        except Exception as e:
            logger.warning(f"SalePriceSkill: Market conditions fetch failed: {e}")
            # Return with web-fetched rate
            return {
                'mortgage_rate': mortgage_rate,
                'mortgage_rate_source': rate_source,
                'market_type': market_type or 'balanced',
                'season': season,
                'local_trend': 'unknown',
                'rate_direction': 'stable',
                'source': 'web_only'
            }

    async def _predict_sale_price(
        self,
        address: str,
        data: Dict[str, Any],
        baseline_metrics: Dict[str, Any],
        market_snapshot: Dict[str, Any],
        knowledge_context: str
    ) -> Dict[str, Any]:
        """Build prompt and get sale price prediction from Claude."""

        pricing = data.get('pricing', {}) or {}
        details = data.get('details', {}) or {}
        market = data.get('market_trends', {}) or {}
        location = data.get('location', {}) or {}
        hoa = data.get('hoa', {}) or {}
        schools = data.get('schools', []) or []

        # Document analyses (inspection reports, HOA documents)
        inspection_analysis = data.get('inspection_analysis', {}) or {}
        hoa_analysis = data.get('hoa_analysis', {}) or {}

        def fmt(val, prefix='$', suffix=''):
            if val is None:
                return 'N/A'
            if isinstance(val, float):
                if prefix == '$':
                    return f"${val:,.0f}{suffix}"
                return f"{val:.2f}{suffix}"
            return str(val)

        # Build baseline info
        baseline_section = "BASELINE CALCULATION:\n"
        baseline_section += f"- Baseline Source: {baseline_metrics.get('baseline_source', 'unknown')}\n"
        baseline_section += f"- Baseline Value: {fmt(baseline_metrics.get('baseline'))}\n"
        baseline_section += f"- List Price: {fmt(baseline_metrics.get('list_price'))}\n"
        baseline_section += f"- Redfin Estimate: {fmt(baseline_metrics.get('redfin_estimate'))}\n"
        if baseline_metrics.get('list_vs_estimate_pct') is not None:
            spread = baseline_metrics['list_vs_estimate_pct']
            direction = "below estimate" if spread > 0 else "above estimate"
            baseline_section += f"- List vs Estimate: {spread:+.1f}% ({direction})\n"

        # Market snapshot section
        market_section = "\nMARKET CONDITIONS:\n"
        rate_source = market_snapshot.get('mortgage_rate_source', '')
        rate_note = f" (from {rate_source})" if rate_source else ""
        market_section += f"- Mortgage Rate (30yr best available): {market_snapshot.get('mortgage_rate', 'N/A')}%{rate_note}\n"
        market_section += f"- Market Type: {market_snapshot.get('market_type', 'N/A')}\n"
        market_section += f"- Season: {market_snapshot.get('season', 'N/A')}\n"
        market_section += f"- Local Trend: {market_snapshot.get('local_trend', 'N/A')}\n"
        market_section += f"- Rate Direction: {market_snapshot.get('rate_direction', 'N/A')}\n"

        # DOM analysis
        dom = baseline_metrics.get('dom')
        dom_section = "\nDAYS ON MARKET:\n"
        if dom is not None:
            dom_section += f"- DOM: {int(dom)} days\n"
            if dom < 7:
                dom_section += "- Signal: HOT - likely sells at or above ask\n"
            elif dom < 30:
                dom_section += "- Signal: Normal pace - sells near ask\n"
            elif dom < 60:
                dom_section += "- Signal: Starting to stale - negotiation room\n"
            else:
                dom_section += "- Signal: STALE - significant discount likely\n"
        else:
            dom_section += "- DOM: Unknown (may be new listing or data not available)\n"
            dom_section += "- Signal: NEUTRAL - missing DOM should lower confidence, NOT price\n"

        # Property details
        prop_section = "\nPROPERTY DETAILS:\n"
        prop_section += f"- Type: {details.get('property_type', 'N/A')}\n"
        prop_section += f"- Beds: {details.get('bedrooms', 'N/A')}\n"
        prop_section += f"- Baths: {details.get('bathrooms', 'N/A')}\n"
        prop_section += f"- Sqft: {details.get('living_area_sqft', 'N/A')}\n"
        prop_section += f"- Year Built: {details.get('year_built', 'N/A')}\n"
        prop_section += f"- Lot Size: {details.get('lot_size_sqft', 'N/A')} sqft\n"

        # Location scores
        loc_section = "\nLOCATION SCORES:\n"
        loc_section += f"- Walk Score: {location.get('walkability_score', 'N/A')}\n"
        loc_section += f"- Transit Score: {location.get('transit_score', 'N/A')}\n"
        loc_section += f"- Bike Score: {location.get('bike_score', 'N/A')}\n"

        # Schools summary
        school_section = "\nSCHOOLS:\n"
        if schools:
            avg_rating = sum(
                s.get('rating', s.get('score', 0)) or 0
                for s in schools
            ) / len(schools) if schools else 0
            school_section += f"- Average Rating: {avg_rating:.1f}/10\n"
            school_section += f"- Number of Schools: {len(schools)}\n"
        else:
            school_section += "- No school data available\n"

        # HOA
        hoa_section = "\nHOA:\n"
        hoa_fee = _parse_number(hoa.get('fee'))
        if hoa_fee:
            hoa_section += f"- Fee: ${hoa_fee:,.0f}/{hoa.get('frequency', 'mo')}\n"
        else:
            hoa_section += "- No HOA or N/A\n"

        # Document analyses (inspection/HOA reports if user uploaded)
        docs_section = ""
        if inspection_analysis or hoa_analysis:
            docs_section = "\nUPLOADED DOCUMENT ANALYSES:\n"

            if inspection_analysis:
                docs_section += "\n[INSPECTION REPORT]\n"
                insp_details = inspection_analysis.get('details', {})
                total_repairs = insp_details.get('total_estimated_repairs')
                if total_repairs:
                    docs_section += f"- Estimated Repairs Needed: {total_repairs}\n"
                issues = insp_details.get('issues', [])
                if issues:
                    major_issues = [i for i in issues if i.get('severity') in ['major', 'critical', 'safety']]
                    if major_issues:
                        docs_section += f"- Major Issues Found: {len(major_issues)}\n"
                        for issue in major_issues[:3]:  # Top 3 major issues
                            docs_section += f"  * {issue.get('description', 'Unknown issue')}"
                            if issue.get('estimated_cost'):
                                docs_section += f" (~{issue.get('estimated_cost')})"
                            docs_section += "\n"
                insp_score = inspection_analysis.get('score')
                if insp_score is not None:
                    docs_section += f"- Property Condition Score: {insp_score}/100\n"
                docs_section += ">>> PRICE IMPACT: Subtract estimated repair costs from predicted price\n"

            if hoa_analysis:
                docs_section += "\n[HOA DOCUMENT]\n"
                hoa_details = hoa_analysis.get('details', {})
                special_assessments = hoa_details.get('special_assessments', {})
                if special_assessments and special_assessments.get('pending'):
                    docs_section += f"- PENDING SPECIAL ASSESSMENT: {special_assessments.get('pending')}\n"
                    docs_section += ">>> PRICE IMPACT: Special assessments reduce effective value\n"
                reserve_fund = hoa_details.get('reserve_fund', {})
                if reserve_fund:
                    reserve_pct = reserve_fund.get('percent_funded')
                    if reserve_pct and reserve_pct < 50:
                        docs_section += f"- LOW RESERVE FUND: {reserve_pct}% funded (risk of future assessments)\n"
                litigation = hoa_details.get('pending_litigation')
                if litigation:
                    docs_section += f"- PENDING LITIGATION: {litigation}\n"
                hoa_score = hoa_analysis.get('score')
                if hoa_score is not None:
                    docs_section += f"- HOA Health Score: {hoa_score}/100\n"

        # Knowledge context
        knowledge_section = ""
        if knowledge_context:
            knowledge_section = f"\nEXPERT MARKET KNOWLEDGE:\n{knowledge_context}\n"

        prompt = f"""{self.skill_data['full_context']}

---

PROPERTY: {address}

{baseline_section}
{market_section}
{dom_section}
{prop_section}
{loc_section}
{school_section}
{hoa_section}
{docs_section}
{knowledge_section}
---

Using the guidelines above, predict the likely final sale price for this property.

Your job is to:
1. Start from the baseline value (may be weighted between list price and Redfin estimate)
2. Apply adjustments based on DOM, market conditions, property features
3. If inspection/HOA documents were analyzed, incorporate those findings:
   - Subtract estimated repair costs from predicted price
   - Factor in special assessments and HOA financial health
4. Provide a predicted midpoint and realistic range:
   - Standard properties: +/- 3-5%
   - Luxury properties (>$1.5M): +/- 5-8% (more price variability)
5. List the key adjustment factors (3-6 most impactful)
6. Explain your reasoning in 2-3 sentences
7. Assign a confidence score (0-100) based on data quality

CRITICAL PRICING INSIGHTS:
- For NEW listings (DOM < 14), the list price hasn't been rejected by the market yet - respect it more
- Redfin estimates tend to be CONSERVATIVE, especially for luxury properties (often 5-10% low)
- Low DOM + list price > Redfin estimate = sellers know something, don't undervalue
- High DOM (>45) = market HAS spoken, price likely needs to come down

IMPORTANT - MISSING DATA HANDLING:
- Missing DOM or other data should LOWER YOUR CONFIDENCE SCORE, NOT the predicted price
- Unknown data = wider price range and lower confidence, but don't arbitrarily reduce the midpoint
- Only adjust price DOWN for concrete negative signals (high DOM, inspection issues, etc.)
- Note missing data in concerns, but don't penalize price for lack of information

Provide your analysis in this JSON format:
{{
    "score": <0-100 confidence score>,
    "confidence": "<high|medium|low>",
    "predicted_sale_price": <number - midpoint estimate>,
    "price_range": {{
        "low": <number - lower bound (-5%)>,
        "high": <number - upper bound (+5%)>
    }},
    "vs_list_price_pct": <number - predicted vs list price %>,
    "vs_redfin_estimate_pct": <number or null - predicted vs redfin estimate %>,
    "reasoning": "<2-3 sentences explaining the prediction>",
    "adjustment_factors": [
        {{"factor": "<description>", "direction": "<up|down>", "impact": "<significant|moderate|slight>"}},
        ...
    ],
    "strengths": ["<positive pricing factors>", ...],
    "concerns": ["<pricing risks>", ...],
    "details": {{
        "prediction_methodology": "<brief methodology note>"
    }}
}}

Return ONLY valid JSON, no other text.
"""

        response_text = await self._call_claude(prompt=prompt, max_tokens=2048)
        analysis = self._parse_json_response(response_text)
        return analysis

    @staticmethod
    def _extract_market_queries(data: Dict[str, Any]) -> List[str]:
        """Extract targeted knowledge queries for market context."""
        queries = []
        region_info = data.get('region_info', {}) or {}
        market = data.get('market_trends', {}) or {}
        details = data.get('details', {}) or {}

        region = region_info.get('region', '')
        city = region_info.get('city', '')
        prop_type = details.get('property_type', '')

        if region:
            queries.append(f"{region} real estate market")
        if city:
            queries.append(f"{city} home prices")
        if prop_type:
            queries.append(f"{prop_type} pricing trends")

        market_type = market.get('market_type', '')
        if market_type:
            queries.append(f"{market_type} market negotiation")

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
            'predicted_sale_price': None,
            'price_range': {'low': None, 'high': None},
            'vs_list_price_pct': None,
            'vs_redfin_estimate_pct': None,
            'reasoning': f'Analysis failed: {error_message}',
            'adjustment_factors': [],
            'strengths': [],
            'concerns': ['Sale price prediction could not be completed'],
            'details': {},
            'error': error_message
        }
