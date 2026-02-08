"""
Promo Code service - Admin promo link generation and redemption
"""
import logging
import secrets
import string
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy.orm import Session

from app.models.promo_code import PromoCode
from app.services.auth.credit_service import add_credits

logger = logging.getLogger(__name__)


def generate_promo_code() -> str:
    """Generate a unique 8-character alphanumeric promo code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))


def create_promo_code(
    db: Session,
    credit_amount: float,
    max_uses: Optional[int] = 1,
    note: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> PromoCode:
    """Create a new promo code with specified credit amount."""
    # Generate unique code
    for _ in range(10):
        code = generate_promo_code()
        if not db.query(PromoCode).filter(PromoCode.code == code).first():
            break
    else:
        raise RuntimeError("Failed to generate unique promo code")

    promo = PromoCode(
        code=code,
        credit_amount=Decimal(str(credit_amount)),
        max_uses=max_uses,
        note=note,
        expires_at=expires_at,
    )
    db.add(promo)
    db.commit()
    db.refresh(promo)

    logger.info(f"Created promo code {code} with ${credit_amount} credit, max_uses={max_uses}")
    return promo


def get_promo_by_code(db: Session, code: str) -> Optional[PromoCode]:
    """Find a promo code by its code string."""
    return db.query(PromoCode).filter(PromoCode.code == code.upper()).first()


def validate_promo_code(db: Session, code: str) -> tuple[bool, str, Optional[PromoCode]]:
    """
    Validate a promo code for use.
    Returns (is_valid, error_message, promo_code)
    """
    promo = get_promo_by_code(db, code)

    if not promo:
        return False, "Invalid promo code", None

    if not promo.is_active:
        return False, "Promo code is no longer active", None

    if promo.expires_at and promo.expires_at < datetime.utcnow():
        return False, "Promo code has expired", None

    if promo.max_uses is not None and promo.uses_count >= promo.max_uses:
        return False, "Promo code has reached maximum uses", None

    return True, "", promo


def redeem_promo_code(db: Session, code: str, user_id: str) -> tuple[bool, str, float]:
    """
    Redeem a promo code for a user (called during registration).
    Returns (success, message, credit_amount)
    """
    is_valid, error_msg, promo = validate_promo_code(db, code)

    if not is_valid:
        return False, error_msg, 0.0

    # Add credits to user
    credit_amount = float(promo.credit_amount)
    add_credits(
        db=db,
        user_id=user_id,
        amount=credit_amount,
        tx_type="promo_code",
        description=f"Promo code: {promo.code}",
    )

    # Update usage count
    promo.uses_count += 1
    db.commit()

    logger.info(f"Redeemed promo code {code} for user {user_id}, ${credit_amount} credited")
    return True, f"${credit_amount:.2f} credit applied!", credit_amount


def list_promo_codes(db: Session, include_inactive: bool = False) -> List[PromoCode]:
    """List all promo codes."""
    query = db.query(PromoCode)
    if not include_inactive:
        query = query.filter(PromoCode.is_active == True)
    return query.order_by(PromoCode.created_at.desc()).all()


def deactivate_promo_code(db: Session, code: str) -> bool:
    """Deactivate a promo code."""
    promo = get_promo_by_code(db, code)
    if not promo:
        return False
    promo.is_active = False
    db.commit()
    logger.info(f"Deactivated promo code {code}")
    return True
