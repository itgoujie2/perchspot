"""
Streaming Analysis API Endpoints

Server-Sent Events (SSE) endpoint for real-time property analysis.
Streams progressive updates as each section is scraped and analyzed.
"""
import logging
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
import json

from app.services.agent.streaming_orchestrator import StreamingAnalysisOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/analyze/stream/{address:path}")
async def stream_property_analysis(address: str):
    """
    Server-Sent Events endpoint for real-time property analysis.

    This endpoint establishes an SSE connection and streams progressive updates
    as the property is scraped and analyzed:

    - **init**: Analysis started
    - **status**: Status message updates
    - **data**: Scraped data for a completed step
    - **analysis**: LLM analysis for a completed step
    - **summary**: Final comprehensive summary
    - **complete**: Analysis finished
    - **error**: Error occurred

    Args:
        address: Full property address (URL-encoded)

    Returns:
        Server-Sent Event stream with progressive updates

    Example:
        GET /api/v1/streaming/analyze/stream/123%20Main%20St%2C%20Seattle%2C%20WA%2098101

    SSE Event Format:
        event: <event_type>
        data: <json_payload>

    Example Events:
        event: status
        data: {"type": "status", "message": "Starting analysis..."}

        event: data
        data: {"type": "data", "step": 3, "step_name": "Basic Property Data", "status": "scraped"}

        event: analysis
        data: {"type": "analysis", "step": 3, "step_name": "Basic Property Data", "analysis": "...", "status": "analyzed"}

        event: summary
        data: {"type": "summary", "content": "...", "status": "complete"}
    """
    logger.info(f"SSE connection established for address: {address}")

    # Create orchestrator
    orchestrator = StreamingAnalysisOrchestrator()

    async def event_generator():
        """
        Generate SSE events from the analysis stream.

        Yields:
            SSE event dictionaries with event type and JSON data
        """
        try:
            # Stream analysis events
            async for event in orchestrator.analyze_streaming(address):
                event_type = event.get("type", "message")

                # Format as SSE event
                yield {
                    "event": event_type,
                    "data": json.dumps(event)
                }

                logger.debug(f"SSE event sent: {event_type}")

        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}", exc_info=True)

            # Send error event
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": str(e)
                })
            }

        finally:
            logger.info(f"SSE connection closed for address: {address}")

    # Return EventSourceResponse for SSE
    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for streaming service.

    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "service": "streaming-analysis",
        "endpoints": {
            "stream": "/analyze/stream/{address}"
        }
    }
