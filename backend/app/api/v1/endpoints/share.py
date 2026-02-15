"""
Share API endpoints - create and view shareable property reports
"""
import logging
from typing import Optional, Any, Dict
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.shared_report import SharedReport
from app.api.v1.deps import get_optional_user

logger = logging.getLogger(__name__)

router = APIRouter()


# Common social media crawler user agents
CRAWLER_USER_AGENTS = [
    'facebookexternalhit',
    'linkedinbot',
    'twitterbot',
    'slackbot',
    'whatsapp',
    'telegrambot',
    'discordbot',
]


def is_crawler(user_agent: str) -> bool:
    """Check if the request is from a social media crawler"""
    if not user_agent:
        return False
    ua_lower = user_agent.lower()
    return any(bot in ua_lower for bot in CRAWLER_USER_AGENTS)


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

            # Use the /og endpoint which has proper meta tags and redirects
            api_base = str(request.base_url).rstrip('/')
            if 'localhost' in api_base:
                api_base = api_base.replace(':8000', ':8000')  # Keep API port
            else:
                api_base = 'https://perchspot.com/api'

            return ShareResponse(
                share_code=existing.share_code,
                share_url=f"{api_base}/v1/share/{existing.share_code}/og",
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

    # Build share URL using the /og endpoint for proper meta tags
    api_base = str(request.base_url).rstrip('/')
    if 'localhost' in api_base:
        api_base = api_base.replace(':8000', ':8000')  # Keep API port
    else:
        api_base = 'https://perchspot.com/api'

    return ShareResponse(
        share_code=shared_report.share_code,
        share_url=f"{api_base}/v1/share/{shared_report.share_code}/og",
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


@router.get("/{share_code}/og", response_class=HTMLResponse)
def get_share_preview(
    share_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Serve an HTML page with Open Graph meta tags for social media crawlers.
    This page auto-redirects to the React app for regular browsers.
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

    # Extract data for meta tags
    address = shared_report.address
    report_data = shared_report.report_data or {}

    # Get scores
    analysis_results = report_data.get('analysis_results', {})
    scores = []
    for key in ['property', 'location', 'schools', 'investment']:
        score = analysis_results.get(key, {}).get('score')
        if score:
            scores.append(score)

    overall_score = round(sum(scores) / len(scores)) if scores else None

    # Get property details
    prop = report_data.get('property', {})
    pricing = report_data.get('pricing', {})
    price = pricing.get('list_price') or prop.get('price')
    beds = prop.get('bedrooms') or prop.get('beds')
    baths = prop.get('bathrooms') or prop.get('baths')
    sqft = prop.get('living_area_sqft') or prop.get('sqft')

    # Build description
    details = []
    if price:
        price_str = f"${int(price):,}" if isinstance(price, (int, float)) else str(price)
        details.append(price_str)
    if beds:
        details.append(f"{beds} bed")
    if baths:
        details.append(f"{baths} bath")
    if sqft:
        sqft_str = f"{int(sqft):,}" if isinstance(sqft, (int, float)) else str(sqft)
        details.append(f"{sqft_str} sqft")

    property_details = " | ".join(details) if details else ""

    if overall_score:
        description = f"{property_details} • AI Score: {overall_score}/100"
    else:
        description = property_details or f"Property analysis for {address}"

    # Get image if available
    images = report_data.get('images', {})
    image_url = images.get('main_photo_url', 'https://perchspot.com/og-image.png')

    # Frontend URL for redirect
    frontend_url = 'https://perchspot.com'
    redirect_url = f"{frontend_url}/share/{share_code}"

    # Build HTML with OG tags
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{address} - Property Analysis | Perchspot</title>
    <meta name="description" content="{description}">

    <!-- Open Graph / Facebook -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="{redirect_url}">
    <meta property="og:title" content="{address}">
    <meta property="og:description" content="{description}">
    <meta property="og:image" content="{image_url}">
    <meta property="og:site_name" content="Perchspot">

    <!-- Twitter -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:url" content="{redirect_url}">
    <meta name="twitter:title" content="{address}">
    <meta name="twitter:description" content="{description}">
    <meta name="twitter:image" content="{image_url}">

    <!-- LinkedIn specific -->
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">

    <!-- Redirect for browsers -->
    <meta http-equiv="refresh" content="0; url={redirect_url}">
    <link rel="canonical" href="{redirect_url}">
</head>
<body>
    <p>Redirecting to <a href="{redirect_url}">Perchspot</a>...</p>
    <script>window.location.href = "{redirect_url}";</script>
</body>
</html>"""

    return HTMLResponse(content=html)
