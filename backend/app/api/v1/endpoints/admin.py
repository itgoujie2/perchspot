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

from app.config import settings
from app.services.agent.tools.notes_manager import get_notes_manager
from app.database.connection import get_db
from app.services.promotions.promo_service import (
    create_promo_code, list_promo_codes, deactivate_promo_code, get_promo_by_code
)

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
