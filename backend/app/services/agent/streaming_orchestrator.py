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
import asyncio
import logging
import json
import re
from typing import Dict, Any, AsyncGenerator, Optional, List
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector
from app.services.agent.tools.notes_manager import get_notes_manager
from app.services.agent.skills.property_skill import PropertySkill
from app.services.agent.skills.location_skill import LocationSkill
from app.services.agent.skills.school_skill import SchoolSkill
from app.services.agent.skills.investment_skill import InvestmentSkill
from app.services.agent.skills.sale_price_skill import SalePriceSkill
from app.services.analysis_logging_service import AnalysisLoggingService
from app.services.knowledge.search_service import get_search_service
from app.models.analysis_log import ANALYSIS_STEPS
from app.config import settings

logger = logging.getLogger(__name__)


def _apply_margin(cost: float) -> float:
    """Apply pricing margin to convert internal cost to user-facing price."""
    if settings.PRICING_MARGIN >= 1.0:
        return cost
    return cost / (1.0 - settings.PRICING_MARGIN)


class StreamingAnalysisOrchestrator:
    """
    Orchestrates streaming property analysis with progressive updates.

    Flow:
    1. Check if notes already exist for this address (cache hit)
    2. If cached: replay extracted data from notes
    3. If not cached: run screenshot extraction pipeline
    """

    def __init__(
        self,
        db: Optional[Session] = None,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ):
        """
        Initialize the orchestrator with screenshot extractor collector.

        Args:
            db: Database session for logging (optional)
            user_id: User ID if authenticated (optional)
            client_ip: Client IP address (optional)
        """
        self.redfin_collector = ScreenshotExtractorCollector()
        logger.info("Using Screenshot Extractor (Chromium + Claude Vision)")

        self.step_data = {}
        self.notes_manager = get_notes_manager()
        self.property_skill = PropertySkill()
        self.location_skill = LocationSkill()
        self.school_skill = SchoolSkill()
        self.investment_skill = InvestmentSkill()
        self.sale_price_skill = SalePriceSkill()

        # Logging context
        self.db = db
        self.user_id = user_id
        self.client_ip = client_ip
        self.logging_service: Optional[AnalysisLoggingService] = None
        self.current_job = None
        self.current_job_id: Optional[str] = None  # Store ID as string to avoid DetachedInstanceError
        self.current_step_log = None

        if db:
            self.logging_service = AnalysisLoggingService(db)

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

    def _parse_cached_analysis(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Parse cached analysis results from the notes file.

        Looks for sections "Property Analysis", "Location Analysis",
        "School Analysis", "Investment Analysis", "Sale Price Analysis" —
        each containing a ```json ... ``` block with the full skill result.

        Returns dict with found analyses if the core 4 are present.
        Sale Price Analysis is optional for backwards compatibility.
        """
        if not self.notes_manager.notes_exist(address):
            return None

        notes_content = self.notes_manager.read_notes(address)
        if not notes_content:
            return None

        # Core 4 are required, sale_price is optional
        required_sections = {
            "Property Analysis": "property",
            "Location Analysis": "location",
            "School Analysis": "schools",
            "Investment Analysis": "investment",
        }
        optional_sections = {
            "Sale Price Analysis": "sale_price",
        }

        cached_analysis = {}

        # Check required sections first
        for section_title, key in required_sections.items():
            # Find the section and extract its JSON block
            pattern = rf'## {re.escape(section_title)}\n(.*?)(?=\n## |\Z)'
            matches = re.findall(pattern, notes_content, re.DOTALL)
            if not matches:
                logger.info(f"Cached analysis missing required section: {section_title}")
                return None

            # Use the last (most recent) match
            section_content = matches[-1]
            fenced = re.search(r'```json\s*\n(.+?)\n```', section_content, re.DOTALL)
            if not fenced:
                logger.info(f"Cached analysis section '{section_title}' has no JSON block")
                return None

            try:
                cached_analysis[key] = json.loads(fenced.group(1))
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON in cached '{section_title}'")
                return None

        # Check optional sections
        for section_title, key in optional_sections.items():
            pattern = rf'## {re.escape(section_title)}\n(.*?)(?=\n## |\Z)'
            matches = re.findall(pattern, notes_content, re.DOTALL)
            if matches:
                section_content = matches[-1]
                fenced = re.search(r'```json\s*\n(.+?)\n```', section_content, re.DOTALL)
                if fenced:
                    try:
                        cached_analysis[key] = json.loads(fenced.group(1))
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON in optional cached '{section_title}'")

        logger.info(f"Found {len(cached_analysis)} cached analysis results for: {address}")
        return cached_analysis

    def _start_step_logging(self, step_number: int) -> Optional[str]:
        """Start logging a step and return the step log ID."""
        if not self.logging_service or not self.current_job_id:
            return None

        step_def = None
        for s in ANALYSIS_STEPS:
            if s["number"] == step_number:
                step_def = s
                break

        if not step_def:
            return None

        step_log = self.logging_service.start_step(
            job_id=self.current_job_id,
            step_number=step_number,
            step_name=step_def["name"],
            step_type=step_def["type"],
        )
        return step_log.id

    def _complete_step_logging(
        self,
        step_log_id: Optional[str],
        cost: float = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Complete a step log."""
        if not self.logging_service or not step_log_id:
            return

        self.logging_service.complete_step(
            step_log_id=step_log_id,
            cost=cost,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            metadata=metadata,
        )

    def _fail_step_logging(self, step_log_id: Optional[str], error: str) -> None:
        """Fail a step log."""
        if not self.logging_service or not step_log_id:
            return
        self.logging_service.fail_step(step_log_id, error)

    async def _yield_cached_data(self, address: str, cached_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yield cached data as streaming events, matching the same format
        as a live extraction so the frontend renders identically.
        """
        start_time = datetime.utcnow()

        # Log cache check step
        cache_step_id = self._start_step_logging(1)
        self._complete_step_logging(cache_step_id, metadata={"cache_hit": True})

        yield {"type": "init", "status": "started", "address": address, "mode": "cached"}
        yield {"type": "status", "message": "Loading property data..."}
        await asyncio.sleep(0.8)

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
            # Log extraction steps (cached replay - no actual cost)
            step_log_id = self._start_step_logging(step_num)
            self._complete_step_logging(step_log_id, metadata={"cached": True})

            yield {
                "type": "data",
                "step": step_num,
                "step_name": step_name,
                "data": step_data,
                "status": "scraped",
                "message": f"Extracted: {step_name}",
                "cost_so_far": 0
            }
            await asyncio.sleep(0.8)

        # Check for cached analysis results before running skills
        cached_analysis = self._parse_cached_analysis(address)

        if cached_analysis:
            # Analysis results are cached — replay them without calling LLM
            # Stagger delivery so the user sees progressive loading

            analysis_skill_map = [
                (7, "Property Condition", "property", "Reviewing property condition..."),
                (8, "Location & Commute", "location", "Evaluating location quality..."),
                (9, "School Quality", "schools", "Analyzing nearby schools..."),
                (10, "Investment Potential", "investment", "Calculating investment metrics..."),
                (12, "Sale Price Prediction", "sale_price", "Predicting sale price..."),
            ]

            analysis_results = {}
            for step_num, step_name, skill_key, status_msg in analysis_skill_map:
                # Skip if this skill result isn't cached (backwards compatibility)
                if skill_key not in cached_analysis:
                    continue
                step_log_id = self._start_step_logging(step_num)
                yield {"type": "status", "message": status_msg}
                await asyncio.sleep(3.5)
                result = cached_analysis[skill_key]
                analysis_results[skill_key] = result

                # Log cached analysis step with original cost
                original_cost = result.get('cost_summary', {}).get('total_cost', 0)
                self._complete_step_logging(
                    step_log_id,
                    cost=0,  # No new cost for cached
                    metadata={"cached": True, "original_cost": original_cost}
                )

                yield {
                    "type": "analysis",
                    "step": step_num,
                    "step_name": step_name,
                    "skill": skill_key,
                    "analysis": self._format_analysis_markdown(result, step_name),
                    "data": result,
                }

            # Recover original analysis cost from cached results
            original_analysis_cost = sum(
                r.get('cost_summary', {}).get('total_cost', 0)
                for r in cached_analysis.values()
            )
            analysis_cost = original_analysis_cost

        else:
            # Some or all analysis missing — run all skills
            analysis_results = {}
            analysis_cost = 0
            async for analysis_event in self._run_analysis_skills(address, cached_data):
                if analysis_event["type"] == "analysis_complete":
                    analysis_results = analysis_event.get("results", {})
                    analysis_cost = analysis_event.get("analysis_cost", 0)
                yield analysis_event

        # Step 11: Generic Knowledge / Property Insights (with timeout to avoid blocking SSE)
        try:
            generic_knowledge, insights_debug = await asyncio.wait_for(
                self._prepare_generic_knowledge(cached_data),
                timeout=45.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Property insights timed out after 45s, skipping")
            generic_knowledge, insights_debug = [], {"error": "timeout"}
        if generic_knowledge:
            yield {
                "type": "generic_knowledge",
                "step": 11,
                "step_name": "Property Insights",
                "data": {
                    "knowledge_points": generic_knowledge,
                    "debug": insights_debug,
                },
            }

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        # Complete job logging
        if self.logging_service and self.current_job_id:
            self.logging_service.complete_job(self.current_job_id, is_cached=True)

        # Cached replay: cost is 0 here. Per-user billing is handled by the endpoint.
        yield {
            "type": "summary",
            "content": json.dumps(cached_data, indent=2, default=str),
            "extracted_data": cached_data,
            "analysis_results": analysis_results,
            "status": "complete",
            "total_scraping_cost": 0,
            "total_analysis_cost": _apply_margin(analysis_cost),
            "total_cost": _apply_margin(analysis_cost),
            "total_time": elapsed,
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

        # Create analysis job for logging
        if self.logging_service:
            self.current_job = self.logging_service.create_analysis_job(
                address=address,
                user_id=self.user_id,
                client_ip=self.client_ip,
            )
            self.current_job_id = str(self.current_job.id)
            logger.info(f"Created analysis job: {self.current_job_id}")

        try:
            # Check for cached data in existing notes
            cached_data = self._parse_cached_data(address)
            if cached_data:
                logger.info(f"Cache hit for: {address} — skipping extraction")
                async for event in self._yield_cached_data(address, cached_data):
                    yield event
                return

            logger.info(f"No cache for: {address} — running extraction")

            # Log cache miss
            cache_step_id = self._start_step_logging(1)
            self._complete_step_logging(cache_step_id, metadata={"cache_hit": False})

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
                    step_cost = scrape_event.get("step_cost", 0)

                    logger.info(f"Step {step_number} ({step_name}) extracted")

                    # Log the extraction step
                    step_log_id = self._start_step_logging(step_number)
                    self._complete_step_logging(
                        step_log_id,
                        cost=step_cost,
                        model=scrape_event.get("model"),
                        metadata={"data_keys": list(step_data.keys()) if step_data else []}
                    )

                    yield {
                        "type": "data",
                        "step": step_number,
                        "step_name": step_name,
                        "data": step_data,
                        "status": "scraped",
                        "message": f"Extracted: {step_name}",
                        "cost_so_far": _apply_margin(scrape_event.get("cost_so_far", 0))
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

                    # Run skill-based analysis on the extracted data
                    analysis_results = {}
                    analysis_cost = 0
                    async for analysis_event in self._run_analysis_skills(address, all_data):
                        if analysis_event["type"] == "analysis_complete":
                            analysis_results = analysis_event.get("results", {})
                            analysis_cost = analysis_event.get("analysis_cost", 0)
                        yield analysis_event

                    # Step 11: Generic Knowledge / Property Insights (with timeout to avoid blocking SSE)
                    try:
                        generic_knowledge, insights_debug = await asyncio.wait_for(
                            self._prepare_generic_knowledge(all_data),
                            timeout=45.0,
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Property insights timed out after 45s, skipping")
                        generic_knowledge, insights_debug = [], {"error": "timeout"}
                    if generic_knowledge:
                        yield {
                            "type": "generic_knowledge",
                            "step": 11,
                            "step_name": "Property Insights",
                            "data": {
                                "knowledge_points": generic_knowledge,
                                "debug": insights_debug,
                            },
                        }

                    total_raw = scrape_event["total_cost"] + analysis_cost

                    # Calculate actual total elapsed time (scraping + analysis)
                    total_elapsed = (datetime.utcnow() - start_time).total_seconds()

                    # Complete job logging
                    if self.logging_service and self.current_job_id:
                        self.logging_service.complete_job(self.current_job_id, is_cached=False)

                    yield {
                        "type": "summary",
                        "content": json.dumps(all_data, indent=2, default=str),
                        "extracted_data": all_data,
                        "analysis_results": analysis_results,
                        "status": "complete",
                        "total_scraping_cost": _apply_margin(scrape_event["total_cost"]),
                        "total_analysis_cost": _apply_margin(analysis_cost),
                        "total_cost": _apply_margin(total_raw),
                        "total_time": total_elapsed
                    }

                # Handle errors
                elif scrape_event["type"] == "error":
                    logger.error(f"Scraping error: {scrape_event['error']}")
                    # Fail job logging
                    if self.logging_service and self.current_job_id:
                        self.logging_service.fail_job(
                            self.current_job_id,
                            error_message=scrape_event.get('error', 'Unknown error'),
                            error_step='extraction'
                        )
                    yield scrape_event

        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}", exc_info=True)
            # Fail job logging
            if self.logging_service and self.current_job_id:
                self.logging_service.fail_job(
                    self.current_job_id,
                    error_message=str(e),
                    error_step='unknown'
                )
            yield {
                "type": "error",
                "error": str(e)
            }

    def _write_knowledge_debug_to_notes(self, address: str, skill_name: str, result: Dict[str, Any]):
        """Write knowledge query debug info to the notes file."""
        queries = result.get('knowledge_queries', [])
        debug_entries = result.get('knowledge_debug', [])

        lines = []
        for entry in debug_entries:
            # Handle both dict and string entries
            if isinstance(entry, dict):
                query = entry.get('query', '')
                results = entry.get('results', [])
            else:
                # entry is a string (legacy format)
                query = str(entry)
                results = []
            lines.append(f"**Query:** `{query}`\n")
            if not results:
                lines.append("- _(no results)_\n")
            else:
                for r in results:
                    if isinstance(r, dict):
                        score = r.get('score', 0)
                        cat = r.get('category', '')
                        src = r.get('source_file', '')
                        text = r.get('text', '')
                    else:
                        score, cat, src, text = 0, '', '', str(r)
                    lines.append(f"- [{cat}] (score: {score}, src: {src})")
                    lines.append(f"  > {text}\n")

        if not lines:
            return

        content = "\n".join(lines)
        total_results = sum(
            len(e.get('results', [])) if isinstance(e, dict) else 0
            for e in debug_entries
        )
        self.notes_manager.append_section(
            address=address,
            section_title=f"Knowledge Debug ({skill_name})",
            content=content,
            metadata={
                "Queries": str(queries),
                "Total Results": total_results,
            }
        )

    @staticmethod
    def _format_analysis_markdown(result: Dict[str, Any], title: str) -> str:
        """Format a skill analysis result as readable markdown for the frontend."""
        score = result.get('score', 'N/A')
        confidence = result.get('confidence', 'N/A')
        reasoning = result.get('reasoning', '')

        lines = [f"**Score: {score}/100** (Confidence: {confidence})\n"]
        if reasoning:
            lines.append(f"{reasoning}\n")

        strengths = result.get('strengths', [])
        if strengths:
            lines.append("**Strengths:**")
            for s in strengths:
                lines.append(f"- {s}")
            lines.append("")

        concerns = result.get('concerns', [])
        if concerns:
            lines.append("**Concerns:**")
            for c in concerns:
                lines.append(f"- {c}")
            lines.append("")

        details = result.get('details', {})
        # Keys to skip in markdown (complex nested data or debug-only)
        skip_keys = {'commute_to_hot_areas', 'missing_data', 'raw_data'}
        if details:
            lines.append("**Details:**")
            for key, val in details.items():
                if key in skip_keys:
                    continue
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    continue  # skip lists of dicts
                elif key == 'missing_data' and isinstance(val, list):
                    lines.append(f"- Missing data: {', '.join(val)}")
                elif isinstance(val, list):
                    lines.append(f"- {key.replace('_', ' ').title()}: {', '.join(str(v) for v in val)}")
                else:
                    lines.append(f"- {key.replace('_', ' ').title()}: {val}")

        return "\n".join(lines)

    async def _run_analysis_skills(self, address: str, all_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Run analysis skills in PARALLEL, yield results in consistent order.

        All 4 skills run concurrently, but results are buffered and yielded
        in order: Property → Location → School → Investment.
        """
        results: Dict[str, Any] = {}
        total_cost = 0.0

        # Skill configuration in desired output order
        skill_configs = [
            {"key": "property", "step": 7, "step_name": "Property Condition",
             "skill": self.property_skill, "notes_title": "Property Analysis"},
            {"key": "location", "step": 8, "step_name": "Location & Commute",
             "skill": self.location_skill, "notes_title": "Location Analysis"},
            {"key": "schools", "step": 9, "step_name": "School Quality",
             "skill": self.school_skill, "notes_title": "School Analysis"},
            {"key": "investment", "step": 10, "step_name": "Investment Potential",
             "skill": self.investment_skill, "notes_title": "Investment Analysis"},
            {"key": "sale_price", "step": 12, "step_name": "Sale Price Prediction",
             "skill": self.sale_price_skill, "notes_title": "Sale Price Analysis"},
        ]

        yield {"type": "status", "message": "Running all analyses in parallel..."}

        # Start step logging for all skills at once
        step_log_ids = {config["key"]: self._start_step_logging(config["step"]) for config in skill_configs}

        # Wrapper to include skill key in result
        async def run_skill_with_key(config):
            try:
                result = await config["skill"].analyze(address, property_data=all_data)
                return (config["key"], result, None)
            except Exception as e:
                logger.error(f"{config['key']} analysis failed: {e}", exc_info=True)
                return (config["key"], None, e)

        # Launch all skills in parallel
        tasks = [asyncio.create_task(run_skill_with_key(config)) for config in skill_configs]

        # Process and yield results immediately as each skill completes
        for completed_task in asyncio.as_completed(tasks):
            key, skill_result, error = await completed_task
            config = next(c for c in skill_configs if c["key"] == key)
            step_log_id = step_log_ids[key]

            if error:
                self._fail_step_logging(step_log_id, str(error))
                yield {"type": "status", "message": f"{config['step_name']} failed: {error}"}
            else:
                results[key] = skill_result
                step_cost = skill_result.get('cost_summary', {}).get('total_cost', 0)
                total_cost += step_cost

                self._complete_step_logging(
                    step_log_id,
                    cost=step_cost,
                    input_tokens=skill_result.get('cost_summary', {}).get('input_tokens', 0),
                    output_tokens=skill_result.get('cost_summary', {}).get('output_tokens', 0),
                    model=skill_result.get('cost_summary', {}).get('model'),
                    metadata={"score": skill_result.get('score')}
                )

                yield {"type": "status", "message": f"{config['step_name']} complete"}

                yield {
                    "type": "analysis",
                    "step": config["step"],
                    "step_name": config["step_name"],
                    "skill": key,
                    "analysis": self._format_analysis_markdown(skill_result, config["step_name"]),
                    "data": skill_result,
                }

                # Save to notes
                self.notes_manager.append_section(
                    address=address,
                    section_title=config["notes_title"],
                    content="```json\n" + json.dumps(skill_result, indent=2, default=str) + "\n```",
                    metadata={
                        "Score": f"{skill_result.get('score', 'N/A')}/100",
                        "Confidence": skill_result.get('confidence', 'N/A')
                    }
                )

                # Save knowledge debug to notes
                if skill_result.get('knowledge_debug'):
                    self._write_knowledge_debug_to_notes(address, config["step_name"], skill_result)

                # Special: GreatSchools enrichment for schools skill
                if key == "schools":
                    raw_schools = skill_result.get('raw_data', {}).get('schools', [])
                    gs_schools = [s for s in raw_schools if any(k.startswith('gs_') for k in s)]
                    if gs_schools:
                        gs_lines = []
                        for s in gs_schools:
                            gs_lines.append(f"### {s.get('name', 'Unknown')}")
                            for k, v in s.items():
                                if k.startswith('gs_'):
                                    if isinstance(v, dict):
                                        gs_lines.append(f"- **{k}**: {json.dumps(v, default=str)}")
                                    else:
                                        gs_lines.append(f"- **{k}**: {v}")
                            gs_lines.append("")
                        self.notes_manager.append_section(
                            address=address,
                            section_title="GreatSchools Enrichment Data",
                            content="\n".join(gs_lines),
                            metadata={"Schools Enriched": len(gs_schools)}
                        )

        yield {
            "type": "analysis_complete",
            "results": results,
            "analysis_cost": total_cost
        }

    async def _prepare_generic_knowledge(
        self, property_data: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Find generic knowledge using two-stage LLM filtering.

        Stage 1: Build rich property query and get 50-100 candidates via broad semantic search
        Stage 2: Use LLM (Haiku) to filter to 10-15 most relevant knowledge points

        Falls back to attribute-based search if LLM filtering fails.

        Returns:
            Tuple of (knowledge_points, debug_info) where debug_info contains
            the search query, candidate counts, and selection details.
        """
        debug_info = {
            "method": "llm_filtered",
            "query": "",
            "property_summary": "",
            "candidates_count": 0,
            "selected_count": 0,
            "candidates_sample": [],
        }

        try:
            # Stage 1: Build rich query from property attributes
            from app.services.knowledge.context_builder import (
                build_knowledge_query,
                build_property_summary,
            )
            query = build_knowledge_query(property_data)
            property_summary = build_property_summary(property_data)

            debug_info["query"] = query
            debug_info["property_summary"] = property_summary

            logger.info(f"Built knowledge query:\n{query[:200]}...")

            # Get broad candidates via hybrid search
            search_service = get_search_service()
            candidates = search_service.get_broad_candidates(query, limit=60, min_score=0.35)

            debug_info["candidates_count"] = len(candidates)
            # Include sample of top candidates for debugging
            debug_info["candidates_sample"] = [
                {
                    "text": c.text[:100] + "..." if len(c.text) > 100 else c.text,
                    "category": c.category,
                    "score": round(c.score, 4),
                }
                for c in candidates[:10]
            ]

            if not candidates:
                logger.info("No broad candidates found, falling back to attribute search")
                return self._fallback_attribute_search(property_data)

            # Pre-filter: Remove obviously irrelevant candidates deterministically
            candidates = self._pre_filter_candidates(candidates, property_data)
            debug_info["candidates_after_prefilter"] = len(candidates)

            if not candidates:
                logger.info("All candidates removed by pre-filter, falling back to attribute search")
                return self._fallback_attribute_search(property_data)

            # Deduplicate near-identical candidates
            candidates = self._deduplicate_candidates(candidates)
            debug_info["candidates_after_dedup"] = len(candidates)

            if not candidates:
                logger.info("All candidates removed by dedup, falling back to attribute search")
                return self._fallback_attribute_search(property_data)

            # Stage 2: LLM filter to select most relevant
            from app.services.knowledge.llm_filter_service import get_filter_service
            filter_service = get_filter_service()

            candidate_dicts = [
                {"text": c.text, "category": c.category}
                for c in candidates
            ]

            selected_indices = await filter_service.filter_relevant_knowledge(
                property_summary=property_summary,
                candidates=candidate_dicts,
                max_results=8,
            )

            debug_info["selected_indices"] = selected_indices
            debug_info["selected_count"] = len(selected_indices)

            if not selected_indices:
                logger.info("LLM filter returned no results, falling back to attribute search")
                return self._fallback_attribute_search(property_data)

            # Build result list from selected candidates
            knowledge_points = []
            for idx in selected_indices:
                if idx < len(candidates):
                    c = candidates[idx]
                    knowledge_points.append({
                        "text": c.text,
                        "category": c.category,
                        "priority": c.priority,
                        "source": "llm_filtered",
                    })

            logger.info(
                f"LLM filtered {len(knowledge_points)} knowledge points "
                f"from {len(candidates)} candidates"
            )
            return knowledge_points, debug_info

        except Exception as e:
            logger.warning(f"Failed to prepare generic knowledge via LLM: {e}")
            debug_info["error"] = str(e)
            return self._fallback_attribute_search(property_data)

    @staticmethod
    def _deduplicate_candidates(candidates, similarity_threshold: float = 0.55):
        """
        Remove near-duplicate candidates using word-level Jaccard similarity.

        Iterates in score order (highest first). For each candidate, checks
        Jaccard similarity against all already-kept candidates. If similarity
        >= threshold, the lower-scoring duplicate is discarded.
        """
        def _tokenize(text: str) -> set:
            return {w.lower() for w in text.split() if len(w) >= 3}

        kept = []
        kept_token_sets = []

        for candidate in candidates:
            tokens = _tokenize(candidate.text)
            if not tokens:
                kept.append(candidate)
                kept_token_sets.append(tokens)
                continue

            is_dup = False
            for existing_tokens in kept_token_sets:
                if not existing_tokens:
                    continue
                intersection = len(tokens & existing_tokens)
                union = len(tokens | existing_tokens)
                if union > 0 and intersection / union >= similarity_threshold:
                    is_dup = True
                    break

            if not is_dup:
                kept.append(candidate)
                kept_token_sets.append(tokens)

        removed = len(candidates) - len(kept)
        if removed > 0:
            logger.info(f"Dedup removed {removed} near-duplicate candidates ({len(kept)} remaining)")

        return kept

    def _pre_filter_candidates(self, candidates, property_data: Dict[str, Any]):
        """
        Deterministic pre-filter to remove obviously irrelevant candidates
        before sending to the LLM filter. Covers 6 filter rules:
        1. HOA — remove HOA content when has_hoa=false
        2. Flood — remove flood content when flood risk is minimal
        3. Construction era — remove wrong-decade content (15-year buffer)
        4. Location — remove content about cities from other metros
        5. Property type — remove condo tips for SFH and vice versa
        6. Landfill/environmental — remove generic landfill/superfund content
        """
        import re as _re

        # --- Extract property attributes ---
        hoa = property_data.get("hoa", {})
        has_hoa = hoa.get("has_hoa", False)
        details = property_data.get("details", {})
        year_built = details.get("year_built")
        property_type = (details.get("property_type") or "").lower()
        location = property_data.get("location", {})
        prop_city = (location.get("city") or "").lower().strip()

        # Determine if climate risks are minimal
        climate = property_data.get("climate_risks", {})
        flood_risk_minimal = True
        if climate:
            flood_level = climate.get("flood")
            if isinstance(flood_level, dict):
                flood_level = flood_level.get("level") or flood_level.get("risk")
            if flood_level and str(flood_level).lower() not in ("none", "minimal", "n/a", ""):
                flood_risk_minimal = False

        # Is SFH vs condo/townhome?
        is_sfh = any(kw in property_type for kw in ("single", "sfh", "house", "residential"))
        is_condo = any(kw in property_type for kw in ("condo", "apartment", "co-op"))

        # --- Regex patterns ---
        hoa_keywords = _re.compile(
            r'\b(hoa|homeowners?\s+association|special\s+assessment|reserve\s+fund|'
            r'reserve\s+study|hoa\s+fee|hoa\s+due|hoa\s+budget|hoa\s+board|'
            r'common\s+area\s+maintenance|association\s+fee)\b',
            _re.IGNORECASE,
        )

        flood_keywords = _re.compile(
            r'\b(flood\s+zone|flood\s+insurance|flood\s+risk|flood\s+plain|'
            r'floodplain|fema\s+flood|flood\s+map|flood\s+elevation)\b',
            _re.IGNORECASE,
        )

        # Matches explicit decade ranges like "1940s-1950s", "1960s homes", "1970s-era"
        era_pattern = _re.compile(
            r'\b(\d{4})s[\s\-]*(to|through|and|\-)?\s*(\d{4})?s?\b',
            _re.IGNORECASE,
        )

        landfill_keywords = _re.compile(
            r'\b(landfill|superfund|brownfield|contaminated\s+soil|'
            r'toxic\s+waste|hazardous\s+waste\s+site|environmental\s+contamination)\b',
            _re.IGNORECASE,
        )

        condo_keywords = _re.compile(
            r'\b(condo\s+association|condo\s+board|condo\s+fee|condo\s+rules|'
            r'unit\s+owner|strata\s+council|common\s+elements)\b',
            _re.IGNORECASE,
        )

        sfh_keywords = _re.compile(
            r'\b(single[\s\-]family|detached\s+home|yard\s+maintenance|'
            r'lot\s+line|property\s+line|septic\s+system|well\s+water)\b',
            _re.IGNORECASE,
        )

        # Metro area groups — cities in the same metro won't trigger location filter
        METRO_GROUPS = [
            {"seattle", "bellevue", "redmond", "kirkland", "renton", "tacoma",
             "bothell", "everett", "issaquah", "sammamish", "woodinville", "kent",
             "federal way", "lynnwood", "burien", "shoreline", "mercer island"},
            {"san francisco", "san jose", "oakland", "palo alto", "sunnyvale",
             "mountain view", "cupertino", "fremont", "santa clara", "berkeley",
             "redwood city", "menlo park", "san mateo", "hayward", "milpitas"},
            {"los angeles", "long beach", "pasadena", "glendale", "burbank",
             "santa monica", "torrance", "inglewood", "pomona", "irvine",
             "anaheim", "costa mesa", "huntington beach"},
            {"new york", "nyc", "brooklyn", "manhattan", "queens", "bronx",
             "staten island", "jersey city", "hoboken", "yonkers"},
            {"austin", "round rock", "cedar park", "pflugerville", "georgetown",
             "san marcos", "kyle", "leander", "lakeway"},
            {"portland", "beaverton", "hillsboro", "tigard", "lake oswego",
             "gresham", "milwaukie", "oregon city"},
        ]

        # Find which metro the property belongs to
        prop_metro = None
        for metro in METRO_GROUPS:
            if prop_city in metro:
                prop_metro = metro
                break

        # Pattern to find city names in text
        all_metro_cities = set()
        for metro in METRO_GROUPS:
            all_metro_cities.update(metro)

        filtered = []
        removed_reasons = {}

        for c in candidates:
            text = c.text
            category = c.category or ""
            combined = f"{text} {category}"
            reason = None

            # 1. Remove HOA candidates when property has no HOA
            if not has_hoa and hoa_keywords.search(combined):
                reason = "hoa"

            # 2. Remove flood candidates when flood risk is minimal
            elif flood_risk_minimal and flood_keywords.search(combined):
                reason = "flood"

            # 3. Construction era filter — remove wrong-decade tips
            elif year_built and not reason:
                for match in era_pattern.finditer(combined):
                    era_start = int(match.group(1))
                    era_end_str = match.group(3)
                    era_end = int(era_end_str) if era_end_str else era_start
                    # The range covers era_start to era_end+9 (e.g., "1940s" = 1940-1949)
                    range_start = era_start
                    range_end = era_end + 9
                    # 15-year buffer: only exclude if year_built is well outside
                    if year_built < range_start - 15 or year_built > range_end + 15:
                        reason = "era"
                        break

            # 4. Location filter — remove content about other metros
            if not reason and prop_city:
                text_lower = combined.lower()
                for metro in METRO_GROUPS:
                    if metro == prop_metro:
                        continue  # Skip our own metro
                    for city in metro:
                        if city in text_lower:
                            reason = "location"
                            break
                    if reason:
                        break

            # 5. Property type filter
            if not reason:
                if is_sfh and condo_keywords.search(combined):
                    reason = "property_type"
                elif is_condo and sfh_keywords.search(combined):
                    reason = "property_type"

            # 6. Landfill/environmental filter
            if not reason and landfill_keywords.search(combined):
                reason = "landfill"

            if reason:
                removed_reasons[reason] = removed_reasons.get(reason, 0) + 1
            else:
                filtered.append(c)

        total_removed = sum(removed_reasons.values())
        if total_removed > 0:
            logger.info(
                f"Pre-filter removed {total_removed} irrelevant candidates "
                f"({len(filtered)} remaining) — reasons: {removed_reasons}"
            )

        return filtered

    def _fallback_attribute_search(
        self, property_data: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fallback to attribute-based search when LLM filtering fails.

        Uses @applies_when tags to match knowledge points to property attributes.
        """
        debug_info = {
            "method": "attribute_fallback",
            "query": "N/A (attribute-based)",
        }

        try:
            search_service = get_search_service()
            knowledge_points = search_service.search_by_attributes_with_details(
                property_data=property_data,
                limit=15,
            )
            debug_info["results_count"] = len(knowledge_points)
            logger.info(f"Fallback attribute search found {len(knowledge_points)} points")
            return knowledge_points, debug_info
        except Exception as e:
            logger.warning(f"Fallback attribute search also failed: {e}")
            debug_info["error"] = str(e)
            return [], debug_info

