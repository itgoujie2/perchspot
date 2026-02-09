"""
Admin API Endpoints

Provides administrative access to cached reports and system management.
All endpoints require admin authentication via X-Admin-Password header.
"""
import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from sqlalchemy import func, desc

from app.config import settings
from app.services.agent.tools.notes_manager import get_notes_manager
from app.database.connection import get_db
from app.services.promotions.promo_service import (
    create_promo_code, list_promo_codes, deactivate_promo_code, get_promo_by_code
)
from app.models.user import User, Purchase, CreditTransaction, SurveyResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_admin(x_admin_password: str = Header(...)):
    """Verify admin password from request header."""
    if x_admin_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")


class CachedReportSummary(BaseModel):
    filename: str
    address: str
    size_bytes: int
    modified: str


class CachedReportsListResponse(BaseModel):
    total: int
    reports: List[CachedReportSummary]


class CachedReportScores(BaseModel):
    property: Optional[float] = None
    location: Optional[float] = None
    schools: Optional[float] = None
    investment: Optional[float] = None


class CachedReportParsed(BaseModel):
    overall_score: Optional[float] = None
    overall_grade: Optional[str] = None
    scores: CachedReportScores
    recommendation: Optional[str] = None
    tool_results: List[Dict[str, Any]] = []


class CachedReportDetail(BaseModel):
    filename: str
    address: str
    content: str
    parsed: CachedReportParsed


@router.get("/cached-reports", response_model=CachedReportsListResponse,
            dependencies=[Depends(verify_admin)])
async def list_cached_reports():
    """List all cached housing analysis reports."""
    try:
        notes_manager = get_notes_manager()
        summary = notes_manager.get_notes_summary()

        reports = [
            CachedReportSummary(
                filename=f["filename"],
                address=f["address"],
                size_bytes=f["size_bytes"],
                modified=f["modified"]
            )
            for f in summary["files"]
        ]

        # Sort by modified date, newest first
        reports.sort(key=lambda r: r.modified, reverse=True)

        return CachedReportsListResponse(
            total=summary["total_files"],
            reports=reports
        )
    except Exception as e:
        logger.error(f"Error listing cached reports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cached-reports/{filename}", response_model=CachedReportDetail,
            dependencies=[Depends(verify_admin)])
async def get_cached_report(filename: str):
    """Get a specific cached report with parsed content."""
    try:
        notes_manager = get_notes_manager()

        # Validate filename
        if not filename.endswith('.md'):
            filename = f"{filename}.md"

        # Derive address from filename
        address = filename.replace('.md', '').replace('_', ' ').title()

        # Read the notes content
        content = notes_manager.read_notes(address)

        if content is None:
            raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

        # Parse the notes for structured data
        parsed_data = notes_manager.parse_notes_for_report(address)

        # Extract category scores
        category_scores = parsed_data.get('category_scores', {}) if parsed_data else {}

        scores = CachedReportScores(
            property=category_scores.get('property'),
            location=category_scores.get('location'),
            schools=category_scores.get('schools'),
            investment=category_scores.get('investment')
        )

        parsed = CachedReportParsed(
            overall_score=parsed_data.get('overall_score') if parsed_data else None,
            overall_grade=parsed_data.get('overall_grade') if parsed_data else None,
            scores=scores,
            recommendation=parsed_data.get('recommendation') if parsed_data else None,
            tool_results=parsed_data.get('tool_results', []) if parsed_data else []
        )

        return CachedReportDetail(
            filename=filename,
            address=address,
            content=content,
            parsed=parsed
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reading cached report {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cached-reports/{filename}",
               dependencies=[Depends(verify_admin)])
async def delete_cached_report(filename: str):
    """Delete a specific cached report."""
    try:
        notes_manager = get_notes_manager()

        # Validate filename
        if not filename.endswith('.md'):
            filename = f"{filename}.md"

        # Get the full path
        notes_path = notes_manager.notes_dir / filename

        if not notes_path.exists():
            raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

        # Delete the file
        notes_path.unlink()

        logger.info(f"Deleted cached report: {filename}")

        return {"status": "ok", "deleted": filename}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting cached report {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Promo Code Management Endpoints
# ============================================

class CreatePromoRequest(BaseModel):
    credit_amount: float
    max_uses: Optional[int] = 1
    note: Optional[str] = None
    expires_days: Optional[int] = None  # Days until expiration


class PromoCodeResponse(BaseModel):
    code: str
    credit_amount: float
    max_uses: Optional[int]
    uses_count: int
    is_active: bool
    note: Optional[str]
    created_at: str
    expires_at: Optional[str]
    registration_url: str


class PromoCodeListResponse(BaseModel):
    total: int
    promo_codes: List[PromoCodeResponse]


@router.post("/promo-codes", response_model=PromoCodeResponse,
             dependencies=[Depends(verify_admin)])
async def create_promo(
    request: CreatePromoRequest,
    db: Session = Depends(get_db)
):
    """Create a new promo code with custom credit amount."""
    try:
        from datetime import timedelta

        expires_at = None
        if request.expires_days:
            expires_at = datetime.utcnow() + timedelta(days=request.expires_days)

        promo = create_promo_code(
            db=db,
            credit_amount=request.credit_amount,
            max_uses=request.max_uses,
            note=request.note,
            expires_at=expires_at,
        )

        # Build registration URL
        domain = os.getenv("DOMAIN", "perchspot.com")
        registration_url = f"https://{domain}/register?promo={promo.code}"

        return PromoCodeResponse(
            code=promo.code,
            credit_amount=float(promo.credit_amount),
            max_uses=promo.max_uses,
            uses_count=promo.uses_count,
            is_active=promo.is_active,
            note=promo.note,
            created_at=promo.created_at.isoformat(),
            expires_at=promo.expires_at.isoformat() if promo.expires_at else None,
            registration_url=registration_url,
        )
    except Exception as e:
        logger.error(f"Error creating promo code: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/promo-codes", response_model=PromoCodeListResponse,
            dependencies=[Depends(verify_admin)])
async def list_promos(
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """List all promo codes."""
    try:
        promos = list_promo_codes(db, include_inactive=include_inactive)
        domain = os.getenv("DOMAIN", "perchspot.com")

        promo_responses = [
            PromoCodeResponse(
                code=p.code,
                credit_amount=float(p.credit_amount),
                max_uses=p.max_uses,
                uses_count=p.uses_count,
                is_active=p.is_active,
                note=p.note,
                created_at=p.created_at.isoformat(),
                expires_at=p.expires_at.isoformat() if p.expires_at else None,
                registration_url=f"https://{domain}/register?promo={p.code}",
            )
            for p in promos
        ]

        return PromoCodeListResponse(
            total=len(promo_responses),
            promo_codes=promo_responses,
        )
    except Exception as e:
        logger.error(f"Error listing promo codes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/promo-codes/{code}",
               dependencies=[Depends(verify_admin)])
async def deactivate_promo(code: str, db: Session = Depends(get_db)):
    """Deactivate a promo code."""
    try:
        success = deactivate_promo_code(db, code)
        if not success:
            raise HTTPException(status_code=404, detail=f"Promo code not found: {code}")
        return {"status": "ok", "deactivated": code}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating promo code {code}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# User Management Endpoints
# ============================================

class UserPurchaseInfo(BaseModel):
    id: str
    amount: float
    credits: float
    status: str
    created_at: str
    completed_at: Optional[str] = None


class UserSummary(BaseModel):
    id: str
    email: str
    credit_balance: float
    total_purchased: float  # Total $ spent
    total_credits_purchased: float  # Total credits bought
    purchase_count: int
    created_at: str
    last_purchase_at: Optional[str] = None


class UserDetail(BaseModel):
    id: str
    email: str
    credit_balance: float
    created_at: str
    survey_completed: bool
    first_purchase_bonus_claimed: bool
    purchases: List[UserPurchaseInfo]
    total_purchased: float
    total_credits_purchased: float


class UserListResponse(BaseModel):
    total: int
    users: List[UserSummary]
    summary: Dict[str, Any]


@router.get("/users", response_model=UserListResponse,
            dependencies=[Depends(verify_admin)])
async def list_users(db: Session = Depends(get_db)):
    """List all registered users with purchase summary."""
    try:
        # Query users with purchase aggregation
        users = db.query(User).order_by(desc(User.created_at)).all()

        user_summaries = []
        total_revenue = 0.0
        total_users_with_purchases = 0

        for user in users:
            # Get completed purchases for this user
            purchases = db.query(Purchase).filter(
                Purchase.user_id == user.id,
                Purchase.status == 'completed'
            ).all()

            total_purchased = sum(float(p.amount) for p in purchases)
            total_credits = sum(float(p.credits) for p in purchases)
            purchase_count = len(purchases)

            if purchase_count > 0:
                total_users_with_purchases += 1
                total_revenue += total_purchased

            # Get last purchase date
            last_purchase = None
            if purchases:
                last_purchase = max(p.completed_at or p.created_at for p in purchases)

            user_summaries.append(UserSummary(
                id=user.id,
                email=user.email,
                credit_balance=float(user.credit_balance),
                total_purchased=total_purchased,
                total_credits_purchased=total_credits,
                purchase_count=purchase_count,
                created_at=user.created_at.isoformat() if user.created_at else "",
                last_purchase_at=last_purchase.isoformat() if last_purchase else None,
            ))

        return UserListResponse(
            total=len(users),
            users=user_summaries,
            summary={
                "total_users": len(users),
                "users_with_purchases": total_users_with_purchases,
                "total_revenue": round(total_revenue, 2),
            }
        )
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}", response_model=UserDetail,
            dependencies=[Depends(verify_admin)])
async def get_user_detail(user_id: str, db: Session = Depends(get_db)):
    """Get detailed user information including all purchases."""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        purchases = db.query(Purchase).filter(
            Purchase.user_id == user_id
        ).order_by(desc(Purchase.created_at)).all()

        purchase_infos = [
            UserPurchaseInfo(
                id=p.id,
                amount=float(p.amount),
                credits=float(p.credits),
                status=p.status,
                created_at=p.created_at.isoformat() if p.created_at else "",
                completed_at=p.completed_at.isoformat() if p.completed_at else None,
            )
            for p in purchases
        ]

        completed_purchases = [p for p in purchases if p.status == 'completed']
        total_purchased = sum(float(p.amount) for p in completed_purchases)
        total_credits = sum(float(p.credits) for p in completed_purchases)

        return UserDetail(
            id=user.id,
            email=user.email,
            credit_balance=float(user.credit_balance),
            created_at=user.created_at.isoformat() if user.created_at else "",
            survey_completed=user.survey_completed == "true",
            first_purchase_bonus_claimed=user.first_purchase_bonus_claimed == "true",
            purchases=purchase_infos,
            total_purchased=total_purchased,
            total_credits_purchased=total_credits,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user detail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Survey Response Endpoints
# ============================================

class SurveyResponseItem(BaseModel):
    id: str
    user_email: str
    how_did_you_hear: Optional[str] = None
    satisfaction: Optional[str] = None
    improvements: Optional[str] = None
    created_at: str


class SurveyListResponse(BaseModel):
    total: int
    surveys: List[SurveyResponseItem]
    summary: Dict[str, Any]


@router.get("/surveys", response_model=SurveyListResponse,
            dependencies=[Depends(verify_admin)])
async def list_surveys(db: Session = Depends(get_db)):
    """List all survey responses."""
    try:
        # Query surveys with user info
        surveys = db.query(SurveyResponse, User.email).join(
            User, SurveyResponse.user_id == User.id
        ).order_by(desc(SurveyResponse.created_at)).all()

        # Calculate satisfaction stats
        satisfaction_counts = {}
        source_counts = {}

        survey_items = []
        for survey, email in surveys:
            survey_items.append(SurveyResponseItem(
                id=survey.id,
                user_email=email,
                how_did_you_hear=survey.how_did_you_hear,
                satisfaction=survey.satisfaction,
                improvements=survey.improvements,
                created_at=survey.created_at.isoformat() if survey.created_at else "",
            ))

            # Count satisfaction ratings
            if survey.satisfaction:
                satisfaction_counts[survey.satisfaction] = satisfaction_counts.get(survey.satisfaction, 0) + 1

            # Count sources
            if survey.how_did_you_hear:
                source_counts[survey.how_did_you_hear] = source_counts.get(survey.how_did_you_hear, 0) + 1

        # Calculate average satisfaction
        avg_satisfaction = None
        if satisfaction_counts:
            total_ratings = sum(int(k) * v for k, v in satisfaction_counts.items() if k.isdigit())
            total_count = sum(v for k, v in satisfaction_counts.items() if k.isdigit())
            if total_count > 0:
                avg_satisfaction = round(total_ratings / total_count, 1)

        return SurveyListResponse(
            total=len(survey_items),
            surveys=survey_items,
            summary={
                "total_responses": len(survey_items),
                "average_satisfaction": avg_satisfaction,
                "satisfaction_breakdown": satisfaction_counts,
                "source_breakdown": source_counts,
            }
        )
    except Exception as e:
        logger.error(f"Error listing surveys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
