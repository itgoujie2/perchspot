"""
UserSimilarHome SQLAlchemy model - stores similar homes extracted during property analysis
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Boolean, Numeric, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class UserSimilarHome(Base):
    """Similar homes found during property analysis - for recommendations"""
    __tablename__ = "user_similar_homes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    source_address = Column(Text, nullable=False)  # Property they analyzed
    similar_address = Column(Text, nullable=False)  # Similar home found
    price = Column(Numeric(12, 2))
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(3, 1))
    sqft = Column(Integer)
    property_type = Column(String(50))
    redfin_url = Column(Text)
    shown_to_user = Column(Boolean, default=False)  # Track if already recommended
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index('idx_similar_homes_user', 'user_id', 'shown_to_user'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )
