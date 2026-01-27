"""
Tool Orchestrator for coordinating granular analysis tool execution.

Uses notes-based system to write incremental analysis results to markdown files.
This enables memory efficiency, transparency, caching, and resumability.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from .tool_registry import get_tool_registry
from .base_tool import BaseTool
from .notes_manager import get_notes_manager

logger = logging.getLogger(__name__)


class ToolOrchestrator:
    """
    Orchestrates the execution of multiple granular analysis tools.

    Responsibilities:
    - Determine which tools to run based on available data
    - Execute tools in appropriate order (parallel when possible)
    - Aggregate results into comprehensive report
    - Track progress and provide status updates
    - Handle errors and partial failures gracefully
    """

    def __init__(self, llm_client: Any, environment: str = "development", reuse_notes: bool = True):
        """
        Initialize orchestrator.

        Args:
            llm_client: LLM client for tool execution
            environment: "development" or "production" (affects notes cleanup)
            reuse_notes: If True, reuse existing notes for same address
        """
        self.llm_client = llm_client
        self.registry = get_tool_registry()
        self.progress_callback: Optional[Callable] = None
        self.environment = environment
        self.reuse_notes = reuse_notes
        self.notes_manager = get_notes_manager(environment=environment)

    def set_progress_callback(self, callback: Callable[[str, int], None]):
        """
        Set callback function for progress updates.

        Args:
            callback: Function(message: str, progress_percent: int)
        """
        self.progress_callback = callback

    def _update_progress(self, message: str, progress_percent: int):
        """Send progress update if callback is set."""
        if self.progress_callback:
            try:
                self.progress_callback(message, progress_percent)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")

    async def analyze_property(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run comprehensive property analysis using all applicable tools.

        Uses notes-based system:
        1. Check if notes exist for this address
        2. If notes exist and reuse_notes=True, parse and return cached report
        3. If notes don't exist, create notes file and run analysis
        4. Write each tool result to notes incrementally
        5. Write final summary to notes
        6. Upload notes to S3 (production mode)
        7. Clean up notes (production mode)

        Args:
            property_data: Complete property data including:
                - address (required)
                - property_info (price, beds, baths, etc.)
                - schools (list of nearby schools)
                - crime_data
                - walkability_data
                - financial_data
                - market_data
                - etc.

        Returns:
            Comprehensive analysis report with scores from all tools
        """
        start_time = datetime.now()
        address = property_data.get('address', 'Unknown')

        logger.info(f"Starting orchestrated analysis for: {address}")
        self._update_progress("Checking for existing analysis...", 2)

        # Check if notes exist for this address
        if self.reuse_notes and self.notes_manager.notes_exist(address):
            logger.info(f"Found existing notes for {address}, reusing cached analysis")
            self._update_progress("Found existing analysis, loading cached results...", 5)

            # Parse existing notes and generate report from cache
            cached_report = await self._generate_report_from_notes(address, property_data)

            if cached_report:
                self._update_progress("Loaded cached analysis!", 100)
                logger.info(f"Returned cached analysis for {address}")
                return cached_report

            # If parsing failed, fall through to run new analysis
            logger.warning(f"Failed to parse cached notes for {address}, running new analysis")

        # Create new notes file
        self._update_progress("Creating analysis notes file...", 5)
        property_info = property_data.get('property_info', {})
        self.notes_manager.create_notes(address, property_info)

        logger.info(f"Created notes file for {address}")

        # Determine which tools to run based on available data
        tools_to_run = self._determine_applicable_tools(property_data)

        logger.info(f"Running {len(tools_to_run)} analysis tools")
        self._update_progress(f"Preparing {len(tools_to_run)} specialized analysis tools...", 10)

        # Execute tools and collect results (writes to notes incrementally)
        results = await self._execute_tools_with_notes(tools_to_run, property_data, address)

        self._update_progress("Aggregating analysis results...", 85)

        # Aggregate results into final report
        final_report = self._aggregate_results(results, property_data)

        # Calculate execution time
        execution_time = (datetime.now() - start_time).total_seconds()
        final_report["metadata"]["execution_time_seconds"] = execution_time

        # Write final summary to notes
        self._update_progress("Writing final summary to notes...", 90)
        self.notes_manager.append_summary(
            address,
            final_report['overall_score'],
            final_report['overall_grade'],
            final_report['category_scores'],
            final_report['summary']['recommendation']
        )

        # Upload to S3 if in production mode (keep local copy for backup)
        if self.environment == "production":
            self._update_progress("Uploading analysis to cloud storage...", 95)
            s3_url = await self.notes_manager.upload_to_s3(address)
            final_report["metadata"]["s3_url"] = s3_url

            if s3_url:
                logger.info(f"Notes uploaded to S3: {s3_url}. Local copy retained for backup (cleaned by periodic task).")
            else:
                logger.warning(f"Failed to upload notes to S3 for {address}, keeping local copy")

        self._update_progress("Analysis complete!", 100)

        logger.info(f"Orchestrated analysis complete in {execution_time:.2f}s. Overall score: {final_report['overall_score']}/100")

        return final_report

    def _determine_applicable_tools(self, property_data: Dict[str, Any]) -> List[tuple[str, BaseTool]]:
        """
        Determine which tools should run based on available data.

        Args:
            property_data: Property data dictionary

        Returns:
            List of (tool_name, tool_instance) tuples to execute
        """
        tools_to_run = []

        # Property Quality tool - ONLY ACTIVE TOOL FOR NOW
        tool = self.registry.get_tool("assess_property_quality")
        if tool:
            tools_to_run.append(("assess_property_quality", tool))

        # TEMPORARILY DISABLED - Other tools use fake data
        # TODO: Re-enable when tools are fully implemented with real data sources

        # # Education tool - run if school data available
        # if property_data.get("schools"):
        #     tool = self.registry.get_tool("analyze_school_quality")
        #     if tool:
        #         tools_to_run.append(("analyze_school_quality", tool))

        # # Crime tool - run if crime data available
        # if property_data.get("crime_data"):
        #     tool = self.registry.get_tool("analyze_crime_risk")
        #     if tool:
        #         tools_to_run.append(("analyze_crime_risk", tool))

        # # Investment tool - run if financial data available
        # if property_data.get("property_info") and property_data.get("financial_data"):
        #     tool = self.registry.get_tool("calculate_investment_metrics")
        #     if tool:
        #         tools_to_run.append(("calculate_investment_metrics", tool))

        # # Walkability tool - run if walkability data available
        # if property_data.get("walkability_data"):
        #     tool = self.registry.get_tool("analyze_walkability")
        #     if tool:
        #         tools_to_run.append(("analyze_walkability", tool))

        return tools_to_run

    async def _execute_tools(
        self,
        tools_to_run: List[tuple[str, BaseTool]],
        property_data: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute all tools (in parallel where possible).

        Args:
            tools_to_run: List of (tool_name, tool_instance) tuples
            property_data: Property data for analysis

        Returns:
            Dictionary mapping tool names to their results
        """
        results = {}
        total_tools = len(tools_to_run)

        # Execute tools in parallel
        tasks = []
        tool_names = []

        for idx, (tool_name, tool) in enumerate(tools_to_run):
            logger.info(f"Executing tool {idx+1}/{total_tools}: {tool_name}")

            # Create task for parallel execution
            task = self._execute_single_tool(tool_name, tool, property_data, idx, total_tools)
            tasks.append(task)
            tool_names.append(tool_name)

        # Wait for all tools to complete
        tool_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for tool_name, result in zip(tool_names, tool_results):
            if isinstance(result, Exception):
                logger.error(f"Tool {tool_name} failed: {result}")
                results[tool_name] = {
                    "tool_name": tool_name,
                    "score": 0,
                    "grade": "F",
                    "confidence": "low",
                    "analysis": f"Tool execution failed: {str(result)}",
                    "key_findings": [],
                    "concerns": [f"Analysis failed: {str(result)}"],
                    "data_points": {},
                    "error": str(result)
                }
            else:
                results[tool_name] = result

        return results

    async def _execute_tools_with_notes(
        self,
        tools_to_run: List[tuple[str, BaseTool]],
        property_data: Dict[str, Any],
        address: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        Execute all tools and write results to notes incrementally.

        Args:
            tools_to_run: List of (tool_name, tool_instance) tuples
            property_data: Property data for analysis
            address: Property address (for notes file)

        Returns:
            Dictionary mapping tool names to their results
        """
        results = {}
        total_tools = len(tools_to_run)

        # Execute tools in parallel
        tasks = []
        tool_names = []

        for idx, (tool_name, tool) in enumerate(tools_to_run):
            logger.info(f"Executing tool {idx+1}/{total_tools}: {tool_name}")

            # Create task for parallel execution
            task = self._execute_single_tool_with_notes(
                tool_name, tool, property_data, address, idx, total_tools
            )
            tasks.append(task)
            tool_names.append(tool_name)

        # Wait for all tools to complete
        tool_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for tool_name, result in zip(tool_names, tool_results):
            if isinstance(result, Exception):
                logger.error(f"Tool {tool_name} failed: {result}")
                results[tool_name] = {
                    "tool_name": tool_name,
                    "score": 0,
                    "grade": "F",
                    "confidence": "low",
                    "analysis": f"Tool execution failed: {str(result)}",
                    "key_findings": [],
                    "concerns": [f"Analysis failed: {str(result)}"],
                    "data_points": {},
                    "error": str(result)
                }
            else:
                results[tool_name] = result

        return results

    async def _execute_single_tool_with_notes(
        self,
        tool_name: str,
        tool: BaseTool,
        property_data: Dict[str, Any],
        address: str,
        idx: int,
        total: int
    ) -> Dict[str, Any]:
        """
        Execute a single tool, update progress, and write result to notes.

        Args:
            tool_name: Name of the tool
            tool: Tool instance
            property_data: Input data
            address: Property address
            idx: Tool index (for progress)
            total: Total number of tools (for progress)

        Returns:
            Tool result dictionary
        """
        try:
            # Update progress
            progress = 15 + int((idx / total) * 65)  # Progress from 15% to 80%
            self._update_progress(f"Running {tool_name.replace('_', ' ').title()}...", progress)

            # Execute tool
            result = await tool.execute(property_data, self.llm_client)

            logger.info(f"Tool {tool_name} completed. Score: {result.get('score', 0)}/100")

            # Write result to notes immediately
            self.notes_manager.append_tool_result(address, tool_name, result)
            logger.debug(f"Wrote {tool_name} result to notes for {address}")

            return result

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            raise

    async def _generate_report_from_notes(
        self,
        address: str,
        property_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate comprehensive report from cached notes file.

        Args:
            address: Property address
            property_data: Original property data (for metadata)

        Returns:
            Comprehensive analysis report, or None if parsing failed
        """
        try:
            # Parse notes file
            parsed_notes = self.notes_manager.parse_notes_for_report(address)

            if not parsed_notes:
                logger.warning(f"Failed to parse notes for {address}")
                return None

            # Aggregate all key findings and concerns from tool results
            all_key_findings = []
            all_concerns = []

            for tool_result in parsed_notes.get('tool_results', []):
                all_key_findings.extend(tool_result.get('key_findings', []))
                all_concerns.extend(tool_result.get('concerns', []))

            # Reconstruct report structure from parsed notes
            report = {
                "overall_score": parsed_notes.get('overall_score', 0),
                "overall_grade": parsed_notes.get('overall_grade', 'F'),
                "confidence": "high",  # Cached results are high confidence

                "category_scores": parsed_notes.get('category_scores', {}),
                "detailed_analysis": {},

                "summary": {
                    "key_findings": all_key_findings,
                    "concerns": all_concerns,
                    "recommendation": parsed_notes.get('recommendation', 'No specific recommendation provided.')
                },

                "property_info": property_data.get("property_info", {}),
                "address": address,

                "metadata": {
                    "analysis_date": datetime.now().isoformat(),
                    "cached": True,
                    "notes_file": str(self.notes_manager.get_notes_path(address)),
                    "full_notes_content": parsed_notes.get('full_content', '')
                }
            }

            # Add tool results to detailed analysis with full content
            for tool_result in parsed_notes.get('tool_results', []):
                tool_name = tool_result['tool_name'].lower().replace(' ', '_')

                report["detailed_analysis"][tool_name] = {
                    "score": tool_result['score'],
                    "grade": tool_result['grade'],
                    "confidence": tool_result['confidence'],
                    "analysis": tool_result.get('analysis', ''),
                    "key_findings": tool_result.get('key_findings', []),
                    "concerns": tool_result.get('concerns', []),
                    "data_points": {}
                }

            logger.info(f"Successfully generated report from cached notes for {address}: "
                       f"{len(all_key_findings)} findings, {len(all_concerns)} concerns")

            return report

        except Exception as e:
            logger.error(f"Error generating report from notes for {address}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    async def _execute_single_tool(
        self,
        tool_name: str,
        tool: BaseTool,
        property_data: Dict[str, Any],
        idx: int,
        total: int
    ) -> Dict[str, Any]:
        """Execute a single tool and update progress (legacy method, use _execute_single_tool_with_notes instead)."""
        try:
            # Update progress
            progress = 15 + int((idx / total) * 65)  # Progress from 15% to 80%
            self._update_progress(f"Running {tool_name.replace('_', ' ').title()}...", progress)

            # Execute tool
            result = await tool.execute(property_data, self.llm_client)

            logger.info(f"Tool {tool_name} completed. Score: {result.get('score', 0)}/100")

            return result

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            raise

    def _aggregate_results(
        self,
        tool_results: Dict[str, Dict[str, Any]],
        property_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Aggregate results from all tools into final comprehensive report.

        Args:
            tool_results: Dictionary of tool results
            property_data: Original property data

        Returns:
            Final comprehensive analysis report
        """
        # Calculate category scores
        category_scores = self._calculate_category_scores(tool_results)

        # Calculate overall score (weighted average)
        overall_score = self._calculate_overall_score(category_scores)

        # Determine overall grade
        overall_grade = self._score_to_grade(overall_score)

        # Aggregate key findings and concerns
        all_findings = []
        all_concerns = []

        for tool_name, result in tool_results.items():
            findings = result.get("key_findings", [])
            concerns = result.get("concerns", [])

            all_findings.extend([f"[{tool_name}] {f}" for f in findings])
            all_concerns.extend([f"[{tool_name}] {c}" for c in concerns])

        # Build final report
        report = {
            "overall_score": round(overall_score, 1),
            "overall_grade": overall_grade,
            "confidence": self._determine_overall_confidence(tool_results),

            "category_scores": category_scores,

            "detailed_analysis": tool_results,

            "summary": {
                "key_findings": all_findings[:10],  # Top 10 findings
                "concerns": all_concerns[:10],  # Top 10 concerns
                "recommendation": self._generate_recommendation(overall_score, overall_grade)
            },

            "property_info": property_data.get("property_info", {}),
            "address": property_data.get("address", "Unknown"),

            "metadata": {
                "analysis_date": datetime.now().isoformat(),
                "tools_executed": list(tool_results.keys()),
                "tools_count": len(tool_results)
            }
        }

        return report

    def _calculate_category_scores(self, tool_results: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate scores for each main category based on tool results.

        Categories:
        - property_quality (not implemented yet)
        - location_commute (walkability)
        - neighborhood (crime)
        - education (schools)
        - environmental (not implemented yet)
        - investment (investment metrics)
        """
        category_scores = {}

        # Education category
        if "analyze_school_quality" in tool_results:
            category_scores["education"] = tool_results["analyze_school_quality"]["score"]

        # Neighborhood category
        if "analyze_crime_risk" in tool_results:
            category_scores["neighborhood"] = tool_results["analyze_crime_risk"]["score"]

        # Location & Commute category
        if "analyze_walkability" in tool_results:
            category_scores["location_commute"] = tool_results["analyze_walkability"]["score"]

        # Investment category
        if "calculate_investment_metrics" in tool_results:
            category_scores["investment"] = tool_results["calculate_investment_metrics"]["score"]

        # Placeholder for unimplemented categories
        # category_scores["property_quality"] = 0
        # category_scores["environmental"] = 0

        return category_scores

    def _calculate_overall_score(self, category_scores: Dict[str, float]) -> float:
        """
        Calculate overall score from category scores.

        Weights (from original plan):
        - property_quality: 30% (not yet implemented)
        - location_commute: 25%
        - education: 20%
        - investment: 25%
        - neighborhood: included in location quality
        - environmental: bonus/penalty

        For now, with limited tools, use equal weighting.
        """
        if not category_scores:
            return 0

        # Equal weighting for now
        total_score = sum(category_scores.values())
        overall_score = total_score / len(category_scores)

        return overall_score

    def _score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"

    def _determine_overall_confidence(self, tool_results: Dict[str, Dict[str, Any]]) -> str:
        """
        Determine overall confidence level based on tool confidences.

        Returns: "high", "medium", or "low"
        """
        confidences = [result.get("confidence", "low") for result in tool_results.values()]

        if not confidences:
            return "low"

        # Map to numeric values
        confidence_values = {
            "high": 3,
            "medium": 2,
            "low": 1
        }

        numeric_confidences = [confidence_values.get(c, 1) for c in confidences]
        avg_confidence = sum(numeric_confidences) / len(numeric_confidences)

        # Convert back
        if avg_confidence >= 2.5:
            return "high"
        elif avg_confidence >= 1.5:
            return "medium"
        else:
            return "low"

    def _generate_recommendation(self, score: float, grade: str) -> str:
        """Generate overall recommendation based on score."""
        if score >= 85:
            return "Excellent property with strong fundamentals across all analyzed categories. Highly recommended."
        elif score >= 75:
            return "Good property with solid performance in most areas. Recommended with minor considerations."
        elif score >= 65:
            return "Acceptable property with average performance. Review specific concerns before proceeding."
        elif score >= 50:
            return "Below-average property with notable concerns. Careful evaluation of risks recommended."
        else:
            return "Poor performance across analyzed categories. Significant concerns identified - proceed with caution."
