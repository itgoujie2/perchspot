"""
Pydantic schemas for request/response validation
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, validator
from enum import Enum


# Enums
class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SchoolType(str, Enum):
    ELEMENTARY = "elementary"
    MIDDLE = "middle"
    HIGH = "high"
    PRIVATE = "private"


class ImageType(str, Enum):
    EXTERIOR = "exterior"
    INTERIOR = "interior"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    BEDROOM = "bedroom"
    LIVING_ROOM = "living_room"
    OTHER = "other"


# Request Schemas
class PropertyAnalysisRequest(BaseModel):
    """Request to analyze a property"""
    address: str = Field(..., min_length=5, max_length=200, description="Full property address")

    @validator('address')
    def validate_address(cls, v):
        """Validate address format and prevent injection"""
        if not v or not v.strip():
            raise ValueError('Address cannot be empty')

        # Remove excessive whitespace
        v = ' '.join(v.split())

        # Check for suspicious patterns
        forbidden = [';', '--', '/*', '*/', 'DROP', 'DELETE', 'INSERT', 'UPDATE']
        if any(f in v.upper() for f in forbidden):
            raise ValueError('Invalid characters in address')

        return v


# Response Schemas
class PropertyAnalysisResponse(BaseModel):
    """Initial response when analysis is requested"""
    analysis_id: str
    status: AnalysisStatus
    message: str


class AnalysisStatusResponse(BaseModel):
    """Response for analysis status polling"""
    analysis_id: str
    status: AnalysisStatus
    progress: int = Field(ge=0, le=100)
    current_step: Optional[str] = None
    estimated_time_remaining: Optional[int] = None  # seconds
    error_message: Optional[str] = None


# Property Data Schemas
class PropertyData(BaseModel):
    """Basic property information"""
    id: Optional[str] = None
    address: str
    address_normalized: str
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    price: Optional[Decimal] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    square_feet: Optional[int] = None
    lot_size: Optional[int] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = None
    description: Optional[str] = None


class PropertyImage(BaseModel):
    """Property image information"""
    id: str
    image_url: Optional[str] = None
    storage_path: Optional[str] = None
    image_type: ImageType
    caption: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class SchoolData(BaseModel):
    """School information"""
    id: Optional[str] = None
    name: str
    address: Optional[str] = None
    school_type: SchoolType
    rating: Optional[Decimal] = Field(None, ge=0, le=10)
    distance_miles: Optional[Decimal] = None
    data: Optional[Dict[str, Any]] = None


# Analysis Result Schemas
class SubScores(BaseModel):
    """Sub-category scores"""
    exterior: Optional[Decimal] = Field(None, ge=0, le=100)
    interior: Optional[Decimal] = Field(None, ge=0, le=100)
    kitchen_bath: Optional[Decimal] = Field(None, ge=0, le=100)
    systems: Optional[Decimal] = Field(None, ge=0, le=100)


class PropertyConditionAnalysis(BaseModel):
    """Property condition analysis results"""
    score: Decimal = Field(..., ge=0, le=100)
    sub_scores: Optional[SubScores] = None
    reasoning: str
    highlights: List[str] = []
    concerns: List[str] = []
    confidence: ConfidenceLevel


class LocationQualityAnalysis(BaseModel):
    """Location quality analysis results"""
    score: Decimal = Field(..., ge=0, le=100)
    neighborhood_score: Optional[Decimal] = Field(None, ge=0, le=100)
    amenities_score: Optional[Decimal] = Field(None, ge=0, le=100)
    transit_score: Optional[Decimal] = Field(None, ge=0, le=100)
    walkability_score: Optional[Decimal] = Field(None, ge=0, le=100)
    reasoning: str
    nearby_amenities: List[str] = []
    transit_options: List[str] = []
    confidence: ConfidenceLevel


class SchoolAnalysis(BaseModel):
    """School analysis results"""
    score: Decimal = Field(..., ge=0, le=100)
    schools: List[SchoolData] = []
    reasoning: str
    highlights: List[str] = []
    concerns: List[str] = []
    confidence: ConfidenceLevel


class InvestmentValueAnalysis(BaseModel):
    """Investment value analysis results"""
    score: Decimal = Field(..., ge=0, le=100)
    price_vs_market: Optional[Decimal] = None  # percentage above/below market
    appreciation_potential: Optional[str] = None
    rental_yield_estimate: Optional[Decimal] = None
    market_trends: Optional[str] = None
    reasoning: str
    recommendations: List[str] = []
    confidence: ConfidenceLevel


class CategoryScores(BaseModel):
    """All category scores"""
    property_condition: Decimal = Field(..., ge=0, le=100)
    location_quality: Decimal = Field(..., ge=0, le=100)
    schools: Decimal = Field(..., ge=0, le=100)
    investment_value: Decimal = Field(..., ge=0, le=100)


class DetailedAnalysis(BaseModel):
    """All detailed analysis results"""
    property_condition: PropertyConditionAnalysis
    location_quality: LocationQualityAnalysis
    schools: SchoolAnalysis
    investment_value: InvestmentValueAnalysis


class AnalysisReportResponse(BaseModel):
    """Complete analysis report"""
    analysis_id: str
    overall_score: Decimal = Field(..., ge=0, le=100)
    overall_grade: str = Field(..., pattern="^[A-F]$")
    confidence: ConfidenceLevel
    category_scores: CategoryScores
    detailed_analysis: DetailedAnalysis
    property_data: PropertyData
    images: List[PropertyImage] = []
    analyzed_at: datetime
    llm_model: Optional[str] = None
    processing_time_seconds: Optional[int] = None


# Database Model Schemas (for ORM)
class PropertyBase(BaseModel):
    """Base property schema"""
    address: str
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    price: Optional[Decimal] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[Decimal] = None
    square_feet: Optional[int] = None


class PropertyCreate(PropertyBase):
    """Schema for creating a property"""
    address_normalized: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = None
    description: Optional[str] = None


class Property(PropertyBase):
    """Schema for property from database"""
    id: str
    address_normalized: str
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Analysis Schemas
class AnalysisCreate(BaseModel):
    """Schema for creating an analysis"""
    property_id: str
    overall_score: Decimal
    overall_grade: str
    confidence_level: ConfidenceLevel
    property_condition_score: Decimal
    location_quality_score: Decimal
    schools_score: Decimal
    investment_value_score: Decimal
    condition_analysis: Dict[str, Any]
    location_analysis: Dict[str, Any]
    school_analysis: Dict[str, Any]
    investment_analysis: Dict[str, Any]
    llm_model: str
    llm_cost: Optional[Decimal] = None
    processing_time_seconds: Optional[int] = None


class Analysis(AnalysisCreate):
    """Schema for analysis from database"""
    id: str
    analyzed_at: datetime

    class Config:
        from_attributes = True


# Health Check Schema
class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    services: Dict[str, str]  # service_name: status


# Error Response Schema
class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
