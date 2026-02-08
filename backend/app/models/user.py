"""
User and CreditTransaction SQLAlchemy models
"""
from sqlalchemy import Column, String, Numeric, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class User(Base):
    """User account model"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    credit_balance = Column(Numeric(10, 4), default=0.0000)
    survey_completed = Column(String(5), default="false")  # "true" or "false" - MySQL BOOLEAN workaround
    first_purchase_bonus_claimed = Column(String(5), default="false")  # "true" or "false"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    credit_transactions = relationship("CreditTransaction", back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_users_email', 'email'),
    )


class IpUsage(Base):
    """IP-based usage tracking for free tier"""
    __tablename__ = "ip_usage"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ip_address = Column(String(45), nullable=False)
    address = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_ip_usage_ip', 'ip_address'),
    )


class Purchase(Base):
    """Stripe payment purchase record"""
    __tablename__ = "purchases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Numeric(10, 4), nullable=False)
    credits = Column(Numeric(10, 4), nullable=False)
    stripe_checkout_session_id = Column(String(255), unique=True)
    stripe_payment_intent_id = Column(String(255))
    status = Column(String(20), nullable=False, default='pending')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    user = relationship("User")

    __table_args__ = (
        Index('idx_purchases_user', 'user_id'),
        Index('idx_purchases_status', 'status'),
        Index('idx_purchases_session', 'stripe_checkout_session_id'),
    )


class CreditTransaction(Base):
    """Credit transaction audit log"""
    __tablename__ = "credit_transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount = Column(Numeric(10, 4), nullable=False)
    balance_after = Column(Numeric(10, 4), nullable=False)
    transaction_type = Column(String(50), nullable=False)  # 'analysis', 'chat', 'signup_bonus', 'topup'
    reference_id = Column(String(500))  # address for analysis, conversation_id for chat
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="credit_transactions")

    __table_args__ = (
        Index('idx_credit_tx_user', 'user_id', 'created_at'),
        Index('idx_credit_tx_type', 'transaction_type'),
        Index('idx_credit_tx_ref', 'user_id', 'transaction_type', 'reference_id'),
    )
