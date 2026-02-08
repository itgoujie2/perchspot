"""
Referral program API endpoints
"""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.api.v1.deps import get_current_user
from app.services.promotions.referral_service import (
    get_or_create_referral_code,
    get_referral_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ReferralCodeResponse(BaseModel):
    referral_code: str
    referral_link: str


class ReferralStatsResponse(BaseModel):
    pending_rewards: int  # Friends who signed up but haven't purchased yet
    completed_referrals: int  # Friends who purchased (reward granted)
    total_earned: float  # Total credits earned from referrals


@router.get("/my-code", response_model=ReferralCodeResponse)
def get_my_referral_code(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current user's referral code (creates one if doesn't exist)."""
    code = get_or_create_referral_code(db, user.id)
    return ReferralCodeResponse(
        referral_code=code,
        referral_link=f"https://perchspot.com/?ref={code}",
    )


@router.get("/stats", response_model=ReferralStatsResponse)
def get_my_referral_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get referral statistics for the current user."""
    stats = get_referral_stats(db, user.id)
    return ReferralStatsResponse(**stats)
