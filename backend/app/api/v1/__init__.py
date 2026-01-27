"""
API v1 routes
"""
from fastapi import APIRouter
from app.api.v1.endpoints import properties, health, granular_analysis, conversations, streaming_analysis

router = APIRouter()

# Include endpoint routers
# Note: Old 'chat' endpoint removed - now using skills-based architecture with 'conversations'
router.include_router(properties.router, prefix="/properties", tags=["properties"])
router.include_router(conversations.router, prefix="/properties", tags=["conversations"])  # Conversations at /api/v1/properties/analysis/{id}/chat
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(granular_analysis.router, prefix="", tags=["granular-analysis"])  # Granular analysis at /api/v1/granular-analysis
router.include_router(streaming_analysis.router, prefix="/streaming", tags=["streaming"])  # Streaming analysis at /api/v1/streaming/analyze/stream/{address}
