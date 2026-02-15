"""
EmailPreference SQLAlchemy model - stores user email preferences
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import secrets

from app.database.connection import Base


class EmailPreference(Base):
    """User email preference settings"""
    __tablename__ = "email_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    weekly_digest = Column(Boolean, default=True)  # Weekly property digest emails
    market_updates = Column(Boolean, default=True)  # Market trend updates
    promotional = Column(Boolean, default=False)  # Promotional emails (default opt-out)
    unsubscribe_token = Column(String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(48))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")

    __table_args__ = (
        Index('idx_email_pref_user', 'user_id'),
        Index('idx_email_pref_token', 'unsubscribe_token'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )
