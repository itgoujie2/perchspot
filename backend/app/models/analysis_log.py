"""
Analysis Step Log model for tracking individual steps in property analysis.
"""
from sqlalchemy import Column, String, Integer, Numeric, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class AnalysisStepLog(Base):
    """
    Tracks each step in a property analysis job.

    Steps:
    1. Cache Check (system)
    2. Property Overview (extraction)
    3. Pricing & Estimates (extraction)
    4. Schools (extraction)
    5. Location & Lifestyle (extraction)
    6. Climate Risks (extraction)
    7. Property Condition (analysis)
    8. Location & Commute (analysis)
    9. School Quality (analysis)
    10. Investment Potential (analysis)
    """
    __tablename__ = "analysis_step_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey('analysis_jobs.id', ondelete='CASCADE'),
        nullable=False
    )
    step_number = Column(Integer, nullable=False)
    step_name = Column(String(100), nullable=False)
    step_type = Column(String(20), nullable=False)  # 'system', 'extraction', 'analysis'
    status = Column(String(20), nullable=False, default='pending')  # pending/in_progress/completed/failed/skipped
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    cost = Column(Numeric(10, 6), default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    model = Column(String(100))
    error_message = Column(Text)
    step_metadata = Column(JSONB)

    # Relationship
    analysis_job = relationship("AnalysisJob", back_populates="step_logs")

    __table_args__ = (
        Index('idx_step_logs_job', 'analysis_job_id'),
        Index('idx_step_logs_status', 'status'),
        Index('idx_step_logs_step', 'step_number'),
        {'mysql_charset': 'utf8mb4', 'mysql_collate': 'utf8mb4_unicode_ci'}
    )


# Step definitions for reference
ANALYSIS_STEPS = [
    {"number": 1, "name": "Cache Check", "type": "system"},
    {"number": 2, "name": "Property Overview", "type": "extraction"},
    {"number": 3, "name": "Pricing & Estimates", "type": "extraction"},
    {"number": 4, "name": "Schools", "type": "extraction"},
    {"number": 5, "name": "Location & Lifestyle", "type": "extraction"},
    {"number": 6, "name": "Climate Risks", "type": "extraction"},
    {"number": 7, "name": "Property Condition", "type": "analysis"},
    {"number": 8, "name": "Location & Commute", "type": "analysis"},
    {"number": 9, "name": "School Quality", "type": "analysis"},
    {"number": 10, "name": "Investment Potential", "type": "analysis"},
]
