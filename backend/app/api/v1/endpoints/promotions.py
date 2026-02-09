"""
Promotions API endpoints - feedback survey, promotion status
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User, SurveyResponse
from app.api.v1.deps import get_current_user
from app.services.auth.credit_service import add_credits

logger = logging.getLogger(__name__)

router = APIRouter()

SURVEY_REWARD_AMOUNT = 1.00


class PromotionStatusResponse(BaseModel):
    survey_completed: bool
    survey_reward_available: bool
    survey_reward_amount: float


class SurveySubmitRequest(BaseModel):
    how_did_you_hear: Optional[str] = None
    satisfaction: Optional[str] = None
    improvements: Optional[str] = None


class SurveyCompleteResponse(BaseModel):
    success: bool
    credits_awarded: float
    message: str


@router.get("/status", response_model=PromotionStatusResponse)
def get_promotion_status(
    user: User = Depends(get_current_user),
):
    """Get the user's promotion status (survey completion, etc.)."""
    survey_done = user.survey_completed == "true"
    return PromotionStatusResponse(
        survey_completed=survey_done,
        survey_reward_available=not survey_done,
        survey_reward_amount=SURVEY_REWARD_AMOUNT,
    )


@router.post("/survey-complete", response_model=SurveyCompleteResponse)
def complete_survey(
    request: SurveySubmitRequest = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Mark the user's survey as completed, store responses, and award credits.
    This is a one-time reward.
    """
    if user.survey_completed == "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Survey reward already claimed",
        )

    # Store survey response if provided
    if request:
        survey_response = SurveyResponse(
            user_id=user.id,
            how_did_you_hear=request.how_did_you_hear,
            satisfaction=request.satisfaction,
            improvements=request.improvements,
        )
        db.add(survey_response)

    # Mark survey as completed
    user.survey_completed = "true"
    db.flush()

    # Add credits
    add_credits(
        db=db,
        user_id=user.id,
        amount=SURVEY_REWARD_AMOUNT,
        tx_type="survey_reward",
        description="Feedback survey completion reward",
    )

    logger.info(f"User {user.id} completed survey, awarded ${SURVEY_REWARD_AMOUNT}")

    return SurveyCompleteResponse(
        success=True,
        credits_awarded=SURVEY_REWARD_AMOUNT,
        message=f"Thank you for your feedback! ${SURVEY_REWARD_AMOUNT:.2f} has been added to your account.",
    )
