"""
Promo Code SQLAlchemy model - Admin-generated promotional links
"""
from sqlalchemy import Column, String, Numeric, DateTime, Integer, Boolean
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class PromoCode(Base):
    """Admin-generated promo codes with custom credit amounts"""
    __tablename__ = "promo_codes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(20), unique=True, nullable=False, index=True)
    credit_amount = Column(Numeric(10, 2), nullable=False)  # Credits to give on registration
    max_uses = Column(Integer, nullable=True)  # None = unlimited
    uses_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    note = Column(String(255), nullable=True)  # Optional note (e.g., "For John")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
