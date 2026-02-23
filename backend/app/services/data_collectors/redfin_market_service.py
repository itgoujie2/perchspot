"""
Redfin Market Service - Fetches real-time local market data

Scrapes publicly available housing market data to replace Claude Haiku
inference for market conditions. Provides actual metrics like median DOM,
sale-to-list ratio, YoY price changes, and inventory months.

Strategy (tries in order, caches 24h):
1. Redfin housing market page scraping
2. Houzeo housing market page scraping
3. Returns None (caller falls back to extracted data or Claude)
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)

# Cache: city_state_key -> (data_dict, fetched_at)
_market_data_cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}
MARKET_DATA_CACHE_HOURS = 24


def _cache_key(city: str, state: str) -> str:
    return f"{city.lower().strip()}_{state.lower().strip()}"


def classify_market_type(
    sale_to_list_ratio: Optional[float],
    median_dom: Optional[float],
) -> str:
    """
    Data-driven market type classification.
    Uses sale-to-list ratio and median DOM to determine market type.
    """
    if sale_to_list_ratio is None and median_dom is None:
        return "balanced"

    # Use both signals when available
    if sale_to_list_ratio is not None and median_dom is not None:
        if sale_to_list_ratio >= 1.02 and median_dom < 14:
            return "seller's"
        if sale_to_list_ratio >= 1.00 and median_dom < 30:
            return "moderate seller's"
        if 0.97 <= sale_to_list_ratio <= 1.00 and 30 <= median_dom <= 60:
            return "balanced"
        if sale_to_list_ratio < 0.97 or median_dom > 60:
            return "buyer's"
        # Default for edge cases
        return "balanced"

    # Single signal fallback
    if median_dom is not None:
        if median_dom < 14:
            return "seller's"
        if median_dom < 30:
            return "moderate seller's"
        if median_dom <= 60:
            return "balanced"
        return "buyer's"

    if sale_to_list_ratio is not None:
        if sale_to_list_ratio >= 1.02:
            return "seller's"
        if sale_to_list_ratio >= 1.00:
            return "moderate seller's"
        if sale_to_list_ratio >= 0.97:
            return "balanced"
        return "buyer's"

    return "balanced"


def _compute_yoy_trend(yoy_pct: Optional[float]) -> str:
    """Convert YoY percentage to human-readable trend string."""
    if yoy_pct is None:
        return "unknown"
    if yoy_pct > 5:
        return f"prices up {yoy_pct:.1f}% YoY (strong growth)"
    if yoy_pct > 1:
        return f"prices up {yoy_pct:.1f}% YoY"
    if yoy_pct > -1:
        return f"prices flat YoY ({yoy_pct:+.1f}%)"
    if yoy_pct > -5:
        return f"prices down {abs(yoy_pct):.1f}% YoY"
    return f"prices down {abs(yoy_pct):.1f}% YoY (significant decline)"


def _parse_float(text: str) -> Optional[float]:
    """Extract a float from text like '$1,480,000' or '40' or '99.2%'."""
    if not text:
        return None
    cleaned = re.sub(r'[,$%]', '', text.strip())
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


async def _fetch_from_redfin(city: str, state: str) -> Optional[Dict[str, Any]]:
    """
    Fetch market data from Redfin's housing market page.
    URL pattern: https://www.redfin.com/city/<state-id>/<state>/<city>/housing-market
    """
    try:
        # Normalize city name for URL (e.g., "San Francisco" -> "San-Francisco")
        city_slug = city.strip().replace(' ', '-')
        state_upper = state.strip().upper()

        # Try common Redfin URL patterns
        urls = [
            f"https://www.redfin.com/city/{city_slug}-{state_upper}/housing-market",
            f"https://www.redfin.com/state/{state_upper}/{city_slug}/housing-market",
        ]

        async with httpx.AsyncClient(
            headers={
                'User-Agent': settings.USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            timeout=15.0,
            follow_redirects=True,
        ) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        continue

                    soup = BeautifulSoup(response.text, 'lxml')
                    text = soup.get_text(separator=' ')

                    data: Dict[str, Any] = {'source': 'redfin'}

                    # Extract median sale price
                    match = re.search(
                        r'median\s+sale\s+price.*?\$\s*([\d,]+)',
                        text, re.IGNORECASE
                    )
                    if match:
                        data['median_sale_price'] = _parse_float(match.group(1))

                    # Extract YoY price change
                    match = re.search(
                        r'([+-]?\d+\.?\d*)\s*%\s*(?:year[- ]over[- ]year|yoy|since last year)',
                        text, re.IGNORECASE
                    )
                    if match:
                        data['yoy_price_change_pct'] = _parse_float(match.group(1))

                    # Extract median days on market
                    match = re.search(
                        r'median\s+days\s+on\s+market.*?(\d+)',
                        text, re.IGNORECASE
                    )
                    if match:
                        data['median_dom'] = _parse_float(match.group(1))

                    # Extract sale-to-list ratio
                    match = re.search(
                        r'sale[- ]to[- ]list.*?(\d+\.?\d*)\s*%',
                        text, re.IGNORECASE
                    )
                    if match:
                        val = _parse_float(match.group(1))
                        if val and val > 50:  # It's a percentage like 99.2
                            data['sale_to_list_ratio'] = val / 100.0

                    # Extract homes sold
                    match = re.search(
                        r'(\d[\d,]*)\s+homes?\s+(?:were\s+)?sold',
                        text, re.IGNORECASE
                    )
                    if match:
                        data['homes_sold_last_30d'] = int(match.group(1).replace(',', ''))

                    # Extract months of supply / inventory
                    match = re.search(
                        r'(\d+\.?\d*)\s+months?\s+(?:of\s+)?(?:supply|inventory)',
                        text, re.IGNORECASE
                    )
                    if match:
                        data['inventory_months'] = _parse_float(match.group(1))

                    # Need at least median_dom or sale_to_list to be useful
                    if data.get('median_dom') is not None or data.get('sale_to_list_ratio') is not None:
                        logger.info(f"RedfinMarketService: Got data from Redfin for {city}, {state}: {data}")
                        return data

                except httpx.HTTPError:
                    continue

    except Exception as e:
        logger.warning(f"RedfinMarketService: Redfin scrape failed for {city}, {state}: {e}")

    return None


async def _fetch_from_houzeo(city: str, state: str) -> Optional[Dict[str, Any]]:
    """
    Fetch market data from Houzeo housing market pages.
    URL pattern: https://www.houzeo.com/housing-market/<state>/<city>
    """
    try:
        # State name mapping for URL (need full state name)
        state_names = {
            'AL': 'alabama', 'AK': 'alaska', 'AZ': 'arizona', 'AR': 'arkansas',
            'CA': 'california', 'CO': 'colorado', 'CT': 'connecticut', 'DE': 'delaware',
            'FL': 'florida', 'GA': 'georgia', 'HI': 'hawaii', 'ID': 'idaho',
            'IL': 'illinois', 'IN': 'indiana', 'IA': 'iowa', 'KS': 'kansas',
            'KY': 'kentucky', 'LA': 'louisiana', 'ME': 'maine', 'MD': 'maryland',
            'MA': 'massachusetts', 'MI': 'michigan', 'MN': 'minnesota', 'MS': 'mississippi',
            'MO': 'missouri', 'MT': 'montana', 'NE': 'nebraska', 'NV': 'nevada',
            'NH': 'new-hampshire', 'NJ': 'new-jersey', 'NM': 'new-mexico', 'NY': 'new-york',
            'NC': 'north-carolina', 'ND': 'north-dakota', 'OH': 'ohio', 'OK': 'oklahoma',
            'OR': 'oregon', 'PA': 'pennsylvania', 'RI': 'rhode-island', 'SC': 'south-carolina',
            'SD': 'south-dakota', 'TN': 'tennessee', 'TX': 'texas', 'UT': 'utah',
            'VT': 'vermont', 'VA': 'virginia', 'WA': 'washington', 'WV': 'west-virginia',
            'WI': 'wisconsin', 'WY': 'wyoming', 'DC': 'washington-dc',
        }

        state_upper = state.strip().upper()
        state_slug = state_names.get(state_upper)
        if not state_slug:
            # Try using the state value directly as a slug
            state_slug = state.strip().lower().replace(' ', '-')

        city_slug = city.strip().lower().replace(' ', '-')
        url = f"https://www.houzeo.com/housing-market/{state_slug}/{city_slug}"

        async with httpx.AsyncClient(
            headers={
                'User-Agent': settings.USER_AGENT,
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            timeout=15.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'lxml')
            text = soup.get_text(separator=' ')

            data: Dict[str, Any] = {'source': 'houzeo'}

            # Extract median sale/home price
            match = re.search(
                r'median\s+(?:home|sale|listing)?\s*price.*?\$\s*([\d,]+)',
                text, re.IGNORECASE
            )
            if match:
                data['median_sale_price'] = _parse_float(match.group(1))

            # Extract YoY change
            match = re.search(
                r'([+-]?\d+\.?\d*)\s*%\s*(?:year[- ]over[- ]year|yoy|compared to|from|since)',
                text, re.IGNORECASE
            )
            if match:
                data['yoy_price_change_pct'] = _parse_float(match.group(1))

            # Extract median days on market
            match = re.search(
                r'(?:median\s+)?days\s+on\s+(?:the\s+)?market.*?(\d+)',
                text, re.IGNORECASE
            )
            if match:
                data['median_dom'] = _parse_float(match.group(1))

            # Extract sale-to-list ratio
            match = re.search(
                r'sale[- ]to[- ]list.*?(\d+\.?\d*)\s*%',
                text, re.IGNORECASE
            )
            if match:
                val = _parse_float(match.group(1))
                if val and val > 50:
                    data['sale_to_list_ratio'] = val / 100.0

            # Homes sold
            match = re.search(
                r'(\d[\d,]*)\s+homes?\s+(?:were\s+)?sold',
                text, re.IGNORECASE
            )
            if match:
                data['homes_sold_last_30d'] = int(match.group(1).replace(',', ''))

            # Months of supply
            match = re.search(
                r'(\d+\.?\d*)\s+months?\s+(?:of\s+)?(?:supply|inventory)',
                text, re.IGNORECASE
            )
            if match:
                data['inventory_months'] = _parse_float(match.group(1))

            if data.get('median_dom') is not None or data.get('sale_to_list_ratio') is not None:
                logger.info(f"RedfinMarketService: Got data from Houzeo for {city}, {state}: {data}")
                return data

    except Exception as e:
        logger.warning(f"RedfinMarketService: Houzeo scrape failed for {city}, {state}: {e}")

    return None


async def get_local_market_data(city: str, state: str) -> Optional[Dict[str, Any]]:
    """
    Fetch real-time local market data for a city.
    Tries Redfin first, then Houzeo, with 24h caching.

    Returns dict with:
        market_type, median_sale_price, yoy_price_change_pct,
        median_dom, sale_to_list_ratio, inventory_months,
        homes_sold_last_30d, local_trend, source, fetched_at
    Or None if all sources fail.
    """
    if not city:
        return None

    key = _cache_key(city, state)

    # Check cache
    if key in _market_data_cache:
        cached_data, cached_time = _market_data_cache[key]
        hours_old = (datetime.now() - cached_time).total_seconds() / 3600
        if hours_old < MARKET_DATA_CACHE_HOURS:
            logger.debug(f"RedfinMarketService: Using cached data for {city}, {state} ({hours_old:.1f}h old)")
            return cached_data

    # Try sources in order
    raw_data = await _fetch_from_redfin(city, state)
    if not raw_data:
        raw_data = await _fetch_from_houzeo(city, state)

    if not raw_data:
        logger.info(f"RedfinMarketService: No data from web sources for {city}, {state}")
        return None

    # Classify market type from real data
    market_type = classify_market_type(
        raw_data.get('sale_to_list_ratio'),
        raw_data.get('median_dom'),
    )

    # Build standardized result
    result = {
        'market_type': market_type,
        'median_sale_price': raw_data.get('median_sale_price'),
        'yoy_price_change_pct': raw_data.get('yoy_price_change_pct'),
        'median_dom': raw_data.get('median_dom'),
        'sale_to_list_ratio': raw_data.get('sale_to_list_ratio'),
        'inventory_months': raw_data.get('inventory_months'),
        'homes_sold_last_30d': raw_data.get('homes_sold_last_30d'),
        'local_trend': _compute_yoy_trend(raw_data.get('yoy_price_change_pct')),
        'source': raw_data.get('source', 'web'),
        'fetched_at': datetime.now().isoformat(),
    }

    # Cache the result
    _market_data_cache[key] = (result, datetime.now())
    logger.info(f"RedfinMarketService: Market data for {city}, {state}: type={market_type}, "
                f"DOM={raw_data.get('median_dom')}, S/L={raw_data.get('sale_to_list_ratio')}, "
                f"source={raw_data.get('source')}")

    return result
