"""
Granular Analysis API endpoints with real-time progress updates via SSE.
"""
import logging
import asyncio
import json
from typing import AsyncIterator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from openai import AsyncOpenAI

from app.config import settings
from app.services.agent.tools.tool_orchestrator import ToolOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/granular-analysis/test")
async def test_endpoint():
    """Simple test endpoint to verify API is working"""
    return {
        "status": "ok",
        "message": "Granular analysis endpoint is accessible",
        "environment": getattr(settings, 'ENVIRONMENT', 'development')
    }


class GranularAnalyzeRequest(BaseModel):
    """Request for granular property analysis"""
    address: str = Field(..., description="Property address to analyze")
    reuse_notes: bool = Field(True, description="Whether to reuse cached notes if available")
    # Mock data for now - in production, this would come from data collectors
    property_info: dict = Field(default_factory=dict)
    schools: list = Field(default_factory=list)
    crime_data: dict = Field(default_factory=dict)
    walkability_data: dict = Field(default_factory=dict)
    nearby_amenities: dict = Field(default_factory=dict)
    transit_options: list = Field(default_factory=list)
    bike_infrastructure: dict = Field(default_factory=dict)
    financial_data: dict = Field(default_factory=dict)
    financing: dict = Field(default_factory=dict)
    market_data: dict = Field(default_factory=dict)


def create_progress_event(message: str, progress: int, event_type: str = "progress") -> str:
    """
    Create a Server-Sent Event formatted message.

    Args:
        message: Progress message
        progress: Progress percentage (0-100)
        event_type: Event type (progress, complete, error)

    Returns:
        SSE formatted string
    """
    data = {
        "message": message,
        "progress": progress,
        "type": event_type
    }
    return f"data: {json.dumps(data)}\n\n"


async def granular_analysis_stream(request: GranularAnalyzeRequest) -> AsyncIterator[str]:
    """
    Stream analysis progress updates and final report.

    Yields SSE formatted progress updates during analysis.
    """
    try:
        # Send initial progress
        yield create_progress_event("Initializing analysis...", 0)

        # Initialize OpenAI client
        llm_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # Create orchestrator with development environment
        # (Change to "production" in production deployment)
        environment = getattr(settings, 'ENVIRONMENT', 'development')
        orchestrator = ToolOrchestrator(
            llm_client,
            environment=environment,
            reuse_notes=request.reuse_notes
        )

        # Progress callback to send SSE updates
        progress_queue = asyncio.Queue()

        def progress_callback(message: str, progress: int):
            """Callback to capture progress updates"""
            try:
                # Put progress update in queue (non-blocking)
                progress_queue.put_nowait({
                    "message": message,
                    "progress": progress
                })
            except asyncio.QueueFull:
                logger.warning("Progress queue full, dropping update")

        orchestrator.set_progress_callback(progress_callback)

        # Build property data from request
        property_data = {
            "address": request.address,
            "property_info": request.property_info,
            "schools": request.schools,
            "crime_data": request.crime_data,
            "walkability_data": request.walkability_data,
            "nearby_amenities": request.nearby_amenities,
            "transit_options": request.transit_options,
            "bike_infrastructure": request.bike_infrastructure,
            "financial_data": request.financial_data,
            "financing": request.financing,
            "market_data": request.market_data
        }

        # Start analysis in background task
        analysis_task = asyncio.create_task(
            orchestrator.analyze_property(property_data)
        )

        # Stream progress updates while analysis runs
        while not analysis_task.done():
            try:
                # Wait for progress update with timeout
                update = await asyncio.wait_for(
                    progress_queue.get(),
                    timeout=0.5
                )

                # Send progress update
                yield create_progress_event(
                    update["message"],
                    update["progress"]
                )

            except asyncio.TimeoutError:
                # No update available, continue waiting
                continue

        # Drain remaining progress updates from queue
        while not progress_queue.empty():
            try:
                update = progress_queue.get_nowait()
                yield create_progress_event(
                    update["message"],
                    update["progress"]
                )
            except asyncio.QueueEmpty:
                break

        # Get analysis result
        report = await analysis_task

        # Send completion event with full report
        yield create_progress_event(
            "Analysis complete!",
            100,
            event_type="complete"
        )

        # Send final report as separate event
        report_event = f"data: {json.dumps({'type': 'report', 'data': report})}\n\n"
        yield report_event

        logger.info(f"Completed granular analysis for {request.address}")

    except Exception as e:
        logger.error(f"Error in granular analysis: {e}", exc_info=True)

        # Send error event
        error_data = {
            "type": "error",
            "message": f"Analysis failed: {str(e)}"
        }
        yield f"data: {json.dumps(error_data)}\n\n"


@router.post("/granular-analysis/stream")
async def analyze_property_stream(request: GranularAnalyzeRequest):
    """
    Analyze property with real-time progress updates via Server-Sent Events.

    Returns a stream of progress updates followed by the final report.

    Example usage:
    ```javascript
    const eventSource = new EventSource('/api/v1/granular-analysis/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'progress') {
            console.log(`${data.progress}%: ${data.message}`);
        } else if (data.type === 'complete') {
            console.log('Analysis complete!');
        } else if (data.type === 'report') {
            console.log('Final report:', data.data);
        }
    };
    ```
    """
    return StreamingResponse(
        granular_analysis_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post("/granular-analysis")
async def analyze_property_sync(request: GranularAnalyzeRequest):
    """
    Analyze property synchronously (no progress updates).

    Returns the complete analysis report once finished.
    Useful for simple API calls without streaming.
    """
    try:
        logger.info(f"Starting synchronous granular analysis for: {request.address}")
        logger.info(f"Request data - schools: {len(request.schools)}, crime_data: {bool(request.crime_data)}")

        # Check if OpenAI API key is configured
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            logger.error("OPENAI_API_KEY not configured in settings")
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY not configured. Please set it in environment variables."
            )

        # Initialize OpenAI client
        logger.info("Initializing OpenAI client...")
        llm_client = AsyncOpenAI(api_key=api_key)

        # Create orchestrator
        environment = getattr(settings, 'ENVIRONMENT', 'development')
        logger.info(f"Creating orchestrator in {environment} mode")

        orchestrator = ToolOrchestrator(
            llm_client,
            environment=environment,
            reuse_notes=request.reuse_notes
        )

        # Build property data
        property_data = {
            "address": request.address,
            "property_info": request.property_info,
            "schools": request.schools,
            "crime_data": request.crime_data,
            "walkability_data": request.walkability_data,
            "nearby_amenities": request.nearby_amenities,
            "transit_options": request.transit_options,
            "bike_infrastructure": request.bike_infrastructure,
            "financial_data": request.financial_data,
            "financing": request.financing,
            "market_data": request.market_data
        }

        logger.info("Starting analysis...")

        # Run analysis
        report = await orchestrator.analyze_property(property_data)

        logger.info(f"Completed sync granular analysis for {request.address}. Score: {report.get('overall_score')}")

        return report

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Synchronous granular analysis error: {e}", exc_info=True)
        error_detail = f"{type(e).__name__}: {str(e)}"
        raise HTTPException(status_code=500, detail=error_detail)
