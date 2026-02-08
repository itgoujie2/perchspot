"""
GreatSchools Service - Enriches school data by scraping GreatSchools pages.

Approach:
1. Fetch the city browse page (/state-slug/city-slug/) to get school name→URL mappings
2. Fuzzy-match Redfin school names against the browse page links
3. Fetch each matched school detail page
4. Extract data from gon.ad_set_targeting, JSON-LD, and HTML

No API key needed, no JS rendering needed.
"""
import asyncio
import json
import re
import logging
from typing import Dict, Any, List, Optional
from difflib import SequenceMatcher

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.greatschools.org"

REQUEST_DELAY = 1.5  # seconds between requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# State abbreviation -> GS URL slug
STATE_SLUGS = {
    "AL": "alabama", "AK": "alaska", "AZ": "arizona", "AR": "arkansas",
    "CA": "california", "CO": "colorado", "CT": "connecticut", "DE": "delaware",
    "FL": "florida", "GA": "georgia", "HI": "hawaii", "ID": "idaho",
    "IL": "illinois", "IN": "indiana", "IA": "iowa", "KS": "kansas",
    "KY": "kentucky", "LA": "louisiana", "ME": "maine", "MD": "maryland",
    "MA": "massachusetts", "MI": "michigan", "MN": "minnesota", "MS": "mississippi",
    "MO": "missouri", "MT": "montana", "NE": "nebraska", "NV": "nevada",
    "NH": "new-hampshire", "NJ": "new-jersey", "NM": "new-mexico", "NY": "new-york",
    "NC": "north-carolina", "ND": "north-dakota", "OH": "ohio", "OK": "oklahoma",
    "OR": "oregon", "PA": "pennsylvania", "RI": "rhode-island", "SC": "south-carolina",
    "SD": "south-dakota", "TN": "tennessee", "TX": "texas", "UT": "utah",
    "VT": "vermont", "VA": "virginia", "WA": "washington", "WV": "west-virginia",
    "WI": "wisconsin", "WY": "wyoming",
}

# Full state names -> abbreviation (for parsing addresses)
STATE_ABBREVS = {v.replace("-", " "): k for k, v in STATE_SLUGS.items()}


def _normalize_state(state: str) -> str:
    """Convert state name or abbreviation to 2-letter abbreviation."""
    s = state.strip()
    if len(s) <= 2:
        return s.upper()
    return STATE_ABBREVS.get(s.lower(), s.upper()[:2])


def _city_slug(city: str) -> str:
    """Convert city name to GS URL slug: 'New York' -> 'new-york'."""
    return re.sub(r'[^a-z0-9]+', '-', city.lower()).strip('-')


def _name_similarity(a: str, b: str) -> float:
    """Fuzzy similarity between two school names."""
    a_clean = re.sub(r'\b(school|elementary|middle|high|senior|academy|preparatory|prep)\b', '', a.lower()).strip()
    b_clean = re.sub(r'\b(school|elementary|middle|high|senior|academy|preparatory|prep)\b', '', b.lower()).strip()
    return SequenceMatcher(None, a_clean, b_clean).ratio()


class GreatSchoolsService:
    """Fetches and parses GreatSchools data for school enrichment."""

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        # Cache: (state_slug, city_slug) -> {school_name_lower: url}
        self._city_school_cache: Dict[tuple, Dict[str, str]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=HEADERS,
                timeout=15.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def enrich_schools(self, schools: List[Dict], city: str, state: str) -> List[Dict]:
        """
        Take Redfin school list, return enriched list with GreatSchools data.
        Fails gracefully per-school.
        """
        state_abbr = _normalize_state(state)
        state_slug = STATE_SLUGS.get(state_abbr)
        if not state_slug:
            logger.warning(f"GreatSchools: Unknown state '{state}' -> '{state_abbr}'")
            return schools

        c_slug = _city_slug(city)

        # Step 1: Fetch city browse page to build name→URL index (one request for all schools)
        school_index = await self._get_city_school_index(state_slug, c_slug)
        if not school_index:
            logger.warning(f"GreatSchools: No school index for {city}, {state_abbr}")
            return schools

        logger.info(f"GreatSchools: City index has {len(school_index)} schools for {city}, {state_abbr}")

        # Step 2: Match each Redfin school to a GS URL and fetch details
        enriched = []
        for school in schools:
            name = school.get("name", "")
            if not name:
                enriched.append(school)
                continue

            # Find best match in city index
            url = self._find_best_match(name, school_index)
            if not url:
                logger.info(f"GreatSchools: No match for '{name}' in city index")
                enriched.append(school)
                continue

            try:
                await asyncio.sleep(REQUEST_DELAY)
                gs_data = await self._fetch_school_details(url)
                if gs_data:
                    merged = {**school, **gs_data}
                    enriched.append(merged)
                    logger.info(f"GreatSchools: Enriched '{name}' — gs_rating={gs_data.get('gs_rating')}, url={url}")
                else:
                    enriched.append(school)
                    logger.info(f"GreatSchools: Page fetched but no data extracted for '{name}'")
            except Exception as e:
                logger.warning(f"GreatSchools: Failed to enrich '{name}': {e}")
                enriched.append(school)

        return enriched

    async def _get_city_school_index(self, state_slug: str, city_slug: str) -> Dict[str, str]:
        """
        Fetch the GS city browse page and return {school_name: full_url} mapping.
        Results are cached per city.
        """
        cache_key = (state_slug, city_slug)
        if cache_key in self._city_school_cache:
            return self._city_school_cache[cache_key]

        client = await self._get_client()
        url = f"{BASE_URL}/{state_slug}/{city_slug}/"

        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"GreatSchools: Failed to fetch city page {url}: {e}")
            return {}

        soup = BeautifulSoup(resp.text, "lxml")
        index: Dict[str, str] = {}

        # School links look like: /washington/bellevue/126-Lake-Hills-Elementary-School/
        pattern = re.compile(rf'^/{re.escape(state_slug)}/{re.escape(city_slug)}/\d+-')
        for a in soup.find_all("a", href=pattern):
            href = a["href"]
            name = a.get_text(strip=True)
            if name:
                index[name] = BASE_URL + href

        self._city_school_cache[cache_key] = index
        logger.info(f"GreatSchools: Indexed {len(index)} schools from {url}")
        return index

    def _find_best_match(self, name: str, index: Dict[str, str]) -> Optional[str]:
        """Find the best fuzzy match for a school name in the city index."""
        best_url = None
        best_score = 0.0

        for gs_name, url in index.items():
            sim = _name_similarity(name, gs_name)
            if sim > best_score:
                best_score = sim
                best_url = url

        if best_score >= 0.4:
            logger.debug(f"GreatSchools: Matched '{name}' -> score={best_score:.2f}")
            return best_url

        logger.debug(f"GreatSchools: No match for '{name}' (best={best_score:.2f})")
        return None

    async def _fetch_school_details(self, url: str) -> Optional[Dict]:
        """Fetch a school detail page and extract structured data."""
        client = await self._get_client()

        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"GreatSchools: Failed to fetch {url}: {e}")
            return None

        return self._extract_school_data(resp.text, url)

    def _extract_school_data(self, html: str, url: str) -> Optional[Dict]:
        """Extract structured school data from a detail page."""
        result: Dict[str, Any] = {"gs_url": url}

        # 1. gon.ad_set_targeting — most reliable for gs_rating
        targeting = self._parse_ad_targeting(html)
        if targeting:
            gs_rating = targeting.get("gs_rating")
            if gs_rating is not None:
                try:
                    result["gs_rating"] = int(gs_rating)
                except (ValueError, TypeError):
                    pass
            result["gs_school_id"] = targeting.get("school_id")
            n_reviews = targeting.get("number_of_reviews_with_comments")
            if n_reviews is not None:
                try:
                    result["gs_review_count"] = int(n_reviews)
                except (ValueError, TypeError):
                    pass

        # 2. JSON-LD structured data — has review aggregate
        ld_data = self._parse_json_ld(html)
        if ld_data:
            agg = ld_data.get("aggregateRating", {})
            if agg:
                if agg.get("ratingValue") is not None:
                    result.setdefault("gs_review_avg", round(float(agg["ratingValue"]), 1))
                if agg.get("reviewCount") is not None:
                    result.setdefault("gs_review_count", int(agg["reviewCount"]))

        # 3. HTML parsing — sub-ratings, enrollment, student-teacher ratio
        soup = BeautifulSoup(html, "lxml")
        html_data = self._extract_from_html(soup)
        for k, v in html_data.items():
            if v is not None:
                result.setdefault(k, v)

        # Clean None values
        result = {k: v for k, v in result.items() if v is not None}

        if result.get("gs_rating") is not None or len(result) > 2:
            return result
        return None

    @staticmethod
    def _parse_ad_targeting(html: str) -> Optional[Dict]:
        """Extract gon.ad_set_targeting JSON from script tags."""
        match = re.search(r'gon\.ad_set_targeting\s*=\s*(\{.+?\})\s*;', html)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _parse_json_ld(html: str) -> Optional[Dict]:
        """Extract JSON-LD School data."""
        for match in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                data = json.loads(match)
                if isinstance(data, dict) and data.get("@type") == "School":
                    return data
            except json.JSONDecodeError:
                continue
        return None

    @staticmethod
    def _extract_from_html(soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract sub-ratings, enrollment, student-teacher ratio from HTML."""
        result: Dict[str, Any] = {}

        # Summary rating from .rs-gs-rating (backup if ad_targeting missed it)
        rs = soup.select_one('.rs-gs-rating')
        if rs:
            m = re.match(r'(\d+)/10', rs.get_text(strip=True))
            if m:
                result["gs_rating"] = int(m.group(1))

        # Sub-ratings from rating-container elements in the RatingFactors section
        rf_section = soup.select_one('[data-ga-click-label=RatingFactors]')
        if rf_section:
            for container in rf_section.select('.rating-container'):
                text = container.get_text(strip=True)
                m = re.match(r'(\d+)/10', text)
                if not m:
                    continue
                rating_val = int(m.group(1))
                # Identify which sub-rating by looking at nearby label
                parent = container.parent
                if not parent:
                    continue
                parent_text = parent.get_text(" ", strip=True).lower()
                if "test score" in parent_text:
                    result["gs_test_scores_rating"] = rating_val
                elif "academic progress" in parent_text or "student progress" in parent_text:
                    result["gs_student_progress_rating"] = rating_val
                elif "equity" in parent_text:
                    result["gs_equity_rating"] = rating_val
                elif "college" in parent_text:
                    result["gs_college_readiness_rating"] = rating_val

        # Enrollment and student-teacher ratio from TeachersStaff or Students section
        # These are often in data tables or text blocks
        full_text = soup.get_text(" ", strip=True)

        # Enrollment: look for "X students" or "Enrollment: X"
        enroll_match = re.search(r'(?:enrollment|students?)\D{0,20}?(\d[\d,]+)\s*(?:students?)?', full_text, re.I)
        if enroll_match:
            try:
                result["gs_enrollment"] = int(enroll_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Student-teacher ratio
        ratio_match = re.search(r'(\d+(?:\.\d+)?)\s*:\s*1\s*(?:student|ratio)', full_text, re.I)
        if not ratio_match:
            ratio_match = re.search(r'student.?teacher\s+ratio\D{0,20}?(\d+(?:\.\d+)?)\s*:\s*1', full_text, re.I)
        if ratio_match:
            try:
                result["gs_student_teacher_ratio"] = float(ratio_match.group(1))
            except ValueError:
                pass

        return result


# Module-level singleton
greatschools_service = GreatSchoolsService()
