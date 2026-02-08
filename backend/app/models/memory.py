"""
UserMemory and UserCityActivity SQLAlchemy models
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class UserMemory(Base):
    """User memory/preference model - stores extracted info from conversations"""
    __tablename__ = "user_memories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    category = Column(String(50), nullable=False)  # budget, property_preference, intent, family_situation, lifestyle
    memory_key = Column(String(100), nullable=False)  # max_price, property_type, has_children, etc.
    memory_value = Column(Text, nullable=False)
    confidence = Column(String(20), default='medium')  # high, medium, low
    source = Column(String(50), nullable=False)  # chat, analysis, explicit
    source_context = Column(Text)  # The context that triggered the save
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User")

    __table_args__ = (
        Index('idx_user_memories_user', 'user_id'),
        Index('idx_user_memories_category', 'user_id', 'category'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )


class UserCityActivity(Base):
    """City activity tracking - auto-captured from property analyses"""
    __tablename__ = "user_city_activity"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(2), nullable=False)
    region = Column(String(100))
    activity_count = Column(Integer, default=1)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index('idx_user_city_activity_user', 'user_id'),
        Index('idx_user_city_activity_last', 'user_id', 'last_activity'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )
