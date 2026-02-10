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
from typing import Dict, Any, AsyncGenerator, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector
from app.services.agent.tools.notes_manager import get_notes_manager
from app.services.agent.skills.property_skill import PropertySkill
from app.services.agent.skills.location_skill import LocationSkill
from app.services.agent.skills.school_skill import SchoolSkill
from app.services.agent.skills.investment_skill import InvestmentSkill
from app.services.analysis_logging_service import AnalysisLoggingService
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

        # Logging context
        self.db = db
        self.user_id = user_id
        self.client_ip = client_ip
        self.logging_service: Optional[AnalysisLoggingService] = None
        self.current_job = None
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
        "School Analysis", "Investment Analysis" — each containing a
        ```json ... ``` block with the full skill result.

        Returns {"property": {...}, "location": {...}, "schools": {...},
        "investment": {...}} if all 4 found, else None.
        """
        if not self.notes_manager.notes_exist(address):
            return None

        notes_content = self.notes_manager.read_notes(address)
        if not notes_content:
            return None

        section_map = {
            "Property Analysis": "property",
            "Location Analysis": "location",
            "School Analysis": "schools",
            "Investment Analysis": "investment",
        }

        cached_analysis = {}

        for section_title, key in section_map.items():
            # Find the section and extract its JSON block
            pattern = rf'## {re.escape(section_title)}\n(.*?)(?=\n## |\Z)'
            matches = re.findall(pattern, notes_content, re.DOTALL)
            if not matches:
                logger.info(f"Cached analysis missing section: {section_title}")
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

        logger.info(f"Found all 4 cached analysis results for: {address}")
        return cached_analysis

    def _start_step_logging(self, step_number: int) -> Optional[str]:
        """Start logging a step and return the step log ID."""
        if not self.logging_service or not self.current_job:
            return None

        step_def = None
        for s in ANALYSIS_STEPS:
            if s["number"] == step_number:
                step_def = s
                break

        if not step_def:
            return None

        step_log = self.logging_service.start_step(
            job_id=str(self.current_job.id),
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
            # All 4 analysis results are cached — replay them without calling LLM
            # Stagger delivery so the user sees progressive loading

            analysis_skill_map = [
                (7, "Property Condition", "property", "Reviewing property condition..."),
                (8, "Location & Commute", "location", "Evaluating location quality..."),
                (9, "School Quality", "schools", "Analyzing nearby schools..."),
                (10, "Investment Potential", "investment", "Calculating investment metrics..."),
            ]

            analysis_results = {}
            for step_num, step_name, skill_key, status_msg in analysis_skill_map:
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

        elapsed = (datetime.utcnow() - start_time).total_seconds()

        # Complete job logging
        if self.logging_service and self.current_job:
            self.logging_service.complete_job(str(self.current_job.id), is_cached=True)

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
            logger.info(f"Created analysis job: {self.current_job.id}")

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

                    total_raw = scrape_event["total_cost"] + analysis_cost

                    # Complete job logging
                    if self.logging_service and self.current_job:
                        self.logging_service.complete_job(str(self.current_job.id), is_cached=False)

                    yield {
                        "type": "summary",
                        "content": json.dumps(all_data, indent=2, default=str),
                        "extracted_data": all_data,
                        "analysis_results": analysis_results,
                        "status": "complete",
                        "total_scraping_cost": _apply_margin(scrape_event["total_cost"]),
                        "total_analysis_cost": _apply_margin(analysis_cost),
                        "total_cost": _apply_margin(total_raw),
                        "total_time": scrape_event["total_time"]
                    }

                # Handle errors
                elif scrape_event["type"] == "error":
                    logger.error(f"Scraping error: {scrape_event['error']}")
                    # Fail job logging
                    if self.logging_service and self.current_job:
                        self.logging_service.fail_job(
                            str(self.current_job.id),
                            error_message=scrape_event.get('error', 'Unknown error'),
                            error_step='extraction'
                        )
                    yield scrape_event

        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}", exc_info=True)
            # Fail job logging
            if self.logging_service and self.current_job:
                self.logging_service.fail_job(
                    str(self.current_job.id),
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
            query = entry.get('query', '')
            results = entry.get('results', [])
            lines.append(f"**Query:** `{query}`\n")
            if not results:
                lines.append("- _(no results)_\n")
            else:
                for r in results:
                    score = r.get('score', 0)
                    cat = r.get('category', '')
                    src = r.get('source_file', '')
                    text = r.get('text', '')
                    lines.append(f"- [{cat}] (score: {score}, src: {src})")
                    lines.append(f"  > {text}\n")

        if not lines:
            return

        content = "\n".join(lines)
        self.notes_manager.append_section(
            address=address,
            section_title=f"Knowledge Debug ({skill_name})",
            content=content,
            metadata={
                "Queries": str(queries),
                "Total Results": sum(len(e.get('results', [])) for e in debug_entries),
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
        Run analysis skills on extracted data and yield streaming events.
        """
        results = {}
        total_cost = 0.0

        # Property analysis (Step 7)
        step_log_id = self._start_step_logging(7)
        yield {"type": "status", "message": "Running property analysis..."}
        try:
            property_result = await self.property_skill.analyze(address, property_data=all_data)
            results["property"] = property_result
            step_cost = 0
            if property_result.get('cost_summary'):
                step_cost = property_result['cost_summary'].get('total_cost', 0)
                total_cost += step_cost

            self._complete_step_logging(
                step_log_id,
                cost=step_cost,
                input_tokens=property_result.get('cost_summary', {}).get('input_tokens', 0),
                output_tokens=property_result.get('cost_summary', {}).get('output_tokens', 0),
                model=property_result.get('cost_summary', {}).get('model'),
                metadata={"score": property_result.get('score')}
            )

            yield {
                "type": "analysis",
                "step": 7,
                "step_name": "Property Condition",
                "skill": "property",
                "analysis": self._format_analysis_markdown(property_result, "Property Condition"),
                "data": property_result,
            }

            # Save to notes
            self.notes_manager.append_section(
                address=address,
                section_title="Property Analysis",
                content="```json\n" + json.dumps(property_result, indent=2, default=str) + "\n```",
                metadata={
                    "Score": f"{property_result.get('score', 'N/A')}/100",
                    "Confidence": property_result.get('confidence', 'N/A')
                }
            )

            # Save knowledge debug to notes
            if property_result.get('knowledge_debug'):
                self._write_knowledge_debug_to_notes(address, "Property", property_result)

        except Exception as e:
            logger.error(f"Property analysis failed: {e}", exc_info=True)
            self._fail_step_logging(step_log_id, str(e))
            yield {"type": "status", "message": f"Property analysis failed: {e}"}

        # Location analysis (Step 8)
        step_log_id = self._start_step_logging(8)
        yield {"type": "status", "message": "Running location analysis..."}
        try:
            location_result = await self.location_skill.analyze(address, property_data=all_data)
            results["location"] = location_result
            step_cost = 0
            if location_result.get('cost_summary'):
                step_cost = location_result['cost_summary'].get('total_cost', 0)
                total_cost += step_cost

            self._complete_step_logging(
                step_log_id,
                cost=step_cost,
                input_tokens=location_result.get('cost_summary', {}).get('input_tokens', 0),
                output_tokens=location_result.get('cost_summary', {}).get('output_tokens', 0),
                model=location_result.get('cost_summary', {}).get('model'),
                metadata={"score": location_result.get('score')}
            )

            yield {
                "type": "analysis",
                "step": 8,
                "step_name": "Location & Commute",
                "skill": "location",
                "analysis": self._format_analysis_markdown(location_result, "Location & Commute"),
                "data": location_result,
            }

            self.notes_manager.append_section(
                address=address,
                section_title="Location Analysis",
                content="```json\n" + json.dumps(location_result, indent=2, default=str) + "\n```",
                metadata={
                    "Score": f"{location_result.get('score', 'N/A')}/100",
                    "Confidence": location_result.get('confidence', 'N/A')
                }
            )

            # Save knowledge debug to notes
            if location_result.get('knowledge_debug'):
                self._write_knowledge_debug_to_notes(address, "Location", location_result)
        except Exception as e:
            logger.error(f"Location analysis failed: {e}", exc_info=True)
            self._fail_step_logging(step_log_id, str(e))
            yield {"type": "status", "message": f"Location analysis failed: {e}"}

        # School analysis (Step 9)
        step_log_id = self._start_step_logging(9)
        yield {"type": "status", "message": "Running school analysis..."}
        try:
            school_result = await self.school_skill.analyze(address, property_data=all_data)
            results["schools"] = school_result
            step_cost = 0
            if school_result.get('cost_summary'):
                step_cost = school_result['cost_summary'].get('total_cost', 0)
                total_cost += step_cost

            self._complete_step_logging(
                step_log_id,
                cost=step_cost,
                input_tokens=school_result.get('cost_summary', {}).get('input_tokens', 0),
                output_tokens=school_result.get('cost_summary', {}).get('output_tokens', 0),
                model=school_result.get('cost_summary', {}).get('model'),
                metadata={"score": school_result.get('score')}
            )

            yield {
                "type": "analysis",
                "step": 9,
                "step_name": "School Quality",
                "skill": "schools",
                "analysis": self._format_analysis_markdown(school_result, "School Quality"),
                "data": school_result,
            }

            self.notes_manager.append_section(
                address=address,
                section_title="School Analysis",
                content="```json\n" + json.dumps(school_result, indent=2, default=str) + "\n```",
                metadata={
                    "Score": f"{school_result.get('score', 'N/A')}/100",
                    "Confidence": school_result.get('confidence', 'N/A')
                }
            )

            if school_result.get('knowledge_debug'):
                self._write_knowledge_debug_to_notes(address, "Schools", school_result)

            # Write GreatSchools enrichment data for debugging
            raw_schools = school_result.get('raw_data', {}).get('schools', [])
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
        except Exception as e:
            logger.error(f"School analysis failed: {e}", exc_info=True)
            self._fail_step_logging(step_log_id, str(e))
            yield {"type": "status", "message": f"School analysis failed: {e}"}

        # Investment analysis (Step 10)
        step_log_id = self._start_step_logging(10)
        yield {"type": "status", "message": "Running investment analysis..."}
        try:
            investment_result = await self.investment_skill.analyze(address, property_data=all_data)
            results["investment"] = investment_result
            step_cost = 0
            if investment_result.get('cost_summary'):
                step_cost = investment_result['cost_summary'].get('total_cost', 0)
                total_cost += step_cost

            self._complete_step_logging(
                step_log_id,
                cost=step_cost,
                input_tokens=investment_result.get('cost_summary', {}).get('input_tokens', 0),
                output_tokens=investment_result.get('cost_summary', {}).get('output_tokens', 0),
                model=investment_result.get('cost_summary', {}).get('model'),
                metadata={"score": investment_result.get('score')}
            )

            yield {
                "type": "analysis",
                "step": 10,
                "step_name": "Investment Potential",
                "skill": "investment",
                "analysis": self._format_analysis_markdown(investment_result, "Investment Potential"),
                "data": investment_result,
            }

            self.notes_manager.append_section(
                address=address,
                section_title="Investment Analysis",
                content="```json\n" + json.dumps(investment_result, indent=2, default=str) + "\n```",
                metadata={
                    "Score": f"{investment_result.get('score', 'N/A')}/100",
                    "Confidence": investment_result.get('confidence', 'N/A')
                }
            )

            if investment_result.get('knowledge_debug'):
                self._write_knowledge_debug_to_notes(address, "Investment", investment_result)
        except Exception as e:
            logger.error(f"Investment analysis failed: {e}", exc_info=True)
            self._fail_step_logging(step_log_id, str(e))
            yield {"type": "status", "message": f"Investment analysis failed: {e}"}

        yield {
            "type": "analysis_complete",
            "results": results,
            "analysis_cost": total_cost
        }

