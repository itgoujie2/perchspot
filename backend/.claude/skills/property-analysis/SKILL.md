---
name: property-analysis
description: Analyzes property condition from extracted listing data. Evaluates property type, age, lot, features, climate risks, and maintenance outlook using Redfin-extracted data and knowledge base context.
allowed-tools: Read, Bash(python:*), Grep
model: claude-sonnet-4-5-20250929
---

# Property Analysis Skill

## Purpose

Analyze residential property condition using pre-extracted Redfin data:
- Property details (type, year built, bedrooms, bathrooms, sqft, lot size, parking)
- Property description (from listing agent)
- Pricing and market data (list price, price/sqft, days on market, market type)
- Features (interior, exterior, appliances, heating/cooling)
- HOA information
- Climate risks
- Photo count (as a confidence signal)
- Knowledge base context (ingested expert knowledge about PNW housing)

**Data source**: Pre-extracted JSON files in `property_data/` directory — no live scraping during analysis.

## When to Use

Use this skill when you need to:
- Evaluate property condition, age, and maintenance outlook
- Assess property type trade-offs (SFH vs townhome vs condo)
- Identify red flags from listing data
- Score property quality (0-100 scale)
- Flag missing critical information

## Instructions

### Step 1: Load Extracted Property Data

Property data is provided as a pre-extracted JSON dict with these sections:
- `property`: address, status, description, MLS number
- `pricing`: list_price, redfin_estimate, price_per_sqft, rental_estimate
- `details`: property_type, year_built, bedrooms, bathrooms, living_area_sqft, lot_size_sqft, parking
- `features`: interior features, exterior features, appliances, heating_cooling
- `hoa`: has_hoa, fee, frequency
- `taxes`: annual_amount
- `climate_risks`: flood, fire, heat, wind, air_quality
- `market_trends`: market_type, days_on_market
- `images`: photo_count

### Step 2: Apply Scoring Rubric

Reference these supporting documents:
- [condition_scoring_rubric.md](condition_scoring_rubric.md) - Detailed scoring rules for year built, property type, lot, parking, HOA, climate, DOM
- [housing_styles.md](housing_styles.md) - Architectural style identification and quality by era
- [photo_analysis_guide.md](photo_analysis_guide.md) - Photo-based condition signals
- [scoring_philosophy.md](scoring_philosophy.md) - Overall scoring approach

### Step 3: Incorporate Knowledge Base

Query the knowledge base for relevant context about:
- Property characteristics mentioned in the listing (e.g., specific builder, materials, neighborhood)
- Age-related concerns for the property's era
- PNW-specific issues

### Step 4: Provide Structured Analysis

```json
{
    "score": 78,
    "confidence": "high",
    "reasoning": "Well-maintained 2002 custom build with generous lot. Approaching major system replacement age for roof and HVAC.",
    "strengths": [
        "Custom-built 4,980 sqft with premium finishes",
        "Large 13,504 sqft lot in quiet enclave",
        "5 bedrooms / 4.5 baths — excellent for families",
        "3-car garage with attached access"
    ],
    "concerns": [
        "Year 2002 build — original roof likely needs replacement ($15-25K)",
        "Original water heater may need replacement"
    ],
    "details": {
        "property_type_assessment": "Single family — best for long-term value and customization",
        "age_assessment": "23 years old — approaching major system replacements (roof, HVAC, water heater)",
        "lot_assessment": "13,504 sqft — above average for Sammamish, good privacy and potential",
        "parking_assessment": "3-car garage — above market standard, desirable",
        "hoa_assessment": "$42/month — minimal, likely common area maintenance only",
        "maintenance_risk": "medium",
        "missing_data": ["heating_cooling", "exterior_material", "roof_type", "foundation"]
    }
}
```

## Important Rules

### Missing Data
**NEVER list missing data as a concern.** Phrases like "heating/cooling info not extracted", "lot size unknown", or "features unavailable" are data extraction limitations, NOT property deficiencies. They affect confidence level, not the score or concerns list. Only list actual property issues as concerns.

### Uneven Strengths/Concerns
Strengths and concerns do NOT need to be balanced. A great property might have 4 strengths and 1 concern. A problematic property might have 1 strength and 4 concerns. Be honest about what you find — don't pad lists to make them equal.

## Scoring Guidelines

- **90-100**: New/near-new construction, no concerns, complete data, excellent features
- **80-89**: Well-maintained, modern systems, minor age-related items only
- **70-79**: Good overall, some deferred maintenance or approaching system replacements
- **60-69**: Fair condition, multiple maintenance concerns or significant data gaps
- **50-59**: Below average, major system replacements overdue or significant issues
- **< 50**: Poor condition, major renovations required or critical red flags

## Confidence Levels

- **High**: Complete extracted data, 25+ photos, clear listing description, modern property
- **Medium**: Some data gaps (1-2 missing fields), 15-24 photos, adequate description
- **Low**: Significant data gaps (3+ missing fields), < 15 photos, vague description
