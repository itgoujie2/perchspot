"""
Credit service - balance management, deduction, per-user billing checks
"""
import logging
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.user import User, CreditTransaction

logger = logging.getLogger(__name__)


def check_balance(db: Session, user_id: str) -> Decimal:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return Decimal("0")
    return Decimal(str(user.credit_balance))


def deduct_credits(
    db: Session,
    user_id: str,
    amount: float,
    tx_type: str,
    ref_id: str = None,
    description: str = None,
) -> bool:
    """
    Atomically deduct credits from user. Returns True if successful, False if insufficient balance.
    """
    cost = Decimal(str(amount))
    if cost <= 0:
        return True

    # Atomic update: only succeeds if balance >= cost
    result = db.execute(
        text(
            "UPDATE users SET credit_balance = credit_balance - :cost "
            "WHERE id = :uid AND credit_balance >= :cost"
        ),
        {"cost": float(cost), "uid": user_id},
    )

    if result.rowcount == 0:
        db.rollback()
        return False

    # Fetch updated balance for audit log
    db.flush()
    user = db.query(User).filter(User.id == user_id).first()
    balance_after = Decimal(str(user.credit_balance))

    tx = CreditTransaction(
        user_id=user_id,
        amount=-cost,
        balance_after=balance_after,
        transaction_type=tx_type,
        reference_id=ref_id,
        description=description,
    )
    db.add(tx)
    db.commit()
    db.refresh(user)

    logger.info(f"Deducted ${cost} from user {user_id} ({tx_type}). Balance: ${balance_after}")
    return True


def has_user_paid_for_analysis(db: Session, user_id: str, address: str) -> bool:
    """Check if this user has already paid for an analysis of this address."""
    tx = (
        db.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == user_id,
            CreditTransaction.transaction_type == "analysis",
            CreditTransaction.reference_id == address,
        )
        .first()
    )
    return tx is not None


def add_credits(
    db: Session,
    user_id: str,
    amount: float,
    tx_type: str,
    description: str = None,
) -> Decimal:
    """Add credits to user account. Returns new balance."""
    credit = Decimal(str(amount))

    db.execute(
        text("UPDATE users SET credit_balance = credit_balance + :amount WHERE id = :uid"),
        {"amount": float(credit), "uid": user_id},
    )
    db.flush()

    user = db.query(User).filter(User.id == user_id).first()
    balance_after = Decimal(str(user.credit_balance))

    tx = CreditTransaction(
        user_id=user_id,
        amount=credit,
        balance_after=balance_after,
        transaction_type=tx_type,
        description=description,
    )
    db.add(tx)
    db.commit()
    db.refresh(user)

    logger.info(f"Added ${credit} to user {user_id} ({tx_type}). Balance: ${balance_after}")
    return balance_after
