"""
Referral SQLAlchemy model
"""
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class Referral(Base):
    """Referral tracking model"""
    __tablename__ = "referrals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    referrer_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    referred_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    referral_code = Column(String(20), unique=True, nullable=False)
    status = Column(String(20), default='pending')  # pending, registered, rewarded
    reward_amount = Column(Numeric(10, 4), default=1.00)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    registered_at = Column(DateTime(timezone=True), nullable=True)
    rewarded_at = Column(DateTime(timezone=True), nullable=True)

    referrer = relationship("User", foreign_keys=[referrer_id])
    referred = relationship("User", foreign_keys=[referred_id])

    __table_args__ = (
        Index('idx_referrals_code', 'referral_code'),
        Index('idx_referrals_referrer', 'referrer_id'),
        Index('idx_referrals_referred', 'referred_id'),
    )
