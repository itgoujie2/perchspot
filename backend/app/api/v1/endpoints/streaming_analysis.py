"""
Streaming Analysis API Endpoints

Server-Sent Events (SSE) endpoint for real-time property analysis.
Streams progressive updates as each section is scraped and analyzed.
"""
import logging
import asyncio
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
import json
import time

from app.services.agent.streaming_orchestrator import StreamingAnalysisOrchestrator
from app.api.v1.deps import get_optional_user_from_query
from app.database.connection import get_db
from app.models.user import User
from app.services.auth.credit_service import has_user_paid_for_analysis, deduct_credits, check_balance
from app.services.auth.ip_tracking_service import get_ip_analysis_count, record_ip_analysis, FREE_ANALYSIS_LIMIT
from app.services.memory import MemoryService
from app.services.search import SimilarHomesService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/analyze/stream/{address:path}")
async def stream_property_analysis(
    address: str,
    request: Request,
    user: Optional[User] = Depends(get_optional_user_from_query),
    db: Session = Depends(get_db),
):
    """
    Server-Sent Events endpoint for real-time property analysis.
    Authenticated users use credits. Anonymous users get a free analysis per IP.
    """
    client_ip = request.client.host if request.client else "unknown"

    if user:
        # Authenticated flow: existing credit-based billing
        logger.info(f"SSE connection established for address: {address} (user: {user.email})")
        already_paid = has_user_paid_for_analysis(db, user.id, address)

        if not already_paid:
            balance = check_balance(db, user.id)
            if balance < Decimal("0.50"):
                raise HTTPException(
                    status_code=402,
                    detail={
                        "message": "Insufficient credits",
                        "balance": float(balance),
                        "minimum": 0.50,
                    },
                )
    else:
        # Anonymous flow: IP-based free tier
        logger.info(f"SSE connection established for address: {address} (anonymous IP: {client_ip})")
        already_paid = False
        ip_count = get_ip_analysis_count(db, client_ip)
        if ip_count >= FREE_ANALYSIS_LIMIT:
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "Free analysis used",
                    "action": "signup",
                },
            )

    # Create orchestrator
    orchestrator = StreamingAnalysisOrchestrator()

    async def event_generator():
        """
        Generate SSE events from the analysis stream.
        Includes heartbeat events to keep the connection alive when browser tab is backgrounded.
        """
        last_heartbeat = time.time()
        heartbeat_interval = 15  # Send heartbeat every 15 seconds
        analysis_complete = False

        try:
            # Create async iterator from the orchestrator
            analysis_iter = orchestrator.analyze_streaming(address).__aiter__()

            # Create initial task for getting next event
            next_event_task = asyncio.create_task(analysis_iter.__anext__())

            while not analysis_complete:
                try:
                    # Wait for either the event or timeout, WITHOUT cancelling the task
                    done, pending = await asyncio.wait(
                        [next_event_task],
                        timeout=heartbeat_interval,
                        return_when=asyncio.FIRST_COMPLETED
                    )

                    if next_event_task in done:
                        # Event received - get result and create new task for next event
                        try:
                            event = next_event_task.result()
                        except StopAsyncIteration:
                            analysis_complete = True
                            continue

                        # Create task for next event
                        next_event_task = asyncio.create_task(analysis_iter.__anext__())
                    else:
                        # Timeout - send heartbeat but keep the task running
                        yield {
                            "event": "heartbeat",
                            "data": json.dumps({"type": "heartbeat", "timestamp": time.time()})
                        }
                        logger.debug("SSE heartbeat sent")
                        last_heartbeat = time.time()
                        continue

                    event_type = event.get("type", "message")

                    # Check if this is the final event
                    if event_type in ["summary", "complete"]:
                        analysis_complete = True

                    # On summary event, handle billing
                    if event_type == "summary":
                        total_cost = event.get("total_cost", 0)

                        if user:
                            # Authenticated billing
                            if already_paid:
                                event["total_cost"] = 0
                                event["credit_deducted"] = 0
                            else:
                                deducted = deduct_credits(
                                    db, user.id, total_cost, "analysis", address,
                                    description=f"Analysis: {address}",
                                )
                                if not deducted:
                                    event["credit_deducted"] = 0
                                    event["credit_error"] = "Insufficient credits"
                                else:
                                    event["credit_deducted"] = total_cost

                            event["credit_balance"] = float(check_balance(db, user.id))

                            # Record city activity for authenticated users
                            try:
                                extracted_data = event.get("extracted_data", {})
                                prop = extracted_data.get("property", {})
                                addr_info = prop.get("address", {})
                                city = addr_info.get("city")
                                state = addr_info.get("state")
                                if city and state:
                                    memory_service = MemoryService(db)
                                    memory_service.record_city_activity(
                                        user_id=user.id,
                                        city=city,
                                        state=state,
                                        region=None,  # Could be enriched later
                                    )
                                    logger.info(f"Recorded city activity: {city}, {state} for user {user.id}")
                            except Exception as e:
                                logger.warning(f"Failed to record city activity: {e}")

                            # Save similar homes for recommendations
                            try:
                                similar_homes = extracted_data.get("similar_homes", [])
                                if similar_homes:
                                    similar_service = SimilarHomesService(db)
                                    saved_count = similar_service.save_similar_homes(
                                        user_id=user.id,
                                        source_address=address,
                                        similar_homes=similar_homes
                                    )
                                    if saved_count > 0:
                                        logger.info(f"Saved {saved_count} similar homes for user {user.id}")
                            except Exception as e:
                                logger.warning(f"Failed to save similar homes: {e}")
                        else:
                            # Anonymous: record IP usage
                            record_ip_analysis(db, client_ip, address)
                            event["credit_deducted"] = 0
                            event["total_cost"] = 0

                    yield {
                        "event": event_type,
                        "data": json.dumps(event)
                    }

                    last_heartbeat = time.time()
                    logger.debug(f"SSE event sent: {event_type}")

                except Exception as e:
                    logger.error(f"Error processing event: {e}", exc_info=True)
                    yield {
                        "event": "error",
                        "data": json.dumps({"type": "error", "error": str(e)})
                    }
                    analysis_complete = True

            # Clean up any pending task
            if not next_event_task.done():
                next_event_task.cancel()
                try:
                    await next_event_task
                except (asyncio.CancelledError, StopAsyncIteration):
                    pass

        except Exception as e:
            logger.error(f"Error in streaming analysis: {e}", exc_info=True)
            yield {
                "event": "error",
                "data": json.dumps({
                    "type": "error",
                    "error": str(e)
                })
            }

        finally:
            logger.info(f"SSE connection closed for address: {address}")

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
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
