"""
Share API endpoints - create and view shareable property reports
"""
import logging
from typing import Optional, Any, Dict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.shared_report import SharedReport
from app.api.v1.deps import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateShareRequest(BaseModel):
    address: str
    report_data: Dict[str, Any]  # The full analysis data


class ShareResponse(BaseModel):
    share_code: str
    share_url: str
    address: str
    created_at: str

    class Config:
        from_attributes = True


class SharedReportResponse(BaseModel):
    share_code: str
    address: str
    report_data: Dict[str, Any]
    created_at: str
    view_count: int

    class Config:
        from_attributes = True


@router.post("", response_model=ShareResponse, status_code=status.HTTP_201_CREATED)
def create_share_link(
    req: CreateShareRequest,
    request: Request,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Create a shareable link for a property report.

    Anyone can create a share link (logged in or not).
    The report data is stored so recipients can view without credits.
    """
    # Check if we already have a recent share for this address by this user
    if user:
        existing = (
            db.query(SharedReport)
            .filter(
                SharedReport.user_id == user.id,
                SharedReport.address == req.address,
            )
            .order_by(SharedReport.created_at.desc())
            .first()
        )
        if existing:
            # Return existing share link
            base_url = str(request.base_url).rstrip('/')
            # Use frontend URL, not API URL
            frontend_url = base_url.replace(':8000', ':5173').replace('/api', '')
            if 'localhost' not in frontend_url and 'perchspot' in frontend_url:
                frontend_url = 'https://perchspot.com'

            return ShareResponse(
                share_code=existing.share_code,
                share_url=f"{frontend_url}/share/{existing.share_code}",
                address=existing.address,
                created_at=existing.created_at.isoformat() if existing.created_at else "",
            )

    # Create new share
    shared_report = SharedReport(
        address=req.address,
        user_id=user.id if user else None,
        report_data=req.report_data,
    )
    db.add(shared_report)
    db.commit()
    db.refresh(shared_report)

    logger.info(f"Created share link for {req.address}: {shared_report.share_code}")

    # Build share URL
    base_url = str(request.base_url).rstrip('/')
    frontend_url = base_url.replace(':8000', ':5173').replace('/api', '')
    if 'localhost' not in frontend_url and 'perchspot' in frontend_url:
        frontend_url = 'https://perchspot.com'

    return ShareResponse(
        share_code=shared_report.share_code,
        share_url=f"{frontend_url}/share/{shared_report.share_code}",
        address=shared_report.address,
        created_at=shared_report.created_at.isoformat() if shared_report.created_at else "",
    )


@router.get("/{share_code}", response_model=SharedReportResponse)
def get_shared_report(
    share_code: str,
    db: Session = Depends(get_db),
):
    """
    Get a shared report by its code.

    This is a PUBLIC endpoint - no authentication required.
    Anyone with the link can view the report.
    """
    shared_report = (
        db.query(SharedReport)
        .filter(SharedReport.share_code == share_code)
        .first()
    )

    if not shared_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shared report not found"
        )

    # Check expiration if set
    if shared_report.expires_at and shared_report.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This shared link has expired"
        )

    # Increment view count
    shared_report.view_count = (shared_report.view_count or 0) + 1
    db.commit()

    return SharedReportResponse(
        share_code=shared_report.share_code,
        address=shared_report.address,
        report_data=shared_report.report_data,
        created_at=shared_report.created_at.isoformat() if shared_report.created_at else "",
        view_count=shared_report.view_count,
    )
