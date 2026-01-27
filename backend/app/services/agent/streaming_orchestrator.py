"""
Streaming Analysis Orchestrator

Coordinates streaming property analysis with progressive updates:
1. Checks for existing cached notes to avoid re-extraction
2. Takes Chromium screenshots of Redfin property pages
3. Extracts structured data via Claude Vision
4. Streams extracted data to frontend via SSE
5. Saves JSON/MD files for later LLM analysis

Architecture:
- Screenshot Extractor: Chromium headless + Claude Vision (~$0.08/property)
- Server-Sent Events: Progressive streaming to frontend
- Notes Cache: Reuses existing notes to skip redundant extraction
"""
import logging
import json
import re
from typing import Dict, Any, AsyncGenerator, Optional
from datetime import datetime

from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector
from app.services.agent.tools.notes_manager import get_notes_manager

logger = logging.getLogger(__name__)


class StreamingAnalysisOrchestrator:
    """
    Orchestrates streaming property analysis with progressive updates.

    Flow:
    1. Check if notes already exist for this address (cache hit)
    2. If cached: replay extracted data from notes
    3. If not cached: run screenshot extraction pipeline
    """

    def __init__(self):
        """Initialize the orchestrator with screenshot extractor collector."""
        self.redfin_collector = ScreenshotExtractorCollector()
        logger.info("Using Screenshot Extractor (Chromium + Claude Vision)")

        self.step_data = {}
        self.notes_manager = get_notes_manager()

    def _parse_cached_data(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Check if complete extracted data exists in notes for this address.

        Returns the cached all_data dict if found, None otherwise.
        """
        if not self.notes_manager.notes_exist(address):
            return None

        notes_content = self.notes_manager.read_notes(address)
        if not notes_content:
            return None

        # Extract all "Extraction Complete" sections (delimited by --- or end of file)
        sections = re.findall(
            r'## Extraction Complete\n(.*?)(?=\n## |\Z)',
            notes_content,
            re.DOTALL
        )
        if not sections:
            logger.info(f"Notes exist but no Extraction Complete section for: {address}")
            return None

        # Try each section (last one is most recent)
        for section_content in reversed(sections):
            # Try fenced JSON first (new format)
            fenced = re.search(r'```json\s*\n(.+?)\n```', section_content, re.DOTALL)
            if fenced:
                try:
                    cached_data = json.loads(fenced.group(1))
                    if "property" in cached_data:
                        logger.info(f"Found cached data (fenced) for: {address}")
                        return cached_data
                except json.JSONDecodeError:
                    pass

            # Try raw JSON (old format): find outermost { ... }
            raw = re.search(r'(\{.+\})', section_content, re.DOTALL)
            if raw:
                try:
                    cached_data = json.loads(raw.group(1))
                    if "property" in cached_data:
                        logger.info(f"Found cached data (raw) for: {address}")
                        return cached_data
                except json.JSONDecodeError:
                    pass

        logger.info(f"Notes exist but could not parse extraction data for: {address}")
        return None

    async def _yield_cached_data(self, address: str, cached_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yield cached data as streaming events, matching the same format
        as a live extraction so the frontend renders identically.
        """
        yield {"type": "init", "status": "started", "address": address, "mode": "cached"}
        yield {"type": "status", "message": "Using cached data from previous extraction..."}

        # Reconstruct step events from cached data
        prop = cached_data.get("property", {})
        pricing = cached_data.get("pricing", {})
        details = cached_data.get("details", {})
        schools = cached_data.get("schools", [])
        climate = cached_data.get("climate_risks", {})
        location = cached_data.get("location", {})
        market = cached_data.get("market_trends", {})

        steps = [
            (2, "Property Overview", {
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
            }),
            (3, "Pricing & Estimates", pricing),
            (4, "Schools", {"schools": schools}),
            (5, "Location & Lifestyle", {**location, **market}),
            (6, "Climate Risks", climate),
        ]

        for step_num, step_name, step_data in steps:
            yield {
                "type": "data",
                "step": step_num,
                "step_name": step_name,
                "data": step_data,
                "status": "scraped",
                "message": f"Cached: {step_name}",
                "cost_so_far": 0
            }

        # Final summary
        yield {
            "type": "summary",
            "content": json.dumps(cached_data, indent=2, default=str),
            "extracted_data": cached_data,
            "status": "complete",
            "total_scraping_cost": 0,
            "total_analysis_cost": 0,
            "total_cost": 0,
            "total_time": 0,
            "cached": True
        }

    async def analyze_streaming(self, address: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream analysis results as they become available.

        First checks for cached notes. If complete data exists, replays it
        without running the extraction pipeline. Otherwise runs fresh extraction.
        """
        logger.info(f"Starting streaming analysis for: {address}")
        start_time = datetime.utcnow()

        try:
            # Check for cached data in existing notes
            cached_data = self._parse_cached_data(address)
            if cached_data:
                logger.info(f"Cache hit for: {address} — skipping extraction")
                async for event in self._yield_cached_data(address, cached_data):
                    yield event
                return

            logger.info(f"No cache for: {address} — running extraction")

            # Create notes file
            self.notes_manager.create_notes(address, {"address": address})

            # Yield initial status
            yield {
                "type": "status",
                "message": f"Starting property analysis for {address}...",
                "timestamp": start_time.isoformat()
            }

            # Start streaming scraper
            async for scrape_event in self.redfin_collector.scrape_property_streaming(address):

                # Forward init/status events directly
                if scrape_event["type"] in ["init", "status"]:
                    yield scrape_event
                    continue

                # Handle step completion
                if scrape_event["type"] == "step_complete":
                    step_number = scrape_event["step"]
                    step_name = scrape_event["step_name"]
                    step_data = scrape_event.get("data", {})

                    logger.info(f"Step {step_number} ({step_name}) extracted")

                    yield {
                        "type": "data",
                        "step": step_number,
                        "step_name": step_name,
                        "data": step_data,
                        "status": "scraped",
                        "message": f"Extracted: {step_name}",
                        "cost_so_far": scrape_event.get("cost_so_far", 0)
                    }

                    # Save raw scraped data to notes
                    if step_data:
                        self.notes_manager.append_raw_scraped_data(
                            address=address,
                            scraped_data=step_data,
                            source=f"redfin_{step_name.lower().replace(' ', '_')}"
                        )

                    self.step_data[step_name] = scrape_event

                # Handle completion
                elif scrape_event["type"] == "complete":
                    logger.info("Extraction complete")

                    all_data = scrape_event.get("all_data", {})

                    # Save complete data to notes
                    self.notes_manager.append_section(
                        address=address,
                        section_title="Extraction Complete",
                        content="```json\n" + json.dumps(all_data, indent=2, default=str) + "\n```",
                        metadata={
                            "Total Cost": f"${scrape_event['total_cost']:.4f}",
                            "Total Time": f"{scrape_event['total_time']:.1f}s",
                            "Status": "Complete"
                        }
                    )

                    logger.info(f"Saved notes to: {self.notes_manager.get_notes_path(address)}")

                    yield {
                        "type": "summary",
                        "content": json.dumps(all_data, indent=2, default=str),
                        "extracted_data": all_data,
                        "status": "complete",
                        "total_scraping_cost": scrape_event["total_cost"],
                        "total_analysis_cost": 0,
                        "total_cost": scrape_event["total_cost"],
                        "total_time": scrape_event["total_time"]
                    }

                # Handle errors
                elif scrape_event["type"] == "error":
                    logger.error(f"Scraping error: {scrape_event['error']}")
                    yield scrape_event

        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e)
            }

