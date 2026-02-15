"""
EmailCampaignLog SQLAlchemy model - logs sent email campaigns
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import JSON
import uuid

from app.database.connection import Base


class EmailCampaignLog(Base):
    """Email campaign log for tracking sent emails"""
    __tablename__ = "email_campaign_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    email_type = Column(String(50), nullable=False)  # 'weekly_digest', 'market_update'
    recipient_email = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=False)
    cities_included = Column(JSON)  # List of cities included in the email
    properties_count = Column(Integer, default=0)  # Number of properties included
    status = Column(String(20), nullable=False, default='pending')  # pending, sent, failed, bounced
    ses_message_id = Column(String(100))  # AWS SES message ID for tracking
    error_message = Column(Text)  # Error details if failed
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")

    __table_args__ = (
        Index('idx_email_log_user', 'user_id'),
        Index('idx_email_log_type', 'email_type'),
        Index('idx_email_log_status', 'status'),
        Index('idx_email_log_sent', 'sent_at'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'},
    )
