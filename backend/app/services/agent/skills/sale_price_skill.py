"""
Sale Price Prediction Skill - Predicts likely final sale price range

Considers:
- Property characteristics
- Days on market (key signal)
- Market conditions (buyer's vs seller's)
- Mortgage rate environment (fetched from web)
- Hot zip codes (premium markets)
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
MORTGAGE_RATE_CACHE_HOURS = 24  # Refresh daily - rates don't change frequently

# Cache for hot zip codes (loaded once from knowledge file)
_hot_zip_codes_cache: Optional[Dict[str, Dict[str, Any]]] = None

# Hot zip code tiers and their price premiums
# Note: Ultra-premium markets are already priced at peak - less room for appreciation
# High-demand markets see more bidding wars and sell above ask
HOT_ZIP_PREMIUM = {
    1: {'min': 0.01, 'max': 0.03, 'label': 'Ultra-Premium'},  # Tier 1: +1% to +3% (already at peak)
    2: {'min': 0.05, 'max': 0.08, 'label': 'High Demand'},     # Tier 2: +5% to +8% (bidding wars)
    3: {'min': 0.02, 'max': 0.04, 'label': 'Emerging Hot'},    # Tier 3: +2% to +4% (growing demand)
}


def _load_hot_zip_codes() -> Dict[str, Dict[str, Any]]:
    """
    Load and parse hot zip codes from knowledge file.
    Returns dict mapping zip_code -> {tier, area, notes, region}
    """
    global _hot_zip_codes_cache
    if _hot_zip_codes_cache is not None:
        return _hot_zip_codes_cache

    # Try multiple paths for the knowledge file
    possible_paths = [
        Path("/app/knowledge/location/HOT_ZIP_CODES_2025_2026.md"),
        Path("./knowledge/location/HOT_ZIP_CODES_2025_2026.md"),
        Path("./backend/knowledge/location/HOT_ZIP_CODES_2025_2026.md"),
    ]

    content = None
    for path in possible_paths:
        if path.exists():
            content = path.read_text()
            logger.info(f"Loaded hot zip codes from {path}")
            break

    if not content:
        logger.warning("Hot zip codes knowledge file not found")
        _hot_zip_codes_cache = {}
        return _hot_zip_codes_cache

    hot_zips = {}
    current_region = ""
    current_tier = 0

    for line in content.split('\n'):
        line = line.strip()

        # Detect region headers (## Seattle / Bellevue, ## San Francisco Bay Area, etc.)
        if line.startswith('## ') and not line.startswith('## Price') and not line.startswith('## How'):
            current_region = line[3:].strip()
            continue

        # Detect tier headers (### Tier 1, ### Tier 2, ### Tier 3)
        if line.startswith('### Tier 1'):
            current_tier = 1
            continue
        elif line.startswith('### Tier 2'):
            current_tier = 2
            continue
        elif line.startswith('### Tier 3'):
            current_tier = 3
            continue

        # Parse table rows with zip codes (| 98039 | Medina | ...)
        if line.startswith('|') and current_tier > 0:
            parts = [p.strip() for p in line.split('|')]
            # Filter out empty parts
            parts = [p for p in parts if p]
            if len(parts) >= 2 and parts[0].isdigit() and len(parts[0]) == 5:
                zip_code = parts[0]
                area = parts[1] if len(parts) > 1 else ""
                notes = parts[-1] if len(parts) > 2 else ""

                hot_zips[zip_code] = {
                    'tier': current_tier,
                    'area': area,
                    'notes': notes,
                    'region': current_region,
                    'premium': HOT_ZIP_PREMIUM.get(current_tier, {})
                }

    logger.info(f"Parsed {len(hot_zips)} hot zip codes")
    _hot_zip_codes_cache = hot_zips
    return _hot_zip_codes_cache


def get_hot_zip_info(zip_code: str) -> Optional[Dict[str, Any]]:
    """
    Check if a zip code is a hot market.
    Returns tier info if hot, None otherwise.
    """
    if not zip_code:
        return None

    # Clean zip code (handle zip+4 format like "98006-1234")
    zip_clean = zip_code.split('-')[0].strip()
    if len(zip_clean) != 5:
        return None

    hot_zips = _load_hot_zip_codes()
    return hot_zips.get(zip_clean)


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

            # Load relevant market knowledge files
            file_keys = self._select_market_files(property_data)
            knowledge_context = self._load_knowledge_files(file_keys)

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

            # Add hot zip code info if applicable
            if baseline_metrics.get('hot_zip_info'):
                analysis['details']['hot_zip'] = {
                    'zip_code': baseline_metrics.get('zip_code'),
                    'tier': baseline_metrics['hot_zip_info'].get('tier'),
                    'area': baseline_metrics['hot_zip_info'].get('area'),
                    'region': baseline_metrics['hot_zip_info'].get('region'),
                    'premium_applied': baseline_metrics.get('hot_zip_premium_applied'),
                }

            analysis['market_snapshot'] = market_snapshot
            analysis['raw_data'] = {
                'address': address,
                'property_data_keys': list(property_data.keys()),
                'knowledge_context_used': bool(knowledge_context),
            }
            analysis['knowledge_debug'] = {"file_keys": file_keys}
            analysis['knowledge_queries'] = file_keys
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

        # Extract zip code for hot market check
        zip_code = None
        prop = data.get('property', {}) or {}
        addr = prop.get('address', {}) or {}
        zip_code = addr.get('zip_code') or addr.get('postal_code') or addr.get('zip')
        if not zip_code:
            region_info = data.get('region_info', {}) or {}
            zip_code = region_info.get('zip_code') or region_info.get('zip')

        # Check if hot zip code
        hot_zip_info = get_hot_zip_info(zip_code) if zip_code else None

        # Determine baseline
        # Use list/asking price as baseline when available - it's what users see
        # and what factors should adjust from. Redfin estimate is passed as context.
        baseline = None
        baseline_source = None

        if list_price:
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

        # Apply hot zip code premium to baseline (only when not using list price,
        # since list price already reflects the local market)
        hot_zip_premium_applied = None
        if baseline and hot_zip_info and baseline_source != 'list_price':
            tier = hot_zip_info['tier']
            premium_info = hot_zip_info.get('premium', {})
            # Use midpoint of premium range
            premium_pct = (premium_info.get('min', 0) + premium_info.get('max', 0)) / 2
            if premium_pct > 0:
                hot_zip_premium_applied = premium_pct
                baseline = baseline * (1 + premium_pct)
                baseline_source = f"{baseline_source}_hot_zip_t{tier}"
                logger.info(f"Applied hot zip premium: Tier {tier} ({premium_pct*100:.1f}%) for zip {zip_code}")

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
            'zip_code': zip_code,
            'hot_zip_info': hot_zip_info,
            'hot_zip_premium_applied': hot_zip_premium_applied,
        }

        # Price vs estimate spread
        if redfin_estimate and list_price:
            metrics['list_vs_estimate_pct'] = round(
                (redfin_estimate - list_price) / list_price * 100, 2
            )

        return metrics

    async def _fetch_market_conditions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetch real-time market conditions from web scrapers.

        Uses redfin_market_service for real local market data instead of
        Claude Haiku inference. Falls back to extracted data, then Claude.

        Returns market snapshot with mortgage rate, market type, season,
        and detailed metrics (DOM, sale-to-list, YoY change, inventory).
        """
        from app.services.data_collectors.redfin_market_service import get_local_market_data

        market = data.get('market_trends', {}) or {}
        region_info = data.get('region_info', {}) or {}

        # Extract city/region for context
        city = region_info.get('city', '')
        state = region_info.get('state', '')

        if not city:
            # Try to extract from address
            prop = data.get('property', {}) or {}
            addr = prop.get('address', {}) or {}
            city = addr.get('city', '')
            state = addr.get('state', '')

        # Get market type from extracted data if available (fallback)
        extracted_market_type = market.get('market_type', '')

        # Get current season
        month = _get_current_month()
        season = _get_season(month)

        # Fetch mortgage rate from web (with caching)
        mortgage_rate, rate_source = await get_current_mortgage_rate()
        logger.info(f"Mortgage rate: {mortgage_rate}% (source: {rate_source})")

        # Try real-time web-scraped market data first
        local_market = None
        if city:
            try:
                local_market = await get_local_market_data(city, state)
            except Exception as e:
                logger.warning(f"SalePriceSkill: Real-time market fetch failed: {e}")

        if local_market:
            logger.info(f"SalePriceSkill: Using real-time market data from {local_market.get('source')}")
            return {
                'mortgage_rate': mortgage_rate,
                'mortgage_rate_source': rate_source,
                'market_type': local_market.get('market_type', 'balanced'),
                'season': season,
                'local_trend': local_market.get('local_trend', 'unknown'),
                'rate_direction': 'stable',
                'median_dom': local_market.get('median_dom'),
                'sale_to_list_ratio': local_market.get('sale_to_list_ratio'),
                'yoy_price_change_pct': local_market.get('yoy_price_change_pct'),
                'inventory_months': local_market.get('inventory_months'),
                'median_sale_price': local_market.get('median_sale_price'),
                'homes_sold_last_30d': local_market.get('homes_sold_last_30d'),
                'source': f"web_realtime_{local_market.get('source', 'unknown')}",
            }

        # Fallback: use extracted data from Redfin listing if available
        if extracted_market_type:
            logger.info(f"SalePriceSkill: Using extracted market data (market_type={extracted_market_type})")
            return {
                'mortgage_rate': mortgage_rate,
                'mortgage_rate_source': rate_source,
                'market_type': extracted_market_type,
                'season': season,
                'local_trend': 'unknown',
                'rate_direction': 'stable',
                'source': 'extracted_data',
            }

        # Final fallback: use Claude Haiku inference
        try:
            region = region_info.get('region', '')
            prompt = f"""Based on your knowledge of current real estate market conditions (as of early 2026), provide market data for {city}, {state if state else region}.

Return ONLY a JSON object with these fields:
- market_type: string ("seller's", "buyer's", or "balanced")
- local_yoy_trend: string (e.g., "prices up 3% YoY" or "prices flat YoY")
- rate_direction: string ("rising", "falling", or "stable")

Return ONLY valid JSON, no explanation."""

            response = await self._call_claude(
                prompt=prompt,
                max_tokens=150,
                model="claude-3-haiku-20240307"
            )

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
                'market_type': market_data.get('market_type', 'balanced'),
                'season': season,
                'local_trend': market_data.get('local_yoy_trend', 'unknown'),
                'rate_direction': market_data.get('rate_direction', 'stable'),
                'source': 'claude_fallback',
            }

        except Exception as e:
            logger.warning(f"SalePriceSkill: All market condition sources failed: {e}")
            return {
                'mortgage_rate': mortgage_rate,
                'mortgage_rate_source': rate_source,
                'market_type': 'balanced',
                'season': season,
                'local_trend': 'unknown',
                'rate_direction': 'stable',
                'source': 'fallback_default',
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

        # Hot zip code section
        hot_zip_section = ""
        hot_zip_info = baseline_metrics.get('hot_zip_info')
        if hot_zip_info:
            hot_zip_section = "\nHOT ZIP CODE MARKET:\n"
            tier = hot_zip_info.get('tier', 0)
            premium_info = hot_zip_info.get('premium', {})
            hot_zip_section += f"- Zip Code: {baseline_metrics.get('zip_code')}\n"
            hot_zip_section += f"- Market Tier: {tier} ({premium_info.get('label', 'Hot')})\n"
            hot_zip_section += f"- Area: {hot_zip_info.get('area', 'N/A')}\n"
            hot_zip_section += f"- Region: {hot_zip_info.get('region', 'N/A')}\n"
            if hot_zip_info.get('notes'):
                hot_zip_section += f"- Notes: {hot_zip_info.get('notes')}\n"
            premium_applied = baseline_metrics.get('hot_zip_premium_applied')
            if premium_applied:
                hot_zip_section += f"- Premium Applied: +{premium_applied*100:.1f}% (already factored into baseline)\n"
            hot_zip_section += ">>> This is a premium/high-demand market - properties often sell at or above ask\n"

        # Market snapshot section
        market_section = "\nMARKET CONDITIONS:\n"
        rate_source = market_snapshot.get('mortgage_rate_source', '')
        rate_note = f" (from {rate_source})" if rate_source else ""
        market_section += f"- Mortgage Rate (30yr best available): {market_snapshot.get('mortgage_rate', 'N/A')}%{rate_note}\n"
        market_section += f"- Market Type: {market_snapshot.get('market_type', 'N/A')}\n"
        market_section += f"- Season: {market_snapshot.get('season', 'N/A')}\n"
        market_section += f"- Local Trend: {market_snapshot.get('local_trend', 'N/A')}\n"
        market_section += f"- Rate Direction: {market_snapshot.get('rate_direction', 'N/A')}\n"
        # Add detailed market metrics when available (from real-time scraping)
        if market_snapshot.get('median_dom') is not None:
            market_section += f"- Area Median DOM: {market_snapshot['median_dom']} days\n"
        if market_snapshot.get('sale_to_list_ratio') is not None:
            market_section += f"- Area Sale-to-List Ratio: {market_snapshot['sale_to_list_ratio']:.3f} ({market_snapshot['sale_to_list_ratio']*100:.1f}%)\n"
        if market_snapshot.get('yoy_price_change_pct') is not None:
            market_section += f"- Area YoY Price Change: {market_snapshot['yoy_price_change_pct']:+.1f}%\n"
        if market_snapshot.get('inventory_months') is not None:
            market_section += f"- Months of Supply: {market_snapshot['inventory_months']:.1f}\n"
        if market_snapshot.get('median_sale_price') is not None:
            market_section += f"- Area Median Sale Price: ${market_snapshot['median_sale_price']:,.0f}\n"
        market_section += f"- Data Source: {market_snapshot.get('source', 'N/A')}\n"

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

        # Location scores - not included in price prediction as they have minimal impact
        loc_section = ""

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
{hot_zip_section}
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
1. Start from the BASELINE (the list/asking price). All adjustments are relative to this.
2. Apply adjustments based on DOM, market conditions, property features
3. If inspection/HOA documents were analyzed, incorporate those findings:
   - Subtract estimated repair costs from predicted price
   - Factor in special assessments and HOA financial health
4. Provide a predicted midpoint and realistic range:
   - Standard properties: +/- 3-5%
   - Luxury properties (>$1.5M): +/- 5-8% (more price variability)
5. List the key adjustment factors (3-6 most impactful)
   - For each factor, estimate the percentage and dollar impact on the baseline (list price)
   - Use guideline ranges (e.g., DOM < 7 = +2% to +5%, seller's market = +3% to +5%, stale listing = -5% to -10%)
   - CRITICAL: The sum of all factor dollar impacts MUST approximately equal (predicted_sale_price - baseline). The math must add up.
6. Explain your reasoning in 2-3 sentences
7. Assign a confidence score (0-100) based on data quality

CRITICAL PRICING INSIGHTS:
- The BASELINE is the list/asking price. Your predicted price = baseline + sum of all factor impacts.
- Use the Redfin estimate as a REFERENCE SIGNAL, not the baseline. If Redfin estimate differs significantly from list price, mention it but don't anchor to it.
- For NEW listings (DOM < 14), the list price hasn't been rejected by the market yet - respect it more
- High DOM (>45) = market HAS spoken, price likely needs to come down
- For luxury properties ($1.5M+): Do NOT add a "Luxury Property Premium" factor. Apply luxury adjustment rules from the guidelines above.
- Market type is based on city-wide data. For luxury properties ($1.5M+), the luxury segment often behaves more like a balanced/buyer's market even when the overall market is classified as "seller's".

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
        {{"factor": "<description>", "direction": "<up|down>", "impact": "<significant|moderate|slight>", "estimated_impact_pct": <number - estimated % impact on baseline>, "estimated_impact_dollars": <number - estimated $ impact on price>}},
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
    def _select_market_files(data: Dict[str, Any]) -> List[str]:
        """Select relevant knowledge file keys for sale price analysis."""
        from app.services.knowledge.skill_knowledge_service import get_market_file_key

        region_info = data.get('region_info', {}) or {}
        prop = data.get('property', {}) or {}
        addr = prop.get('address', {}) or {}

        file_keys = ["hot_zip_codes"]

        region = region_info.get('region', '')
        address_str = addr.get('full', '') or addr.get('street', '')
        market_key = get_market_file_key(region=region, address=address_str)
        if market_key:
            file_keys.append(market_key)

        logger.info(f"SalePriceSkill: Selected knowledge files: {file_keys}")
        return file_keys

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
