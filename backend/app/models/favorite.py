"""
UserFavorite SQLAlchemy model for saved properties
"""
from sqlalchemy import Column, String, CHAR, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class UserFavorite(Base):
    """User's saved/favorited properties"""
    __tablename__ = "user_favorites"

    # Use CHAR(36) to match users table id column type
    id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(CHAR(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    address = Column(String(500), nullable=False)
    nickname = Column(String(100))
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index('idx_user_favorites_user', 'user_id'),
        Index('idx_user_favorites_created', 'user_id', 'created_at'),
    )
