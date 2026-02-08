"""
History API endpoints - view past property analyses
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database.connection import get_db
from app.models.user import User, CreditTransaction
from app.api.v1.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class HistoryItemResponse(BaseModel):
    id: str
    address: str
    analyzed_at: str
    cost: float

    class Config:
        from_attributes = True


class HistoryListResponse(BaseModel):
    items: List[HistoryItemResponse]
    total: int


@router.get("", response_model=HistoryListResponse)
def list_history(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List past property analyses for the current user.
    Queries credit_transactions where type='analysis' to find analyzed properties.
    """
    # Query analysis transactions for this user
    query = (
        db.query(CreditTransaction)
        .filter(
            CreditTransaction.user_id == user.id,
            CreditTransaction.transaction_type == "analysis"
        )
        .order_by(desc(CreditTransaction.created_at))
    )

    total = query.count()
    transactions = query.offset(offset).limit(limit).all()

    items = []
    for tx in transactions:
        # reference_id contains the address for analysis transactions
        if tx.reference_id:
            items.append(
                HistoryItemResponse(
                    id=tx.id,
                    address=tx.reference_id,
                    analyzed_at=tx.created_at.isoformat() if tx.created_at else "",
                    cost=abs(float(tx.amount)),
                )
            )

    return HistoryListResponse(items=items, total=total)
