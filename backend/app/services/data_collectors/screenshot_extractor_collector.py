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


# Scroll positions to capture (matches the extraction schema)
SCROLL_POSITIONS = [
    (0, "property_top"),
    (700, "scroll_700"),
    (1400, "scroll_1400"),
    (2100, "scroll_2100"),
    (2800, "scroll_2800"),
    (3500, "scroll_3500"),
    (4200, "scroll_4200"),
    (4900, "scroll_4900"),
    (5600, "scroll_5600"),
    (6300, "scroll_6300"),
    (7000, "scroll_7000"),
    (7700, "scroll_7700"),
    (8400, "scroll_8400"),
    (9100, "scroll_9100"),
    (9800, "scroll_9800"),
    (10500, "scroll_10500"),
    (11200, "scroll_11200"),
    (11900, "scroll_11900"),
    (12600, "scroll_12600"),
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
    "main_photo_visible": boolean
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
                # Launch Chromium
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage'
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
                await asyncio.sleep(3)

                # Close any popups (like Google sign-in)
                try:
                    close_buttons = await page.query_selector_all('[aria-label="Close"], .close, [data-testid="close"]')
                    for btn in close_buttons:
                        await btn.click()
                        await asyncio.sleep(0.5)
                except:
                    pass

                # Search for the address
                logger.info(f"Searching for: {address}")
                try:
                    search_input = await page.wait_for_selector('input[placeholder*="City"], input[placeholder*="Address"], input[type="search"], #search-box-input', timeout=15000)
                except:
                    # Try alternate selector
                    search_input = await page.query_selector('input[class*="search"]') or await page.query_selector('input[aria-label*="search"]')

                if search_input:
                    await search_input.click()
                    await search_input.fill(address)
                    await asyncio.sleep(2)
                else:
                    logger.error("Could not find search input")
                    await browser.close()
                    return screenshots

                # Press Enter or click search
                await page.keyboard.press("Enter")
                await asyncio.sleep(3)

                # Check if we're on a property page or search results
                current_url = page.url
                logger.info(f"Current URL: {current_url}")

                # If on search results, click the first result
                if "/redfin-search" in current_url or "searchResults" in current_url:
                    logger.info("On search results, clicking first result...")
                    try:
                        first_result = await page.wait_for_selector('.HomeCardContainer a, .HomeCard a, [data-rf-test-name="basic-card-photo"]', timeout=10000)
                        await first_result.click()
                        await asyncio.sleep(3)
                    except:
                        logger.warning("Could not find search result to click")

                # Wait for property page to load
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
                await asyncio.sleep(3)

                # Create address slug for filenames
                address_slug = self._create_slug(address)
                screenshot_dir = self.screenshots_dir / address_slug
                screenshot_dir.mkdir(parents=True, exist_ok=True)

                # Take screenshots at different scroll positions
                for i, (scroll_pos, name) in enumerate(SCROLL_POSITIONS):
                    try:
                        # Scroll to position
                        await page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                        await asyncio.sleep(0.5)

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

        # Add screenshots as images (limit to first 15 to manage costs)
        # Filter out any screenshots with empty data
        for screenshot in screenshots[:15]:
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
