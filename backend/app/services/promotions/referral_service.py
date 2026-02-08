"""
Referral program service - code generation, tracking, and rewards
"""
import logging
import secrets
import string
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models.referral import Referral
from app.models.user import User
from app.services.auth.credit_service import add_credits

logger = logging.getLogger(__name__)

REFERRAL_REWARD_AMOUNT = Decimal("1.00")


def generate_referral_code() -> str:
    """Generate a unique 8-character alphanumeric referral code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))


def get_or_create_referral_code(db: Session, user_id: str) -> str:
    """Get existing referral code or create a new one for the user."""
    # Check if user already has a referral code
    existing = db.query(Referral).filter(
        Referral.referrer_id == user_id,
        Referral.referred_id.is_(None),  # A "template" referral for this user
        Referral.status == 'pending'
    ).first()

    if existing:
        return existing.referral_code

    # Generate a unique code
    for _ in range(10):  # Try up to 10 times to avoid collision
        code = generate_referral_code()
        if not db.query(Referral).filter(Referral.referral_code == code).first():
            break
    else:
        raise RuntimeError("Failed to generate unique referral code")

    # Create the referral template
    referral = Referral(
        referrer_id=user_id,
        referral_code=code,
        status='pending',
    )
    db.add(referral)
    db.commit()
    db.refresh(referral)

    logger.info(f"Created referral code {code} for user {user_id}")
    return code


def get_referral_by_code(db: Session, code: str) -> Optional[Referral]:
    """Find a referral by its code."""
    return db.query(Referral).filter(Referral.referral_code == code).first()


def register_referral(db: Session, referral_code: str, referred_user_id: str) -> bool:
    """
    Register a new user as having been referred.
    Returns True if successful, False if code invalid or already used.
    """
    referral = get_referral_by_code(db, referral_code)

    if not referral:
        logger.warning(f"Invalid referral code: {referral_code}")
        return False

    if referral.status != 'pending':
        logger.warning(f"Referral code {referral_code} already used (status: {referral.status})")
        return False

    if referral.referrer_id == referred_user_id:
        logger.warning(f"User {referred_user_id} tried to use their own referral code")
        return False

    # Update the referral
    referral.referred_id = referred_user_id
    referral.status = 'registered'
    referral.registered_at = datetime.utcnow()
    db.commit()

    # Create a new pending referral for the referrer so they can share again
    new_code = generate_referral_code()
    for _ in range(10):
        if not db.query(Referral).filter(Referral.referral_code == new_code).first():
            break
        new_code = generate_referral_code()

    new_referral = Referral(
        referrer_id=referral.referrer_id,
        referral_code=new_code,
        status='pending',
    )
    db.add(new_referral)
    db.commit()

    logger.info(f"Registered referral: {referral_code} -> user {referred_user_id}")
    return True


def reward_referrer(db: Session, referred_user_id: str) -> bool:
    """
    Grant reward to referrer when referred user makes a purchase.
    Returns True if reward granted, False if no pending referral or already rewarded.
    """
    # Find the referral for this referred user that's in 'registered' status
    referral = db.query(Referral).filter(
        Referral.referred_id == referred_user_id,
        Referral.status == 'registered'
    ).first()

    if not referral:
        logger.debug(f"No registered referral found for user {referred_user_id}")
        return False

    # Grant reward to referrer
    add_credits(
        db=db,
        user_id=referral.referrer_id,
        amount=float(REFERRAL_REWARD_AMOUNT),
        tx_type="referral_reward",
        description=f"Referral reward for user {referred_user_id[:8]}...",
    )

    # Update referral status
    referral.status = 'rewarded'
    referral.rewarded_at = datetime.utcnow()
    db.commit()

    logger.info(f"Granted ${REFERRAL_REWARD_AMOUNT} referral reward to user {referral.referrer_id}")
    return True


def get_referral_stats(db: Session, user_id: str) -> dict:
    """Get referral statistics for a user."""
    # Count referrals by status
    registered_count = db.query(Referral).filter(
        Referral.referrer_id == user_id,
        Referral.status == 'registered'
    ).count()

    rewarded_count = db.query(Referral).filter(
        Referral.referrer_id == user_id,
        Referral.status == 'rewarded'
    ).count()

    total_earned = rewarded_count * float(REFERRAL_REWARD_AMOUNT)

    return {
        "pending_rewards": registered_count,  # Friends signed up but haven't purchased
        "completed_referrals": rewarded_count,
        "total_earned": total_earned,
    }
