"""
Screenshot Extractor Collector - Simple Chromium + Claude Vision Approach

Simple flow:
1. Use Playwright/Chromium to navigate to Redfin property page
2. Take screenshots at different scroll positions
3. Send screenshots to Claude Vision to extract structured property data
4. Save extracted data to JSON/MD files

No computer-use, no Firefox, no complex agent loops.
"""
import logging
import asyncio
import base64
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, AsyncGenerator
from playwright.async_api import async_playwright, Page, Browser
import anthropic

logger = logging.getLogger(__name__)


# Scroll positions to capture (optimized for speed - reduced from 19 to 10)
# Covers key sections: top, details, schools, location scores, climate, similar homes
SCROLL_POSITIONS = [
    (0, "property_top"),       # Header, price, main photo
    (800, "scroll_800"),       # Property details
    (1600, "scroll_1600"),     # Features/description
    (2400, "scroll_2400"),     # More details
    (3200, "scroll_3200"),     # Schools section
    (4000, "scroll_4000"),     # Location scores
    (5000, "scroll_5000"),     # Climate risks
    (6000, "scroll_6000"),     # Market trends
    (7500, "scroll_7500"),     # Similar homes
    (9000, "scroll_9000"),     # More similar homes
]

# Claude Vision extraction prompt
EXTRACTION_PROMPT = """You are extracting property data from Redfin screenshots.

Analyze ALL the screenshots provided and extract the following information into a structured JSON format.
Look carefully at each screenshot as different sections contain different data.

IMPORTANT: Extract ALL available data. If a field is not visible in any screenshot, use null.

Return a JSON object with this structure:
{
  "property": {
    "address": {
      "street": "string",
      "city": "string",
      "state": "string",
      "zip": "string"
    },
    "status": "string (e.g., 'For Sale', 'Sold', 'Off Market')",
    "mls_number": "string or null",
    "description": "string - the full 'About this home' description text"
  },
  "pricing": {
    "list_price": number or null,
    "sold_price": number or null,
    "sold_date": "string or null",
    "redfin_estimate": number or null,
    "price_per_sqft": number or null,
    "rental_estimate": number or null
  },
  "details": {
    "property_type": "string (e.g., 'Townhome', 'Single Family')",
    "year_built": number or null,
    "bedrooms": number,
    "bathrooms": number,
    "living_area_sqft": number or null,
    "lot_size_sqft": number or null,
    "parking": "string (e.g., '2 car garage')",
    "stories": number or null
  },
  "features": {
    "interior": ["list of interior features"],
    "exterior": ["list of exterior features"],
    "appliances": ["list of appliances included"],
    "heating_cooling": "string description"
  },
  "hoa": {
    "has_hoa": boolean,
    "fee": number or null,
    "frequency": "string or null"
  },
  "taxes": {
    "annual_amount": number or null,
    "tax_year": number or null
  },
  "schools": [
    {
      "name": "string",
      "type": "string (Elementary/Middle/High)",
      "rating": number (out of 10),
      "distance": "string"
    }
  ],
  "location": {
    "walkability_score": number or null,
    "transit_score": number or null,
    "bike_score": number or null
  },
  "climate_risks": {
    "flood": "string (Minimal/Minor/Moderate/Major/Severe)",
    "fire": "string",
    "heat": "string",
    "wind": "string",
    "air_quality": "string"
  },
  "market_trends": {
    "market_type": "string (Buyer's/Seller's Market)",
    "median_sale_price": number or null,
    "days_on_market": number or null
  },
  "images": {
    "photo_count": number,
    "main_photo_visible": boolean,
    "main_photo_url": "string URL of main property photo or null"
  },
  "similar_homes": [
    {
      "address": "full street address, city, state",
      "price": number or null,
      "bedrooms": number or null,
      "bathrooms": number or null,
      "sqft": number or null,
      "property_type": "string (e.g., 'House', 'Townhome') or null",
      "redfin_url": "https://... or null"
    }
  ]
}

Look for the "Similar Homes" or "Nearby Homes" section near the bottom of the page.
Extract up to 6 similar properties if visible. Include full address with city and state.

Analyze all screenshots carefully and extract as much data as possible.
Return ONLY valid JSON, no other text."""


class ScreenshotExtractorCollector:
    """
    Simple Redfin collector using Chromium screenshots + Claude Vision.

    Much simpler than computer-use approach:
    - No agent loops
    - No Firefox
    - No coordinate clicking
    - Just screenshots and vision extraction
    """

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.screenshots_dir = Path("/app/screenshots")
        self.property_data_dir = Path("/app/property_data")
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.property_data_dir.mkdir(parents=True, exist_ok=True)

        # Cost tracking
        self.total_cost = 0.0
        self.api_calls = 0
        self.screenshots_taken = 0
        self.api_call_details = []  # Track each call for debugging

        # Photo URL tracking
        self._current_main_photo_url = None

        # Cost per 1M tokens (Claude Sonnet 4)
        # Input: $3/1M, Output: $15/1M
        self.COST_PER_INPUT_TOKEN = 3.0 / 1_000_000  # $0.000003
        self.COST_PER_OUTPUT_TOKEN = 15.0 / 1_000_000  # $0.000015

        # For local development, use local paths
        if not os.path.exists("/app"):
            self.screenshots_dir = Path("./screenshots")
            self.property_data_dir = Path("./property_data")

    async def scrape_property(self, address: str) -> Dict[str, Any]:
        """
        Scrape property data using screenshot + vision extraction approach.

        Args:
            address: Full property address

        Returns:
            Dict with success status and extracted data
        """
        logger.info(f"Starting screenshot extraction for: {address}")
        start_time = time.time()

        # Reset counters
        self.total_cost = 0.0
        self.api_calls = 0
        self.screenshots_taken = 0

        try:
            # Step 1: Take screenshots
            screenshots = await self._capture_screenshots(address)

            if not screenshots:
                return {
                    "success": False,
                    "error": "Failed to capture screenshots",
                    "data": {}
                }

            logger.info(f"Captured {len(screenshots)} screenshots")

            # Step 2: Extract data using Claude Vision
            extracted_data = await self._extract_data_from_screenshots(screenshots, address)

            # Step 3: Save to files
            await self._save_extracted_data(address, extracted_data)

            # Add metadata
            extracted_data["_metadata"] = {
                "source": "redfin",
                "extraction_method": "screenshot_vision",
                "extraction_date": datetime.utcnow().isoformat() + "Z",
                "screenshots_count": len(screenshots),
                "api_calls": self.api_calls,
                "total_cost": round(self.total_cost, 6),
                "extraction_time_seconds": round(time.time() - start_time, 2)
            }

            logger.info(f"Extraction complete. Cost: ${self.total_cost:.4f}")

            return {
                "success": True,
                "data": extracted_data,
                "scraping_cost": self.total_cost,
                "scraping_time_seconds": time.time() - start_time
            }

        except Exception as e:
            logger.error(f"Screenshot extraction failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": {}
            }

    async def scrape_property_streaming(self, address: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streaming version that yields progress events for the streaming orchestrator.

        Yields events compatible with StreamingAnalysisOrchestrator:
        - init, status, step_complete, complete, error
        """
        logger.info(f"Starting streaming screenshot extraction for: {address}")
        start_time = time.time()

        self.total_cost = 0.0
        self.api_calls = 0
        self.screenshots_taken = 0
        self.api_call_details = []
        self._current_main_photo_url = None

        yield {"type": "init", "status": "started", "address": address, "mode": "extraction"}
        yield {"type": "status", "message": "Looking up property information..."}

        try:
            # Step 1: Capture property page data
            yield {"type": "status", "message": "Gathering property listing data..."}
            screenshots = await self._capture_screenshots(address)

            if not screenshots:
                yield {"type": "error", "error": "Failed to retrieve property data"}
                return

            yield {
                "type": "step_complete",
                "step": 1,
                "step_name": "Data Collection",
                "data": {"pages_analyzed": len(screenshots)},
                "cost_so_far": 0
            }

            # Step 2: Extract structured data
            yield {"type": "status", "message": "Extracting property details..."}
            extracted_data = await self._extract_data_from_screenshots(screenshots, address)

            # Step 3: Save files
            await self._save_extracted_data(address, extracted_data)

            # Yield extracted data as step_complete events
            prop = extracted_data.get("property", {})
            pricing = extracted_data.get("pricing", {})
            details = extracted_data.get("details", {})
            schools = extracted_data.get("schools", [])
            climate = extracted_data.get("climate_risks", {})
            location = extracted_data.get("location", {})
            market = extracted_data.get("market_trends", {})

            yield {
                "type": "step_complete",
                "step": 2,
                "step_name": "Property Overview",
                "data": {
                    "address": prop.get("address", {}),
                    "status": prop.get("status"),
                    "description": prop.get("description", ""),
                    "property_type": details.get("property_type"),
                    "year_built": details.get("year_built"),
                    "bedrooms": details.get("bedrooms"),
                    "bathrooms": details.get("bathrooms"),
                    "sqft": details.get("living_area_sqft"),
                    "lot_size": details.get("lot_size_sqft"),
                    "parking": details.get("parking"),
                },
                "cost_so_far": round(self.total_cost, 4)
            }

            yield {
                "type": "step_complete",
                "step": 3,
                "step_name": "Pricing & Estimates",
                "data": pricing,
                "cost_so_far": round(self.total_cost, 4)
            }

            yield {
                "type": "step_complete",
                "step": 4,
                "step_name": "Schools",
                "data": {"schools": schools},
                "cost_so_far": round(self.total_cost, 4)
            }

            yield {
                "type": "step_complete",
                "step": 5,
                "step_name": "Location & Lifestyle",
                "data": {**location, **market},
                "cost_so_far": round(self.total_cost, 4)
            }

            yield {
                "type": "step_complete",
                "step": 6,
                "step_name": "Climate Risks",
                "data": climate,
                "cost_so_far": round(self.total_cost, 4)
            }

            # Final completion event
            total_time = time.time() - start_time
            yield {
                "type": "complete",
                "status": "complete",
                "all_data": extracted_data,
                "total_cost": round(self.total_cost, 6),
                "total_time": round(total_time, 2)
            }

        except Exception as e:
            logger.error(f"Streaming extraction error: {e}", exc_info=True)
            yield {"type": "error", "error": str(e)}

    async def _capture_screenshots(self, address: str) -> List[Dict[str, Any]]:
        """
        Capture screenshots of the Redfin property page at different scroll positions.
        """
        screenshots = []

        try:
            async with async_playwright() as p:
                # Launch Chromium with performance optimizations for EC2
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-extensions',
                        '--disable-background-networking',
                        '--disable-sync',
                        '--disable-translate',
                        '--no-first-run',
                        '--single-process',  # Reduces memory usage on low-resource instances
                        '--disable-features=site-per-process',
                    ]
                )

                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )

                page = await context.new_page()

                # Navigate to Redfin and search
                logger.info("Navigating to Redfin...")
                await page.goto("https://www.redfin.com", wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(1.5)  # Reduced from 3s

                # Close any popups (like Google sign-in) - with robust error handling
                await self._dismiss_popups(page)

                # Search for the address with retry logic
                logger.info(f"Searching for: {address}")
                search_success = await self._perform_search(page, address)
                if not search_success:
                    logger.error("Could not perform search")
                    await browser.close()
                    return screenshots

                # Check for disambiguation popup immediately after search
                # This handles the "Did you mean" dialog before URL changes
                if await self._handle_disambiguation_popup(page):
                    logger.info("Handled disambiguation popup after search")
                    await asyncio.sleep(1)

                # Check if we're on a property page or search results
                current_url = page.url
                logger.info(f"Current URL: {current_url}")

                # If on search results, click the first result with retry
                if "/redfin-search" in current_url or "searchResults" in current_url:
                    logger.info("On search results, clicking first result...")
                    await self._click_first_result(page)

                # Wait for property page to load
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=30000)
                except Exception as e:
                    logger.warning(f"Page load state wait failed: {e}")
                await asyncio.sleep(1.5)  # Reduced from 3s

                # Extract main photo URL before scrolling
                main_photo_url = await self._extract_main_photo_url(page)
                if main_photo_url:
                    logger.info(f"Extracted main photo URL: {main_photo_url[:100]}...")

                # Create address slug for filenames
                address_slug = self._create_slug(address)
                screenshot_dir = self.screenshots_dir / address_slug
                screenshot_dir.mkdir(parents=True, exist_ok=True)

                # Store photo URL for later use
                self._current_main_photo_url = main_photo_url

                # Take screenshots at different scroll positions
                for i, (scroll_pos, name) in enumerate(SCROLL_POSITIONS):
                    try:
                        # Scroll to position
                        await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                        await asyncio.sleep(0.3)  # Reduced from 0.5s

                        # Take screenshot
                        screenshot_path = screenshot_dir / f"screenshot_{i+1:02d}_{name}.png"
                        await page.screenshot(path=str(screenshot_path), full_page=False)

                        # Read and encode screenshot
                        with open(screenshot_path, 'rb') as f:
                            screenshot_data = base64.b64encode(f.read()).decode('utf-8')

                        screenshots.append({
                            "index": i + 1,
                            "name": name,
                            "scroll_position": scroll_pos,
                            "path": str(screenshot_path),
                            "data": screenshot_data
                        })

                        self.screenshots_taken += 1
                        logger.info(f"Screenshot {i+1}/{len(SCROLL_POSITIONS)}: {name}")

                    except Exception as e:
                        logger.warning(f"Failed to capture screenshot at {scroll_pos}: {e}")
                        continue

                # Also take a full-page screenshot for reference
                try:
                    full_page_path = screenshot_dir / "full_page.png"
                    await page.screenshot(path=str(full_page_path), full_page=True)
                    logger.info("Captured full-page screenshot")
                except Exception as e:
                    logger.warning(f"Failed to capture full-page screenshot: {e}")

                await browser.close()

        except Exception as e:
            logger.error(f"Error capturing screenshots: {e}", exc_info=True)

        return screenshots

    async def _dismiss_popups(self, page: Page, max_attempts: int = 3):
        """Dismiss any popups or overlays on the page."""
        for attempt in range(max_attempts):
            try:
                # Common popup close selectors
                close_selectors = [
                    '[aria-label="Close"]',
                    '[aria-label="close"]',
                    'button.close',
                    '[data-testid="close"]',
                    '.modal-close',
                    '[data-rf-test-name="closeButton"]',
                    'button[aria-label*="dismiss"]',
                ]

                for selector in close_selectors:
                    try:
                        buttons = await page.query_selector_all(selector)
                        for btn in buttons:
                            if await btn.is_visible():
                                await btn.click(timeout=2000)
                                await asyncio.sleep(0.3)
                    except Exception:
                        continue

                # Press Escape to close any modal
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                break

            except Exception as e:
                logger.debug(f"Popup dismiss attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(0.5)

    async def _extract_main_photo_url(self, page: Page) -> Optional[str]:
        """
        Extract the main property photo URL from the Redfin page.

        Tries multiple selectors to find the primary property image.
        Returns the URL or None if not found.
        """
        try:
            # Redfin property photo selectors (in order of preference)
            photo_selectors = [
                # Main hero image
                'img[data-rf-test-name="hero-photo"]',
                'img[data-rf-test-name="primary-photo"]',
                # Photo gallery main image
                '.PhotosView img',
                '.photo-view img',
                '.slideshow-image img',
                '.carousel-image img',
                # Main property image container
                '.main-photo img',
                '.primary-photo img',
                '.HomeMainMedia img',
                # Generic large property images
                'img[class*="photo"][src*="ssl.cdn-redfin"]',
                'img[src*="ssl.cdn-redfin.com"]',
                'img[src*="photos.zillowstatic"]',
                # Backup: any large image in the header area
                '.above-the-fold img',
                'header img[src*="cdn"]',
            ]

            for selector in photo_selectors:
                try:
                    images = await page.query_selector_all(selector)
                    for img in images:
                        if await img.is_visible():
                            # Try srcset first (for higher resolution)
                            srcset = await img.get_attribute('srcset')
                            if srcset:
                                # Parse srcset and get highest resolution URL
                                urls = srcset.split(',')
                                if urls:
                                    # Get the last (usually highest res) or first
                                    best_url = urls[-1].strip().split(' ')[0]
                                    if best_url and 'http' in best_url:
                                        return best_url

                            # Fall back to src
                            src = await img.get_attribute('src')
                            if src and 'http' in src:
                                # Skip tiny placeholder images
                                width = await img.get_attribute('width')
                                if width and int(width) < 100:
                                    continue
                                return src

                except Exception:
                    continue

            # Try to extract from background-image style
            bg_selectors = [
                '.PhotosView [style*="background-image"]',
                '.photo-view [style*="background-image"]',
                '.HomeMainMedia [style*="background-image"]',
                '[class*="photo"] [style*="background-image"]',
            ]

            for selector in bg_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for el in elements:
                        if await el.is_visible():
                            style = await el.get_attribute('style')
                            if style and 'url(' in style:
                                # Extract URL from background-image: url("...")
                                import re
                                url_match = re.search(r'url\(["\']?(https?://[^"\')]+)["\']?\)', style)
                                if url_match:
                                    return url_match.group(1)
                except Exception:
                    continue

            logger.warning("Could not extract main photo URL from page")
            return None

        except Exception as e:
            logger.warning(f"Error extracting main photo URL: {e}")
            return None

    def _normalize_address_for_search(self, address: str) -> str:
        """
        Normalize address format for Redfin search.

        Handles common user input variations:
        - Missing space between state and zip (WA98040 -> WA 98040)
        - Street abbreviations (Pl -> Place, St -> Street, etc.)

        Args:
            address: Raw address input from user

        Returns:
            Normalized address suitable for Redfin search
        """
        normalized = address

        # Fix missing space between state abbreviation and zip code
        # Matches patterns like "WA98040" (2-letter state + 5-digit zip)
        normalized = re.sub(r'\b([A-Za-z]{2})(\d{5})\b', r'\1 \2', normalized)

        # Normalize common street type abbreviations to full form
        # Redfin's search works better with full forms
        street_abbrevs = [
            (r'\bPl\b', 'Place'),
            (r'\bSt\b', 'Street'),
            (r'\bAve\b', 'Avenue'),
            (r'\bBlvd\b', 'Boulevard'),
            (r'\bDr\b', 'Drive'),
            (r'\bLn\b', 'Lane'),
            (r'\bRd\b', 'Road'),
            (r'\bCt\b', 'Court'),
            (r'\bCir\b', 'Circle'),
            (r'\bPkwy\b', 'Parkway'),
            (r'\bHwy\b', 'Highway'),
            (r'\bTer\b', 'Terrace'),
        ]
        for abbrev, full in street_abbrevs:
            # Case-insensitive replacement, preserving original case style
            normalized = re.sub(abbrev, full, normalized, flags=re.IGNORECASE)

        if normalized != address:
            logger.info(f"Normalized address for search: '{address}' -> '{normalized}'")

        return normalized

    async def _perform_search(self, page: Page, address: str, max_retries: int = 3) -> bool:
        """Perform search with retry logic for dynamic DOM."""
        # Normalize address for better Redfin search results
        search_address = self._normalize_address_for_search(address)

        for attempt in range(max_retries):
            try:
                # Wait a bit for page to stabilize
                await asyncio.sleep(1)

                # Try multiple search input selectors
                search_selectors = [
                    '#search-box-input',
                    'input[placeholder*="City"]',
                    'input[placeholder*="Address"]',
                    'input[type="search"]',
                    'input[class*="search"]',
                    'input[aria-label*="search"]',
                ]

                search_input = None
                for selector in search_selectors:
                    try:
                        search_input = await page.wait_for_selector(selector, timeout=5000)
                        if search_input and await search_input.is_visible():
                            break
                    except Exception:
                        continue

                if not search_input:
                    logger.warning(f"Search attempt {attempt + 1}: No search input found")
                    await asyncio.sleep(2)
                    continue

                # Clear and fill with fresh element reference
                await search_input.click(timeout=5000)
                await asyncio.sleep(0.5)

                # Use keyboard to clear and type (more reliable than fill)
                await page.keyboard.press("Control+a")
                await page.keyboard.type(search_address, delay=30)  # Reduced delay from 50ms
                await asyncio.sleep(1.5)  # Reduced from 2s

                # Press Enter
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)  # Reduced from 3s

                return True

            except Exception as e:
                logger.warning(f"Search attempt {attempt + 1} failed: {e}")
                # Dismiss any popups that might have appeared
                await self._dismiss_popups(page)
                await asyncio.sleep(2)

        return False

    async def _handle_disambiguation_popup(self, page: Page) -> bool:
        """
        Handle Redfin's "Did you mean" disambiguation popup.

        When an address has multiple matches (e.g., similar street names),
        Redfin shows a popup asking the user to clarify. This method:
        1. Collects all disambiguation options
        2. Checks each one for active listing status
        3. Prefers active listings over off-market ones

        Returns:
            True if disambiguation popup was handled, False if not found
        """
        try:
            # Check for "Did you mean" popup - various possible selectors
            disambiguation_selectors = [
                # Dialog/modal with address suggestions
                '[role="dialog"] a[href*="/home/"]',
                '[role="dialog"] a[href*="/WA/"]',
                '.disambiguate a',
                '.SearchResultsDisambiguate a',
                # Autocomplete dropdown with address matches
                '.SearchInputAutocomplete a[href*="/home/"]',
                '.SearchInputAutocomplete a[href*="/WA/"]',
                '[data-rf-test-name="search-box-autocomplete"] a',
                # Generic modal address links
                '.modal a[href*="/home/"]',
                '[class*="modal"] a[href*="/home/"]',
                '[class*="dialog"] a[href*="/home/"]',
            ]

            # Collect all disambiguation URLs
            all_urls = []
            for selector in disambiguation_selectors:
                try:
                    results = await page.query_selector_all(selector)
                    for result in results:
                        if await result.is_visible():
                            href = await result.get_attribute('href')
                            if href:
                                if not href.startswith('http'):
                                    href = f"https://www.redfin.com{href}"
                                if href not in all_urls:
                                    all_urls.append(href)
                except Exception:
                    continue

            if not all_urls:
                return False

            logger.info(f"Disambiguation popup found with {len(all_urls)} options: {all_urls}")

            # If only one option, just use it
            if len(all_urls) == 1:
                await page.goto(all_urls[0], wait_until="domcontentloaded", timeout=30000)
                return True

            # Try each URL and prefer active listings
            first_url = all_urls[0]  # Fallback
            for url in all_urls:
                try:
                    logger.info(f"Checking disambiguation option: {url}")
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(1)

                    # Check if this is an active listing
                    is_active = await self._is_active_listing(page)
                    if is_active:
                        logger.info(f"Found active listing: {url}")
                        return True
                    else:
                        logger.info(f"Listing is off-market, trying next option...")

                except Exception as e:
                    logger.warning(f"Error checking {url}: {e}")
                    continue

            # No active listing found, use first URL as fallback
            logger.info(f"No active listings found, using first option: {first_url}")
            await page.goto(first_url, wait_until="domcontentloaded", timeout=30000)
            return True

        except Exception as e:
            logger.debug(f"Disambiguation popup check failed: {e}")
            return False

    async def _is_active_listing(self, page: Page) -> bool:
        """
        Check if the current property page is an active listing (For Sale).

        Returns False for off-market, sold, pending, or other inactive statuses.
        Uses specific status elements first, then falls back to targeted page sections.
        """
        try:
            # FIRST: Check specific Redfin status elements (most reliable)
            status_selectors = [
                '[data-rf-test-name="abp-status"]',
                '[data-rf-test-name="homeStatus"]',
                '.HomeStatus',
                '.PropertyPageStatus',
                '.HomeInfoV2 .status',
                '.ListingStatusBannerSection',
                '.above-the-fold .status',
                '.propertyStatus',
            ]

            for selector in status_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        text_lower = text.lower().strip()
                        logger.debug(f"Status element '{selector}' text: {text_lower}")

                        # Check for inactive
                        if any(ind in text_lower for ind in ['off market', 'off-market', 'sold', 'not for sale', 'no longer']):
                            logger.info(f"Status element shows inactive: {text_lower}")
                            return False
                        # Check for active
                        if any(ind in text_lower for ind in ['for sale', 'active', 'coming soon', 'pending', 'contingent']):
                            logger.info(f"Status element shows active: {text_lower}")
                            return True
                except Exception:
                    continue

            # SECOND: Check the main header/banner area only (not full page)
            # Look for prominent status text near the top of the page
            header_selectors = [
                '.HomeMainStats',
                '.HomeInfo',
                '.above-the-fold',
                'header',
                '[class*="Banner"]',
                '[class*="Status"]',
            ]

            for selector in header_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        text_lower = text.lower()

                        # Off-market indicators (specific phrases)
                        if 'off market' in text_lower or 'off-market' in text_lower:
                            # Make sure it's about THIS property, not a sidebar link
                            if 'this home' in text_lower or 'this property' in text_lower or text_lower.startswith('off'):
                                logger.info(f"Header indicates off-market")
                                return False

                        # For sale indicators
                        if 'for sale' in text_lower:
                            logger.info(f"Header indicates for sale")
                            return True
                except Exception:
                    continue

            # THIRD: Check page title which usually shows status
            try:
                title = await page.title()
                title_lower = title.lower()
                logger.debug(f"Page title: {title_lower}")

                if 'off market' in title_lower or 'sold' in title_lower:
                    logger.info(f"Page title indicates off-market: {title}")
                    return False
                if 'for sale' in title_lower:
                    logger.info(f"Page title indicates for sale: {title}")
                    return True
            except Exception:
                pass

            # FOURTH: Check for a price element (active listings usually show price prominently)
            try:
                price_selectors = [
                    '[data-rf-test-name="abp-price"]',
                    '.price',
                    '.HomeMainStats .price',
                    '.statsValue',
                ]
                for selector in price_selectors:
                    price_el = await page.query_selector(selector)
                    if price_el:
                        price_text = await price_el.inner_text()
                        # If there's a clear price with $, likely active
                        if '$' in price_text and any(c.isdigit() for c in price_text):
                            # But also check it's not "Sold for $X"
                            parent = await price_el.evaluate('el => el.parentElement?.innerText || ""')
                            if 'sold' not in parent.lower():
                                logger.info(f"Found active price: {price_text}")
                                return True
            except Exception:
                pass

            # Default: assume active if we can't determine
            logger.info("Could not determine listing status, assuming active")
            return True

        except Exception as e:
            logger.warning(f"Error checking listing status: {e}")
            return True  # Default to active on error

    async def _click_first_result(self, page: Page, max_retries: int = 3):
        """Click the first search result with retry logic."""
        # First check for disambiguation popup ("Did you mean" dialog)
        if await self._handle_disambiguation_popup(page):
            logger.info("Handled disambiguation popup successfully")
            return

        result_selectors = [
            '.HomeCardContainer a',
            '.HomeCard a',
            '[data-rf-test-name="basic-card-photo"]',
            '.MapHomeCard a',
            'a[href*="/home/"]',
        ]

        for attempt in range(max_retries):
            try:
                await asyncio.sleep(1)

                # Check disambiguation popup again on each retry
                if await self._handle_disambiguation_popup(page):
                    return

                for selector in result_selectors:
                    try:
                        # Wait for selector and verify it's still attached
                        result = await page.wait_for_selector(selector, timeout=5000)
                        if result and await result.is_visible():
                            # Get href and navigate directly (more reliable than clicking)
                            href = await result.get_attribute('href')
                            if href:
                                if not href.startswith('http'):
                                    href = f"https://www.redfin.com{href}"
                                logger.info(f"Navigating to property: {href}")
                                await page.goto(href, wait_until="domcontentloaded", timeout=30000)
                                return
                            else:
                                # Fallback to click
                                await result.click(timeout=5000)
                                await asyncio.sleep(3)
                                return
                    except Exception as e:
                        logger.debug(f"Selector {selector} failed: {e}")
                        continue

                logger.warning(f"Click result attempt {attempt + 1}: No clickable result found")
                await asyncio.sleep(2)

            except Exception as e:
                logger.warning(f"Click result attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2)

        logger.warning("Could not click any search result after all retries")

    async def _extract_data_from_screenshots(
        self,
        screenshots: List[Dict[str, Any]],
        address: str
    ) -> Dict[str, Any]:
        """
        Send screenshots to Claude Vision and extract structured property data.
        """
        logger.info(f"Extracting data from {len(screenshots)} screenshots...")

        # Build message content with images
        content = [
            {
                "type": "text",
                "text": f"Extract property data for: {address}\n\n{EXTRACTION_PROMPT}"
            }
        ]

        # Add screenshots as images (we now have 10 optimized positions)
        # Filter out any screenshots with empty data
        for screenshot in screenshots[:10]:
            if not screenshot.get("data"):
                logger.warning(f"Skipping empty screenshot: {screenshot.get('name', 'unknown')}")
                continue
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot["data"]
                }
            })

        try:
            # Call Claude Vision API
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": content
                }]
            )

            # Track cost
            self.api_calls += 1
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            call_cost = (
                input_tokens * self.COST_PER_INPUT_TOKEN +
                output_tokens * self.COST_PER_OUTPUT_TOKEN
            )
            self.total_cost += call_cost

            self.api_call_details.append({
                "model": "claude-sonnet-4-20250514",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": round(call_cost, 6)
            })

            logger.info(f"Vision extraction API call: {input_tokens} input, {output_tokens} output tokens = ${call_cost:.6f}")

            # Extract JSON from response
            response_text = response.content[0].text

            # Try to parse JSON
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                extracted_data = json.loads(json_match.group(0))

                # Merge in the main photo URL extracted via Playwright
                if self._current_main_photo_url:
                    if "images" not in extracted_data:
                        extracted_data["images"] = {}
                    extracted_data["images"]["main_photo_url"] = self._current_main_photo_url
                    logger.info(f"Added main_photo_url to extracted data")

                return extracted_data
            else:
                logger.error("No JSON found in Claude response")
                return {"error": "No JSON extracted", "raw_response": response_text[:500]}

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {"error": f"JSON parse error: {e}"}
        except Exception as e:
            logger.error(f"Claude API error: {e}", exc_info=True)
            return {"error": str(e)}

    async def _save_extracted_data(self, address: str, data: Dict[str, Any]):
        """
        Save extracted data to JSON and MD files.
        Enriches data with region detection and commute times before saving.
        """
        # Enrich with region & commute data
        await self._enrich_with_region_data(address, data)

        address_slug = self._create_slug(address)

        # Save JSON
        json_path = self.property_data_dir / f"{address_slug}.json"
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved JSON: {json_path}")

        # Generate and save Markdown summary
        md_content = self._generate_markdown(address, data)
        md_path = self.property_data_dir / f"{address_slug}.md"
        with open(md_path, 'w') as f:
            f.write(md_content)
        logger.info(f"Saved Markdown: {md_path}")

    async def _enrich_with_region_data(self, address: str, data: Dict[str, Any]):
        """Detect region and fetch commute times, storing results in data['region_info']."""
        try:
            from app.services.agent.skills.location_skill import parse_hot_areas, detect_region, HOT_AREAS_PATH
            from app.services.data_collectors.google_maps_service import google_maps_service

            hot_areas = parse_hot_areas(os.path.normpath(HOT_AREAS_PATH))
            region = detect_region(address, hot_areas)

            # Collect all hot areas across all regions
            all_destinations = []
            for r, destinations in hot_areas.items():
                for d in destinations:
                    all_destinations.append({**d, "_region": r})

            region_info: Dict[str, Any] = {"region": region or "Unknown", "commute_to_hot_areas": []}

            if all_destinations:
                logger.info(f"Detected region '{region}' for {address}, fetching commute times to {len(all_destinations)} hot areas")
                commute_data = await google_maps_service.get_commute_times(address, all_destinations)
                # Tag each result with its sub-region
                for i, c in enumerate(commute_data):
                    c["sub_region"] = all_destinations[i]["_region"]
                region_info["commute_to_hot_areas"] = commute_data

            data["region_info"] = region_info
        except Exception as e:
            logger.warning(f"Region enrichment failed for {address}: {e}")
            data["region_info"] = {"region": "Unknown", "commute_to_hot_areas": []}

    @staticmethod
    def _fmt_price(value) -> str:
        """Format a price value with commas, or return 'N/A'."""
        if value is None or value == 'N/A':
            return 'N/A'
        try:
            return f"{int(value):,}"
        except (ValueError, TypeError):
            return str(value)

    def _generate_markdown(self, address: str, data: Dict[str, Any]) -> str:
        """Generate a human-readable markdown summary."""

        prop = data.get("property", {}) or {}
        pricing = data.get("pricing", {}) or {}
        details = data.get("details", {}) or {}
        schools = data.get("schools", []) or []
        location = data.get("location", {}) or {}
        climate = data.get("climate_risks", {}) or {}
        meta = data.get("_metadata", {}) or {}
        region_info = data.get("region_info", {}) or {}

        fmt = self._fmt_price

        md = f"""# Property Analysis: {address}

**Extraction Date:** {meta.get('extraction_date', 'N/A')}
**Source:** Redfin
**Status:** {prop.get('status', 'N/A')}

---

## Property Description

> {prop.get('description', 'No description available')}

---

## Pricing

| Metric | Value |
|--------|-------|
| List Price | ${fmt(pricing.get('list_price'))} |
| Redfin Estimate | ${fmt(pricing.get('redfin_estimate'))} |
| Price/Sq Ft | ${fmt(pricing.get('price_per_sqft'))} |
| Rental Estimate | ${fmt(pricing.get('rental_estimate'))}/mo |

---

## Property Details

| Feature | Value |
|---------|-------|
| Type | {details.get('property_type', 'N/A')} |
| Year Built | {details.get('year_built', 'N/A')} |
| Bedrooms | {details.get('bedrooms', 'N/A')} |
| Bathrooms | {details.get('bathrooms', 'N/A')} |
| Living Area | {fmt(details.get('living_area_sqft'))} sq ft |
| Lot Size | {fmt(details.get('lot_size_sqft'))} sq ft |
| Parking | {details.get('parking', 'N/A')} |

---

## Schools

| School | Type | Rating | Distance |
|--------|------|--------|----------|
"""
        for school in schools[:5]:
            md += f"| {school.get('name', 'N/A')} | {school.get('type', 'N/A')} | {school.get('rating', 'N/A')}/10 | {school.get('distance', 'N/A')} |\n"

        md += f"""
---

## Location Scores

| Category | Score |
|----------|-------|
| Walkability | {location.get('walkability_score', 'N/A')}/10 |
| Transit | {location.get('transit_score', 'N/A')}/10 |
| Bike | {location.get('bike_score', 'N/A')}/10 |

---

## Region & Commute

**Region:** {region_info.get('region', 'Unknown')}

"""
        commute_areas = region_info.get("commute_to_hot_areas", [])
        if commute_areas:
            md += "| Destination | Drive | Transit |\n"
            md += "|-------------|-------|--------|\n"
            for c in commute_areas:
                drive = f"{c['drive_minutes']} min" if c.get('drive_minutes') is not None else "N/A"
                transit = f"{c['transit_minutes']} min" if c.get('transit_minutes') is not None else "N/A"
                md += f"| {c['name']} | {drive} | {transit} |\n"
        else:
            md += "*No commute data available (GOOGLE_MAPS_API_KEY not set or region not recognized)*\n"

        md += f"""
---

## Climate Risks

| Factor | Risk Level |
|--------|------------|
| Flood | {climate.get('flood', 'N/A')} |
| Fire | {climate.get('fire', 'N/A')} |
| Heat | {climate.get('heat', 'N/A')} |
| Air Quality | {climate.get('air_quality', 'N/A')} |

---

## Extraction Metadata

- Screenshots: {meta.get('screenshots_count', 'N/A')}
- API Calls: {meta.get('api_calls', 'N/A')}
- Total Cost: ${meta.get('total_cost', 0):.4f}
- Extraction Time: {meta.get('extraction_time_seconds', 'N/A')}s

---

*Data extracted from Redfin using Claude Vision*
"""
        return md

    def _create_slug(self, address: str) -> str:
        """Create a filename-safe slug from address."""
        # Remove special characters, lowercase, replace spaces with underscores
        slug = re.sub(r'[^\w\s-]', '', address.lower())
        slug = re.sub(r'[\s-]+', '_', slug)
        return slug[:50]  # Limit length
