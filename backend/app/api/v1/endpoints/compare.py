"""
Compare API endpoint - side-by-side property comparison

Uses cached analysis data from notes. Properties must be analyzed first before comparison.
"""
import logging
import json
import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.user import User
from app.api.v1.deps import get_optional_user
from app.services.agent.tools.notes_manager import get_notes_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class CompareRequest(BaseModel):
    addresses: List[str]  # 2-3 addresses to compare


class PropertyScores(BaseModel):
    property: Optional[int] = None
    location: Optional[int] = None
    schools: Optional[int] = None
    investment: Optional[int] = None
    overall: Optional[int] = None


class PropertySummary(BaseModel):
    address: str
    price: Optional[str] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    sqft: Optional[int] = None
    year_built: Optional[int] = None
    scores: PropertyScores
    strengths: List[str] = []
    concerns: List[str] = []
    cached: bool = True
    needs_analysis: bool = False


class CompareResponse(BaseModel):
    properties: List[PropertySummary]
    comparison_notes: Optional[str] = None


def get_cached_data(address: str, notes_manager) -> Optional[dict]:
    """Get cached extraction data from notes"""
    if not notes_manager.notes_exist(address):
        return None

    notes_content = notes_manager.read_notes(address)
    if not notes_content:
        return None

    # Extract "Extraction Complete" section
    sections = re.findall(
        r'## Extraction Complete\n(.*?)(?=\n## |\Z)',
        notes_content,
        re.DOTALL
    )
    if not sections:
        return None

    for section_content in reversed(sections):
        # Try fenced JSON
        fenced = re.search(r'```json\s*\n(.+?)\n```', section_content, re.DOTALL)
        if fenced:
            try:
                cached_data = json.loads(fenced.group(1))
                if "property" in cached_data:
                    return cached_data
            except json.JSONDecodeError:
                pass

        # Try raw JSON
        raw = re.search(r'(\{.+\})', section_content, re.DOTALL)
        if raw:
            try:
                cached_data = json.loads(raw.group(1))
                if "property" in cached_data:
                    return cached_data
            except json.JSONDecodeError:
                pass

    return None


def get_cached_analysis(address: str, notes_manager) -> Optional[dict]:
    """Get cached analysis results from notes"""
    if not notes_manager.notes_exist(address):
        return None

    notes_content = notes_manager.read_notes(address)
    if not notes_content:
        return None

    section_map = {
        "Property Analysis": "property",
        "Location Analysis": "location",
        "School Analysis": "schools",
        "Investment Analysis": "investment",
    }

    cached_analysis = {}

    for section_title, key in section_map.items():
        pattern = rf'## {re.escape(section_title)}\n(.*?)(?=\n## |\Z)'
        matches = re.findall(pattern, notes_content, re.DOTALL)
        if not matches:
            continue

        section_content = matches[-1]
        fenced = re.search(r'```json\s*\n(.+?)\n```', section_content, re.DOTALL)
        if fenced:
            try:
                cached_analysis[key] = json.loads(fenced.group(1))
            except json.JSONDecodeError:
                pass

    return cached_analysis if cached_analysis else None


def extract_property_summary(extracted_data: dict, analysis_results: dict, address: str) -> PropertySummary:
    """Extract a summary from cached analysis data"""
    property_data = extracted_data.get("property", {}) or extracted_data.get("details", {}) or {}
    pricing_data = extracted_data.get("pricing", {}) or {}

    # Extract scores
    prop_score = analysis_results.get("property", {}).get("score")
    loc_score = analysis_results.get("location", {}).get("score")
    school_score = analysis_results.get("schools", {}).get("score")
    invest_score = analysis_results.get("investment", {}).get("score")

    scores = [s for s in [prop_score, loc_score, school_score, invest_score] if s is not None]
    overall = round(sum(scores) / len(scores)) if scores else None

    # Collect strengths and concerns from all analyses
    all_strengths = []
    all_concerns = []
    for key in ["property", "location", "schools", "investment"]:
        result = analysis_results.get(key, {})
        if result.get("strengths"):
            all_strengths.extend(result["strengths"][:2])
        if result.get("concerns"):
            all_concerns.extend(result["concerns"][:2])

    # Get price and convert to string if needed
    raw_price = pricing_data.get("list_price") or property_data.get("price") or property_data.get("list_price")
    price_str = None
    if raw_price is not None:
        if isinstance(raw_price, (int, float)):
            price_str = f"${raw_price:,.0f}"
        else:
            price_str = str(raw_price)

    return PropertySummary(
        address=address,
        price=price_str,
        beds=property_data.get("bedrooms") or property_data.get("beds"),
        baths=property_data.get("bathrooms") or property_data.get("baths"),
        sqft=property_data.get("living_area_sqft") or property_data.get("sqft"),
        year_built=property_data.get("year_built"),
        scores=PropertyScores(
            property=prop_score,
            location=loc_score,
            schools=school_score,
            investment=invest_score,
            overall=overall,
        ),
        strengths=all_strengths[:5],
        concerns=all_concerns[:5],
        cached=True,
        needs_analysis=False,
    )


@router.post("", response_model=CompareResponse)
async def compare_properties(
    req: CompareRequest,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Compare 2-3 properties side by side using cached analysis data.

    Properties must be analyzed first before they can be compared.
    Returns scores, key stats, and pros/cons for each property.
    """
    if len(req.addresses) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 addresses are required for comparison"
        )
    if len(req.addresses) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 3 addresses can be compared at once"
        )

    # Deduplicate addresses
    addresses = list(dict.fromkeys(req.addresses))
    if len(addresses) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 unique addresses are required"
        )

    notes_manager = get_notes_manager()
    properties = []

    for address in addresses:
        try:
            # Check for cached data
            extracted_data = get_cached_data(address, notes_manager)
            analysis_results = get_cached_analysis(address, notes_manager)

            if not extracted_data or not analysis_results:
                # Property needs to be analyzed first
                properties.append(PropertySummary(
                    address=address,
                    scores=PropertyScores(),
                    concerns=["This property hasn't been analyzed yet. Please analyze it first."],
                    needs_analysis=True,
                ))
                continue

            summary = extract_property_summary(extracted_data, analysis_results, address)
            properties.append(summary)

        except Exception as e:
            logger.error(f"Error getting cached data for {address}: {e}")
            properties.append(PropertySummary(
                address=address,
                scores=PropertyScores(),
                concerns=[f"Error: {str(e)}"],
            ))

    # Generate comparison notes
    comparison_notes = None
    analyzed_props = [p for p in properties if p.scores.overall is not None]
    if len(analyzed_props) >= 2:
        sorted_props = sorted(analyzed_props, key=lambda p: p.scores.overall or 0, reverse=True)
        best = sorted_props[0]
        comparison_notes = f"Based on overall scores, {best.address} scores highest at {best.scores.overall}/100."

    return CompareResponse(properties=properties, comparison_notes=comparison_notes)
