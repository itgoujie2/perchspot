"""
Stripe payment endpoints - packages, checkout, webhook
"""
import logging
from datetime import datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database.connection import get_db
from app.models.user import Purchase
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.services.auth.credit_service import add_credits
from app.services.promotions.referral_service import reward_referrer

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Credit packages
# ---------------------------------------------------------------------------

PRESET_AMOUNTS = [5, 10, 20]
MIN_AMOUNT = 1
MAX_AMOUNT = 100
FIRST_PURCHASE_BONUS_PERCENT = 0.10  # 10% bonus on first purchase


class CheckoutRequest(BaseModel):
    amount: int  # dollar amount, 1 credit = $1


@router.get("/presets")
def get_presets():
    """Return preset credit amounts (1 credit = $1)."""
    return {"presets": PRESET_AMOUNTS, "min": MIN_AMOUNT, "max": MAX_AMOUNT}


@router.post("/create-checkout")
def create_checkout(
    req: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout Session for the given dollar amount (1 credit = $1)."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")

    if req.amount < MIN_AMOUNT or req.amount > MAX_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Amount must be between ${MIN_AMOUNT} and ${MAX_AMOUNT}")

    credits = req.amount
    price_cents = req.amount * 100

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": price_cents,
                    "product_data": {
                        "name": f"{credits} Perchspot Credits",
                        "description": f"Perchspot — {credits} credits",
                    },
                },
                "quantity": 1,
            }],
            success_url="http://localhost:5173/chat?purchase=success",
            cancel_url="http://localhost:5173/chat?purchase=cancel",
            client_reference_id=user.id,
            metadata={
                "user_id": user.id,
                "credits": str(credits),
            },
        )
    except stripe.StripeError as e:
        logger.error(f"Stripe error creating checkout: {e}")
        raise HTTPException(status_code=502, detail="Payment service error")

    # Record pending purchase
    purchase = Purchase(
        user_id=user.id,
        amount=req.amount,
        credits=credits,
        stripe_checkout_session_id=session.id,
        status="pending",
    )
    db.add(purchase)
    db.commit()

    logger.info(f"Checkout session created for user {user.id}, ${req.amount} = {credits} credits, session {session.id}")
    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events (no auth — verified by signature)."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.warning("STRIPE_WEBHOOK_SECRET not set — skipping signature verification")
        raise HTTPException(status_code=503, detail="Webhook not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        checkout_session_id = session["id"]
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id") or session.get("client_reference_id")
        credits_str = metadata.get("credits", "0")

        if not user_id:
            logger.error(f"Webhook: no user_id in session {checkout_session_id}")
            return {"status": "error", "message": "no user_id"}

        # Find the pending purchase
        purchase = db.query(Purchase).filter(
            Purchase.stripe_checkout_session_id == checkout_session_id
        ).first()

        if not purchase:
            logger.warning(f"Webhook: no purchase record for session {checkout_session_id}")
            return {"status": "ignored"}

        if purchase.status == "completed":
            logger.info(f"Webhook: purchase {purchase.id} already completed (duplicate event)")
            return {"status": "already_completed"}

        # Update purchase record
        purchase.status = "completed"
        purchase.stripe_payment_intent_id = session.get("payment_intent")
        purchase.completed_at = datetime.utcnow()
        db.flush()

        # Add credits to user
        credits_amount = float(credits_str)

        # Check for first purchase bonus
        user = db.query(User).filter(User.id == user_id).first()
        bonus_amount = 0.0
        if user and user.first_purchase_bonus_claimed != "true":
            bonus_amount = credits_amount * FIRST_PURCHASE_BONUS_PERCENT
            user.first_purchase_bonus_claimed = "true"
            db.flush()
            logger.info(f"First purchase bonus: {bonus_amount} credits for user {user_id}")

        total_credits = credits_amount + bonus_amount

        add_credits(
            db=db,
            user_id=user_id,
            amount=total_credits,
            tx_type="purchase",
            description=f"Purchased {credits_amount} credits" + (f" + {bonus_amount:.2f} first purchase bonus" if bonus_amount > 0 else "") + f" (Stripe session {checkout_session_id})",
        )

        # Check and reward referrer if applicable
        if reward_referrer(db, user_id):
            logger.info(f"Referral reward granted for referring user {user_id}")

        logger.info(f"Webhook: fulfilled {total_credits} credits for user {user_id}")
        return {"status": "fulfilled"}

    # Other event types — acknowledge but ignore
    return {"status": "ignored"}
