"""
Context Builder — Constructs rich property queries for knowledge retrieval

Extracts property attributes and builds formatted query strings that enable
better semantic matching with generic knowledge points.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def build_knowledge_query(property_data: Dict[str, Any]) -> str:
    """
    Build a rich query string for knowledge retrieval from property data.

    Extracts key attributes that might match generic knowledge points:
    - Property basics: bedrooms, bathrooms, property type, living area
    - Age info: year built, property age
    - Location: city, state, neighborhood
    - HOA: presence and fee amount
    - Pricing: list price
    - Features: heating, roofing, foundation, etc.

    Args:
        property_data: Property data dict with structure:
            {
                "details": {"year_built": 1985, "property_type": "townhome", ...},
                "hoa": {"has_hoa": True, "fee": 350, ...},
                "location": {"city": "Seattle", "state": "WA", ...},
                "pricing": {"list_price": 850000, ...},
                ...
            }

    Returns:
        Formatted query string like:
        "4 bedroom 3 bathroom single-family home built in 1995
         Located in Bellevue WA, 2400 sqft, listed at $1.2M
         Features: HOA ($350/mo), gas heating, composite roof
         Property age: 30 years, resale home"
    """
    parts = []

    # Extract details
    details = property_data.get("details", {})
    bedrooms = details.get("bedrooms")
    bathrooms = details.get("bathrooms")
    property_type = details.get("property_type", "")
    living_area = details.get("living_area_sqft")
    year_built = details.get("year_built")
    lot_size = details.get("lot_size_sqft")
    stories = details.get("stories")

    # Property basics line
    basics = []
    if bedrooms:
        basics.append(f"{bedrooms} bedroom")
    if bathrooms:
        basics.append(f"{bathrooms} bathroom")
    if property_type:
        basics.append(property_type.replace("_", " "))
    if basics:
        parts.append(" ".join(basics))

    # Year built and age
    if year_built:
        current_year = datetime.now().year
        age = current_year - year_built
        parts.append(f"Built in {year_built} ({age} years old)")

        # Add age category hints for knowledge matching
        if age >= 50:
            parts.append("Historic/vintage home")
        elif age >= 30:
            parts.append("Older home potentially needing updates")
        elif age >= 15:
            parts.append("Established home")
        elif age < 5:
            parts.append("New construction")

    # Location info
    location = property_data.get("location", {})
    city = location.get("city", "")
    state = location.get("state", "")
    neighborhood = location.get("neighborhood", "")

    if city or state:
        loc_parts = []
        if neighborhood:
            loc_parts.append(f"{neighborhood} neighborhood")
        if city:
            loc_parts.append(city)
        if state:
            loc_parts.append(state)
        parts.append(f"Located in {' '.join(loc_parts)}")

    # Size info
    if living_area:
        parts.append(f"{living_area:,} square feet living area")
    if lot_size:
        # Convert to more readable format for large lots
        if lot_size >= 43560:  # 1 acre
            acres = lot_size / 43560
            parts.append(f"{acres:.2f} acre lot")
        else:
            parts.append(f"{lot_size:,} sqft lot")

    # Pricing
    pricing = property_data.get("pricing", {})
    list_price = pricing.get("list_price")
    if list_price:
        if list_price >= 1_000_000:
            price_str = f"${list_price / 1_000_000:.1f}M"
        else:
            price_str = f"${list_price / 1_000:,.0f}K"
        parts.append(f"Listed at {price_str}")

        # Add price category hints
        if list_price >= 2_000_000:
            parts.append("Luxury price point")
        elif list_price >= 1_000_000:
            parts.append("High-end market")
        elif list_price < 400_000:
            parts.append("Entry-level price point")

    # HOA info
    hoa = property_data.get("hoa", {})
    has_hoa = hoa.get("has_hoa")
    hoa_fee = hoa.get("fee")
    if has_hoa:
        if hoa_fee:
            parts.append(f"HOA community (${hoa_fee}/month)")
        else:
            parts.append("HOA community")
    else:
        parts.append("No HOA")

    # Features from description or features list
    features = []

    # Check for specific feature keywords in description
    description = property_data.get("description", "")
    features_list = property_data.get("features", [])

    # Heating/cooling
    heating_keywords = _extract_feature(description, features_list, [
        "gas heating", "electric heating", "heat pump", "radiant heat",
        "forced air", "central air", "AC", "air conditioning"
    ])
    if heating_keywords:
        features.extend(heating_keywords)

    # Roofing
    roof_keywords = _extract_feature(description, features_list, [
        "composition roof", "composite roof", "tile roof", "metal roof",
        "asphalt shingle", "slate roof", "wood shake"
    ])
    if roof_keywords:
        features.extend(roof_keywords)

    # Foundation
    foundation_keywords = _extract_feature(description, features_list, [
        "slab foundation", "crawl space", "basement", "raised foundation",
        "pier and beam", "concrete foundation"
    ])
    if foundation_keywords:
        features.extend(foundation_keywords)

    # Special features that may need knowledge points
    special_keywords = _extract_feature(description, features_list, [
        "pool", "spa", "hot tub", "solar panels", "well water", "septic",
        "fireplace", "hardwood floors", "waterfront", "view",
        "ADU", "mother-in-law", "guest house"
    ])
    if special_keywords:
        features.extend(special_keywords)

    if features:
        parts.append(f"Features: {', '.join(features)}")

    # Stories
    if stories and stories > 1:
        parts.append(f"{stories}-story home")

    # Property context hints
    context_hints = []

    # First-time buyer considerations
    if list_price and list_price < 600_000:
        context_hints.append("first-time buyer consideration")

    # Investment potential
    if property_type and "multi" in property_type.lower():
        context_hints.append("multi-family investment")

    # Fixer-upper indicators
    if year_built and (datetime.now().year - year_built) > 40:
        context_hints.append("potential renovation considerations")

    if context_hints:
        parts.append(f"Context: {', '.join(context_hints)}")

    return "\n".join(parts)


def _extract_feature(
    description: str,
    features_list: list,
    keywords: list
) -> list:
    """Extract matching keywords from description or features list."""
    found = []
    text = (description + " " + " ".join(features_list)).lower()

    for keyword in keywords:
        if keyword.lower() in text:
            found.append(keyword)

    return found


def build_property_summary(property_data: Dict[str, Any]) -> str:
    """
    Build a concise property summary for LLM context.

    Shorter than build_knowledge_query, focused on key identifiers.
    Used as context in the LLM filter prompt.
    """
    details = property_data.get("details", {})
    location = property_data.get("location", {})
    pricing = property_data.get("pricing", {})
    hoa = property_data.get("hoa", {})

    lines = []

    # Basic property info
    basics = []
    if details.get("bedrooms"):
        basics.append(f"{details['bedrooms']}BR")
    if details.get("bathrooms"):
        basics.append(f"{details['bathrooms']}BA")
    if details.get("property_type"):
        basics.append(details["property_type"].replace("_", " "))
    if basics:
        lines.append(" / ".join(basics))

    # Age and size
    info = []
    if details.get("year_built"):
        info.append(f"Built {details['year_built']}")
    if details.get("living_area_sqft"):
        info.append(f"{details['living_area_sqft']:,} sqft")
    if info:
        lines.append(", ".join(info))

    # Location
    loc_parts = []
    if location.get("city"):
        loc_parts.append(location["city"])
    if location.get("state"):
        loc_parts.append(location["state"])
    if loc_parts:
        lines.append(", ".join(loc_parts))

    # Price
    if pricing.get("list_price"):
        price = pricing["list_price"]
        if price >= 1_000_000:
            lines.append(f"${price / 1_000_000:.1f}M")
        else:
            lines.append(f"${price / 1_000:,.0f}K")

    # HOA
    if hoa.get("has_hoa"):
        if hoa.get("fee"):
            lines.append(f"HOA ${hoa['fee']}/mo")
        else:
            lines.append("Has HOA")
    else:
        lines.append("No HOA")

    # Climate risks (helps LLM filter exclude irrelevant disaster knowledge)
    climate = property_data.get("climate_risks", {})
    if climate:
        risk_parts = []
        for risk_type in ["flood", "fire", "wind", "heat", "drought"]:
            level = climate.get(risk_type)
            if isinstance(level, dict):
                level = level.get("level") or level.get("risk")
            if level and str(level).lower() not in ("none", "minimal", "n/a", ""):
                risk_parts.append(f"{risk_type}: {level}")
        if risk_parts:
            lines.append(f"Climate risks: {', '.join(risk_parts)}")
        else:
            lines.append("Climate risks: minimal/none reported")

    return "\n".join(lines)
