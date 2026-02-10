"""
SQLAlchemy database models
"""
from sqlalchemy import Column, String, Integer, Numeric, Text, DateTime, ForeignKey, Boolean, TIMESTAMP, UniqueConstraint, Index
from app.models.user import User  # Import for relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database.connection import Base


class Property(Base):
    """Property model"""
    __tablename__ = "properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    address = Column(Text, nullable=False)
    address_normalized = Column(Text, nullable=False, unique=True)
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))

    # Property details
    price = Column(Numeric(12, 2))
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(3, 1))
    square_feet = Column(Integer)
    lot_size = Column(Integer)
    year_built = Column(Integer)
    property_type = Column(String(50))
    description = Column(Text)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    data_sources = relationship("PropertyDataSource", back_populates="property", cascade="all, delete-orphan")
    images = relationship("PropertyImage", back_populates="property", cascade="all, delete-orphan")
    analyses = relationship("PropertyAnalysis", back_populates="property", cascade="all, delete-orphan")
    schools = relationship("PropertySchool", back_populates="property", cascade="all, delete-orphan")
    comparables = relationship("ComparableProperty", back_populates="property", cascade="all, delete-orphan")
    jobs = relationship("AnalysisJob", back_populates="property", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_properties_location', 'latitude', 'longitude'),
        Index('idx_properties_zip', 'zip_code'),
        Index('idx_properties_created', 'created_at'),
    )


class PropertyDataSource(Base):
    """Property data from external sources"""
    __tablename__ = "property_data_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.id', ondelete='CASCADE'), nullable=False)
    source = Column(String(50), nullable=False)
    data = Column(JSONB, nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    property = relationship("Property", back_populates="data_sources")

    # Constraints
    __table_args__ = (
        UniqueConstraint('property_id', 'source', name='uix_property_source'),
        Index('idx_property_sources', 'property_id', 'source'),
    )


class PropertyImage(Base):
    """Property images"""
    __tablename__ = "property_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.id', ondelete='CASCADE'), nullable=False)
    image_url = Column(Text)
    storage_path = Column(Text)
    image_type = Column(String(50))
    caption = Column(Text)
    width = Column(Integer)
    height = Column(Integer)
    file_size = Column(Integer)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    property = relationship("Property", back_populates="images")

    # Indexes
    __table_args__ = (
        Index('idx_property_images', 'property_id'),
        Index('idx_image_type', 'image_type'),
    )


class School(Base):
    """School model"""
    __tablename__ = "schools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(2))
    zip_code = Column(String(10))
    latitude = Column(Numeric(10, 8))
    longitude = Column(Numeric(11, 8))
    school_type = Column(String(50))
    rating = Column(Numeric(3, 1))
    data = Column(JSONB)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    properties = relationship("PropertySchool", back_populates="school", cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('name', 'address', name='uix_school_name_address'),
        Index('idx_schools_location', 'latitude', 'longitude'),
        Index('idx_schools_type', 'school_type'),
        Index('idx_schools_rating', 'rating'),
    )


class PropertySchool(Base):
    """Property-School relationship"""
    __tablename__ = "property_schools"

    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.id', ondelete='CASCADE'), primary_key=True)
    school_id = Column(UUID(as_uuid=True), ForeignKey('schools.id', ondelete='CASCADE'), primary_key=True)
    distance_miles = Column(Numeric(5, 2))

    # Relationships
    property = relationship("Property", back_populates="schools")
    school = relationship("School", back_populates="properties")

    # Indexes
    __table_args__ = (
        Index('idx_property_schools_distance', 'distance_miles'),
    )


class PropertyAnalysis(Base):
    """Property analysis results"""
    __tablename__ = "property_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.id', ondelete='CASCADE'), nullable=False)

    # Overall scores
    overall_score = Column(Numeric(5, 2), nullable=False)
    overall_grade = Column(String(2), nullable=False)
    confidence_level = Column(String(20), nullable=False)

    # Category scores
    property_condition_score = Column(Numeric(5, 2))
    location_quality_score = Column(Numeric(5, 2))
    schools_score = Column(Numeric(5, 2))
    investment_value_score = Column(Numeric(5, 2))

    # Detailed analysis (JSON)
    condition_analysis = Column(JSONB)
    location_analysis = Column(JSONB)
    school_analysis = Column(JSONB)
    investment_analysis = Column(JSONB)

    # Metadata
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    llm_model = Column(String(50))
    llm_cost = Column(Numeric(10, 4))
    processing_time_seconds = Column(Integer)

    # Relationships
    property = relationship("Property", back_populates="analyses")
    report = relationship("AnalysisReport", back_populates="analysis", uselist=False, cascade="all, delete-orphan")

    # Constraints
    __table_args__ = (
        UniqueConstraint('property_id', 'analyzed_at', name='uix_property_analyzed'),
        Index('idx_analyses_property', 'property_id'),
        Index('idx_analyses_score', 'overall_score'),
        Index('idx_analyses_date', 'analyzed_at'),
    )


class AnalysisReport(Base):
    """Generated analysis reports"""
    __tablename__ = "analysis_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id = Column(UUID(as_uuid=True), ForeignKey('property_analyses.id', ondelete='CASCADE'), nullable=False, unique=True)
    pdf_path = Column(Text)
    html_content = Column(Text)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    analysis = relationship("PropertyAnalysis", back_populates="report")

    # Indexes
    __table_args__ = (
        Index('idx_reports_analysis', 'analysis_id'),
    )


class APIUsageLog(Base):
    """API usage tracking"""
    __tablename__ = "api_usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service = Column(String(50), nullable=False)
    endpoint = Column(String(100))
    request_params = Column(JSONB)
    tokens_used = Column(Integer)
    cost = Column(Numeric(10, 4))
    response_time_ms = Column(Integer)
    status = Column(String(20), nullable=False)
    error_message = Column(Text)
    logged_at = Column(DateTime(timezone=True), server_default=func.now())

    # Indexes
    __table_args__ = (
        Index('idx_usage_service', 'service', 'logged_at'),
        Index('idx_usage_status', 'status'),
        Index('idx_usage_date', 'logged_at'),
    )


class APICache(Base):
    """API response cache"""
    __tablename__ = "api_cache"

    cache_key = Column(String(255), primary_key=True)
    data = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Indexes
    __table_args__ = (
        Index('idx_cache_expiry', 'expires_at'),
    )


class AnalysisJob(Base):
    """Async analysis jobs tracking with comprehensive logging"""
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    property_id = Column(String(36), ForeignKey('properties.id', ondelete='CASCADE'), nullable=True)
    status = Column(String(20), nullable=False, default='pending')
    progress = Column(Integer, default=0)
    current_step = Column(String(100))
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # New logging fields
    request_id = Column(String(36), unique=True, index=True)  # Correlation ID for tracing
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # Links to User
    address = Column(String(500))  # Property address being analyzed
    address_normalized = Column(String(500), index=True)  # Normalized for dedup
    is_cached = Column(Boolean, default=False)  # True if served from cache
    total_duration_ms = Column(Integer)  # Total time in milliseconds
    total_cost = Column(Numeric(10, 6), default=0)  # Internal LLM cost
    total_cost_user = Column(Numeric(10, 6), default=0)  # User-facing cost (with margin)
    error_step = Column(String(50))  # Which step failed
    client_ip = Column(String(45))  # For anonymous users

    # Relationships
    property = relationship("Property", back_populates="jobs")
    user = relationship("User", foreign_keys=[user_id])
    step_logs = relationship("AnalysisStepLog", back_populates="analysis_job", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_jobs_status', 'status'),
        Index('idx_jobs_created', 'created_at'),
        Index('idx_jobs_property', 'property_id'),
        Index('idx_jobs_user', 'user_id'),
        Index('idx_jobs_address', 'address_normalized'),
        Index('idx_jobs_request', 'request_id'),
    )


class ComparableProperty(Base):
    """Comparable properties for investment analysis"""
    __tablename__ = "comparable_properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey('properties.id', ondelete='CASCADE'), nullable=False)
    comparable_address = Column(Text, nullable=False)
    distance_miles = Column(Numeric(5, 2))
    price = Column(Numeric(12, 2))
    square_feet = Column(Integer)
    price_per_sqft = Column(Numeric(10, 2))
    bedrooms = Column(Integer)
    bathrooms = Column(Numeric(3, 1))
    sale_date = Column(DateTime)
    data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    property = relationship("Property", back_populates="comparables")

    # Indexes
    __table_args__ = (
        Index('idx_comparables_property', 'property_id'),
        Index('idx_comparables_distance', 'distance_miles'),
    )
