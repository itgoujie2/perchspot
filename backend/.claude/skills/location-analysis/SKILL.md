---
name: location-analysis
description: Analyzes location quality including neighborhood, commute, walkability, amenities, region identification, and commute times to hot areas. Use when evaluating property location, accessibility, or lifestyle factors.
allowed-tools: Read, Bash(python:*), Grep
model: claude-sonnet-4-5-20250929
---

# Location Analysis Skill

## Purpose

Analyze location quality for a residential property using:
- Region and neighborhood identification
- Commute times to configurable "hot areas" (employment centers) via Google Maps API
- Neighborhood characteristics (urban/suburban/rural)
- Commute considerations (if work location provided)
- Walkability and accessibility
- Nearby amenities

## Hot Areas Configuration

The file [hot_areas.md](hot_areas.md) defines commute destinations grouped by metro region. Each entry has a name and a reference address used for Google Maps Distance Matrix API queries.

The system automatically detects which metro region a property belongs to and fetches commute times to all hot areas in that region.

## When to Use

Use this skill when you need to:
- Identify which region and neighborhood a property is in
- Calculate commute times to major employment centers
- Evaluate neighborhood quality and character
- Assess commute times and accessibility
- Determine walkability and transit options
- Score location quality (0-100 scale)

## Instructions

### Step 1: Extract Location Information

```python
# Address provides city, state, and general area
address = "123 Main St, Seattle, WA 98101"

# Optional: Work location for commute analysis
work_location = "Downtown Seattle"  # or None
```

### Step 2: Region Detection and Commute Calculation

The skill automatically:
1. Parses `hot_areas.md` to load all metro regions and their hot areas
2. Detects the property's metro region via city/state keyword matching
3. Calls Google Maps Distance Matrix API for drive time (peak hours, pessimistic) and transit time to each hot area in the region
4. Passes commute data into the analysis prompt

### Step 3: Apply Analysis Framework

Load contexts:

```python
from app.context.context_manager import context_manager
contexts = context_manager.get_contexts_for('location_skill')
```

Key contexts:
- [commute_evaluation.md](commute_evaluation.md) - Commute assessment
- [neighborhood_scoring.md](neighborhood_scoring.md) - Neighborhood quality
- [walkability_factors.md](walkability_factors.md) - Walkability scoring
- [hot_areas.md](hot_areas.md) - Hot areas per metro region

### Step 4: Provide Structured Analysis

```json
{
    "score": 80,
    "confidence": "medium",
    "reasoning": "Suburban location with good accessibility. Quiet neighborhood, 30-minute commute to downtown, walkable to local amenities.",
    "strengths": [
        "Quiet residential neighborhood",
        "Close to major highways (I-5)",
        "Walkable to grocery stores and parks"
    ],
    "concerns": [
        "Limited public transit options",
        "30-minute commute in traffic",
        "Few restaurants within walking distance"
    ],
    "details": {
        "region": "Seattle Metro",
        "neighborhood": "Capitol Hill",
        "neighborhood_type": "urban",
        "walkability_assessment": "High - most amenities walkable",
        "commute_assessment": "Good - short drive or transit to major centers",
        "commute_to_hot_areas": [
            {"name": "SLU (South Lake Union)", "drive_minutes": 12, "transit_minutes": 22},
            {"name": "Seattle Downtown", "drive_minutes": 8, "transit_minutes": 15},
            {"name": "Bellevue Downtown", "drive_minutes": 25, "transit_minutes": 45},
            {"name": "Redmond Downtown", "drive_minutes": 35, "transit_minutes": 55},
            {"name": "Microsoft Campus", "drive_minutes": 32, "transit_minutes": 50}
        ],
        "amenities_nearby": ["grocery stores", "restaurants", "parks", "transit"]
    }
}
```

## Important Rules

### Missing Data
**NEVER list missing data as a concern.** "Work location not provided", "walkability data unavailable", or "transit times unknown" are data limitations, NOT location deficiencies. They affect confidence level, not score or concerns. Only list actual location issues as concerns.

### Uneven Strengths/Concerns
Strengths and concerns do NOT need to be balanced. A prime location might have 4 strengths and 0-1 concerns. A poor location might have 1 strength and 4 concerns. Be honest — don't pad lists.

## Scoring Guidelines

- **90-100**: Prime location, urban center, excellent transit, walkable, <15 min to multiple hot areas
- **80-89**: Great location, good accessibility, some amenities walkable, <25 min to key hot areas
- **70-79**: Good location, suburban, car-dependent but convenient, <35 min to hot areas
- **60-69**: Fair location, longer commutes, limited amenities, 35-50 min to hot areas
- **50-59**: Below average, remote, poor accessibility, >50 min to hot areas
- **< 50**: Poor location, very remote or undesirable area

## Analysis Framework

### Region and Neighborhood Identification
- Identify the metro region (Seattle Metro, SF Bay Area, Portland Metro, etc.)
- Identify the specific neighborhood by name (e.g., Capitol Hill, Ballard, SoMa)
- Consider neighborhood reputation, trends, and character

### Commute to Hot Areas Evaluation
Use actual Google Maps commute data when available:
- Drive < 15 min to nearest hot area: Excellent (+15 points)
- Drive 15-25 min: Good (+5 points)
- Drive 25-40 min: Fair (baseline)
- Drive 40-60 min: Poor (-10 points)
- Drive > 60 min: Very poor (-20 points)

### Neighborhood Type Assessment
- **Urban**: Downtown, high-density, walkable, transit-rich
- **Suburban**: Residential, car-dependent, family-friendly
- **Rural**: Remote, large lots, limited services

### Commute Evaluation
- < 15 minutes: Excellent (+10 points)
- 15-30 minutes: Good (baseline)
- 30-45 minutes: Fair (-5 points)
- 45-60 minutes: Poor (-10 points)
- > 60 minutes: Very poor (-20 points)

### Walkability Factors
- Grocery stores within 0.5 miles: +5 points
- Restaurants/cafes within 0.5 miles: +5 points
- Parks within 0.5 miles: +3 points
- Transit stops within 0.25 miles: +5 points

### Power Line & Electrical Infrastructure
- High voltage lines (≥115kV) within 0.1 miles: -15 to -20 points
- High voltage lines within 0.25 miles: -8 to -12 points
- Substation within 0.25 miles: -5 to -10 points
- Power infrastructure 0.25-0.5 miles: Minor note (-3 to -5 points)
- No power infrastructure within 0.5 miles: No impact

## Additional Resources

For commute evaluation methodology, see [commute_evaluation.md](commute_evaluation.md).

For neighborhood scoring details, see [neighborhood_scoring.md](neighborhood_scoring.md).

For walkability assessment, see [walkability_factors.md](walkability_factors.md).

For hot area definitions, see [hot_areas.md](hot_areas.md).

## Example Usage

```python
# Analyze location
address = "123 Main St, Seattle, WA 98101"
work_location = "Bellevue, WA"  # Optional

# This skill will:
# 1. Detect region (Seattle Metro) and identify neighborhood
# 2. Fetch commute times to all Seattle hot areas via Google Maps
# 3. Assess neighborhood type and character
# 4. Evaluate commute if work location provided
# 5. Determine walkability
# 6. Return structured analysis with score, region, neighborhood, and commute_to_hot_areas
```
