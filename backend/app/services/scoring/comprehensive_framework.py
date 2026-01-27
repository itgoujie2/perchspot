"""
Comprehensive Housing Analysis Framework
Based on the semantic model with 8 major categories
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class ScoreWeights(BaseModel):
    """Scoring weights for different buyer types"""
    family: float
    investor: float
    retiree: float


class Category(BaseModel):
    """Analysis category definition"""
    id: str
    name: str
    description: str
    weights: ScoreWeights
    sub_areas: List[str]


# Define the 8 major categories
CATEGORIES = {
    "physical_quality": Category(
        id="physical_quality",
        name="Physical Quality",
        description="Structure, materials, condition, and specifications",
        weights=ScoreWeights(family=0.15, investor=0.15, retiree=0.20),
        sub_areas=[
            "Basic Specifications",
            "Structural Components",
            "Material Quality",
            "Mechanical Systems",
            "Condition Assessment"
        ]
    ),
    "location_accessibility": Category(
        id="location_accessibility",
        name="Location & Accessibility",
        description="Commute, transportation, and connectivity",
        weights=ScoreWeights(family=0.15, investor=0.10, retiree=0.10),
        sub_areas=[
            "Commute Analysis",
            "Highway Access",
            "Highway Proximity Issues",
            "Daily Essentials",
            "Transportation Infrastructure"
        ]
    ),
    "education": Category(
        id="education",
        name="Education",
        description="School quality and educational resources",
        weights=ScoreWeights(family=0.20, investor=0.10, retiree=0.00),
        sub_areas=[
            "Elementary School",
            "Middle School",
            "High School",
            "Private/Charter Options",
            "Higher Education"
        ]
    ),
    "neighborhood_environment": Category(
        id="neighborhood_environment",
        name="Neighborhood & Environment",
        description="Safety, noise, air quality, and community",
        weights=ScoreWeights(family=0.15, investor=0.10, retiree=0.20),
        sub_areas=[
            "Safety & Crime",
            "Noise Pollution",
            "Air Quality",
            "Walkability & Livability",
            "Community Character"
        ]
    ),
    "lot_land": Category(
        id="lot_land",
        name="Lot & Land Characteristics",
        description="Size, topography, orientation, and natural features",
        weights=ScoreWeights(family=0.10, investor=0.05, retiree=0.15),
        sub_areas=[
            "Size & Shape",
            "Topography",
            "Sun Exposure",
            "Views & Privacy",
            "Natural Features"
        ]
    ),
    "natural_hazards": Category(
        id="natural_hazards",
        name="Natural Hazards & Risk",
        description="Flood, earthquake, wildfire, and climate risks",
        weights=ScoreWeights(family=0.10, investor=0.10, retiree=0.15),
        sub_areas=[
            "Flood Risk",
            "Earthquake Risk",
            "Wildfire Risk",
            "Climate Risks",
            "Other Hazards"
        ]
    ),
    "financial_investment": Category(
        id="financial_investment",
        name="Financial & Investment",
        description="Value metrics, rental potential, and appreciation",
        weights=ScoreWeights(family=0.10, investor=0.35, retiree=0.10),
        sub_areas=[
            "Current Valuation",
            "Rental Analysis",
            "Cash Flow Metrics",
            "Appreciation Potential",
            "Carrying Costs"
        ]
    ),
    "legal_regulatory": Category(
        id="legal_regulatory",
        name="Legal & Regulatory",
        description="Zoning, HOA, permits, and restrictions",
        weights=ScoreWeights(family=0.05, investor=0.05, retiree=0.10),
        sub_areas=[
            "Zoning & Land Use",
            "Permits & History",
            "HOA/Community",
            "Title & Easements",
            "Environmental/Disclosure"
        ]
    )
}


class SubAreaScore(BaseModel):
    """Score for a specific sub-area"""
    name: str
    score: float  # 1-10
    rating: str  # Poor, Below Average, Average, Good, Excellent
    findings: List[str]
    data_sources: List[str]
    confidence: str  # High, Medium, Low


class CategoryScore(BaseModel):
    """Score for a major category"""
    category_id: str
    category_name: str
    overall_score: float  # 1-10
    overall_rating: str
    sub_area_scores: List[SubAreaScore]
    key_strengths: List[str]
    key_concerns: List[str]
    data_completeness: float  # 0-100%


class ComprehensiveAnalysis(BaseModel):
    """Complete property analysis result"""
    address: str
    analysis_date: str
    buyer_type: str  # family, investor, retiree

    # Category scores
    category_scores: Dict[str, CategoryScore]

    # Overall scores (weighted by buyer type)
    overall_score: float  # 1-10
    overall_rating: str

    # Summary
    executive_summary: str
    top_strengths: List[str]
    top_concerns: List[str]
    recommendation: str

    # Metadata
    data_sources_used: List[str]
    analysis_completeness: float
    confidence_level: str


def get_rating_from_score(score: float) -> str:
    """Convert numeric score to rating"""
    if score >= 9:
        return "Excellent"
    elif score >= 7:
        return "Good"
    elif score >= 5:
        return "Average"
    elif score >= 3:
        return "Below Average"
    else:
        return "Poor"


def calculate_weighted_score(category_scores: Dict[str, CategoryScore], buyer_type: str) -> float:
    """Calculate overall weighted score based on buyer type"""
    total_score = 0.0
    total_weight = 0.0

    for category_id, category_score in category_scores.items():
        if category_id not in CATEGORIES:
            continue

        category = CATEGORIES[category_id]
        weight = getattr(category.weights, buyer_type, 0.0)

        total_score += category_score.overall_score * weight
        total_weight += weight

    if total_weight == 0:
        return 0.0

    return total_score / total_weight


# Data source mappings
DATA_SOURCES = {
    # Free public sources
    "greatschools": "GreatSchools.org",
    "walkscore": "Walk Score",
    "fema_flood": "FEMA Flood Map Service",
    "fema_risk": "FEMA National Risk Index",
    "first_street": "First Street Foundation",
    "epa_air": "EPA AirNow",
    "fbi_crime": "FBI Crime Data Explorer",
    "hud_noise": "HUD DNL Calculator",
    "usgs": "USGS",

    # Real estate platforms
    "zillow": "Zillow",
    "redfin": "Redfin",
    "rentometer": "Rentometer",

    # APIs
    "google_maps": "Google Maps API",
    "google_places": "Google Places API",

    # Professional services
    "home_inspection": "Home Inspection Report",
    "nhd_report": "Natural Hazard Disclosure",
    "title_company": "Title Company Records"
}
