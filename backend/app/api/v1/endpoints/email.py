"""
Email preferences and unsubscribe API endpoints
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.models.email_preference import EmailPreference
from app.api.v1.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class EmailPreferencesResponse(BaseModel):
    """Email preferences response"""
    weekly_digest: bool
    market_updates: bool
    promotional: bool

    class Config:
        from_attributes = True


class UpdateEmailPreferencesRequest(BaseModel):
    """Update email preferences request"""
    weekly_digest: Optional[bool] = None
    market_updates: Optional[bool] = None
    promotional: Optional[bool] = None


@router.get("/preferences", response_model=EmailPreferencesResponse)
def get_email_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's email preferences"""
    prefs = db.query(EmailPreference).filter(EmailPreference.user_id == user.id).first()

    if not prefs:
        # Return default preferences (all enabled except promotional)
        return EmailPreferencesResponse(
            weekly_digest=True,
            market_updates=True,
            promotional=False,
        )

    return EmailPreferencesResponse(
        weekly_digest=prefs.weekly_digest,
        market_updates=prefs.market_updates,
        promotional=prefs.promotional,
    )


@router.put("/preferences", response_model=EmailPreferencesResponse)
def update_email_preferences(
    req: UpdateEmailPreferencesRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update user's email preferences"""
    prefs = db.query(EmailPreference).filter(EmailPreference.user_id == user.id).first()

    if not prefs:
        # Create new preferences
        prefs = EmailPreference(user_id=user.id)
        db.add(prefs)

    # Update only provided fields
    if req.weekly_digest is not None:
        prefs.weekly_digest = req.weekly_digest
    if req.market_updates is not None:
        prefs.market_updates = req.market_updates
    if req.promotional is not None:
        prefs.promotional = req.promotional

    db.commit()
    db.refresh(prefs)

    logger.info(f"Updated email preferences for user {user.email}")

    return EmailPreferencesResponse(
        weekly_digest=prefs.weekly_digest,
        market_updates=prefs.market_updates,
        promotional=prefs.promotional,
    )


@router.get("/unsubscribe/{token}", response_class=HTMLResponse)
def unsubscribe_email(
    token: str,
    db: Session = Depends(get_db),
):
    """
    One-click unsubscribe endpoint (public, no auth required).
    CAN-SPAM compliance: must be accessible without login.
    """
    prefs = db.query(EmailPreference).filter(EmailPreference.unsubscribe_token == token).first()

    if not prefs:
        # Return a friendly error page
        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Unsubscribe - Perchspot</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                           display: flex; justify-content: center; align-items: center; min-height: 100vh;
                           background: #F1F5F9; margin: 0; }
                    .card { background: white; padding: 40px; border-radius: 12px; text-align: center;
                            box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; }
                    h1 { color: #EF4444; margin: 0 0 15px; }
                    p { color: #64748B; line-height: 1.6; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>Invalid Link</h1>
                    <p>This unsubscribe link is invalid or has expired.
                       Please log in to manage your email preferences.</p>
                </div>
            </body>
            </html>
            """,
            status_code=404,
        )

    # Unsubscribe from weekly digest (the main email type)
    prefs.weekly_digest = False
    db.commit()

    logger.info(f"User unsubscribed via token: {token[:10]}...")

    # Return success page
    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Unsubscribed - Perchspot</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                       display: flex; justify-content: center; align-items: center; min-height: 100vh;
                       background: #F1F5F9; margin: 0; }
                .card { background: white; padding: 40px; border-radius: 12px; text-align: center;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; }
                h1 { color: #10B981; margin: 0 0 15px; }
                p { color: #64748B; line-height: 1.6; }
                a { color: #2563EB; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Unsubscribed</h1>
                <p>You've been successfully unsubscribed from our weekly digest emails.</p>
                <p style="margin-top: 20px;">
                    <a href="https://perchspot.com">Return to Perchspot</a>
                </p>
            </div>
        </body>
        </html>
        """
    )


@router.post("/resubscribe/{token}", response_class=HTMLResponse)
def resubscribe_email(
    token: str,
    db: Session = Depends(get_db),
):
    """
    Resubscribe endpoint (public, no auth required).
    """
    prefs = db.query(EmailPreference).filter(EmailPreference.unsubscribe_token == token).first()

    if not prefs:
        raise HTTPException(status_code=404, detail="Invalid token")

    prefs.weekly_digest = True
    db.commit()

    logger.info(f"User resubscribed via token: {token[:10]}...")

    return HTMLResponse(
        content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Resubscribed - Perchspot</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                       display: flex; justify-content: center; align-items: center; min-height: 100vh;
                       background: #F1F5F9; margin: 0; }
                .card { background: white; padding: 40px; border-radius: 12px; text-align: center;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1); max-width: 400px; }
                h1 { color: #2563EB; margin: 0 0 15px; }
                p { color: #64748B; line-height: 1.6; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Welcome Back!</h1>
                <p>You've been successfully resubscribed to our weekly digest emails.</p>
            </div>
        </body>
        </html>
        """
    )
