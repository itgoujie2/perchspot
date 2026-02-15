"""
API v1 routes
"""
from fastapi import APIRouter
from app.api.v1.endpoints import properties, health, granular_analysis, conversations, streaming_analysis, knowledge, chat, auth, payments, admin, documents, memory, referrals, promotions, favorites, history, compare, share, email

router = APIRouter()

# Include endpoint routers
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(chat.router, prefix="/chat", tags=["chat"])  # Chat at /api/v1/chat/chat
router.include_router(properties.router, prefix="/properties", tags=["properties"])
router.include_router(conversations.router, prefix="/properties", tags=["conversations"])  # Conversations at /api/v1/properties/analysis/{id}/chat
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(granular_analysis.router, prefix="", tags=["granular-analysis"])  # Granular analysis at /api/v1/granular-analysis
router.include_router(streaming_analysis.router, prefix="/streaming", tags=["streaming"])  # Streaming analysis at /api/v1/streaming/analyze/stream/{address}
router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])  # Knowledge store at /api/v1/knowledge/
router.include_router(payments.router, prefix="/payments", tags=["payments"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])  # Document upload at /api/v1/documents/
router.include_router(memory.router, prefix="/user", tags=["user"])  # User memories at /api/v1/user/memories
router.include_router(referrals.router, prefix="/referrals", tags=["referrals"])  # Referral program at /api/v1/referrals/
router.include_router(promotions.router, prefix="/promotions", tags=["promotions"])  # Promotions at /api/v1/promotions/
router.include_router(favorites.router, prefix="/favorites", tags=["favorites"])  # Favorites at /api/v1/favorites/
router.include_router(history.router, prefix="/history", tags=["history"])  # History at /api/v1/history/
router.include_router(compare.router, prefix="/compare", tags=["compare"])  # Compare at /api/v1/compare/
router.include_router(share.router, prefix="/share", tags=["share"])  # Share at /api/v1/share/
router.include_router(email.router, prefix="/email", tags=["email"])  # Email at /api/v1/email/
