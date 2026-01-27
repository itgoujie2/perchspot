---
name: location-analysis
description: Analyzes location quality including neighborhood, commute, walkability, and amenities. Use when evaluating property location, accessibility, or lifestyle factors.
allowed-tools: Read, Bash(python:*), Grep
model: claude-sonnet-4-5-20250929
---

# Location Analysis Skill

## Purpose

Analyze location quality for a residential property using:
- Neighborhood characteristics (urban/suburban/rural)
- Commute considerations (if work location provided)
- Walkability and accessibility
- Nearby amenities

## When to Use

Use this skill when you need to:
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

### Step 2: Apply Analysis Framework

Load contexts:

```python
from app.context.context_manager import context_manager
contexts = context_manager.get_contexts_for('location_skill')
```

Key contexts:
- [commute_evaluation.md](commute_evaluation.md) - Commute assessment
- [neighborhood_scoring.md](neighborhood_scoring.md) - Neighborhood quality
- [walkability_factors.md](walkability_factors.md) - Walkability scoring

### Step 3: Provide Structured Analysis

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
        "neighborhood_type": "suburban",
        "walkability_assessment": "Moderate - some amenities walkable",
        "commute_assessment": "Reasonable - 30 min drive, limited transit",
        "amenities_nearby": ["grocery stores", "parks", "schools"]
    }
}
```

## Scoring Guidelines

- **90-100**: Prime location, urban center, excellent transit, walkable
- **80-89**: Great location, good accessibility, some amenities walkable
- **70-79**: Good location, suburban, car-dependent but convenient
- **60-69**: Fair location, longer commutes, limited amenities
- **50-59**: Below average, remote, poor accessibility
- **< 50**: Poor location, very remote or undesirable area

## Analysis Framework

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

## Additional Resources

For commute evaluation methodology, see [commute_evaluation.md](commute_evaluation.md).

For neighborhood scoring details, see [neighborhood_scoring.md](neighborhood_scoring.md).

For walkability assessment, see [walkability_factors.md](walkability_factors.md).

## Example Usage

```python
# Analyze location
address = "123 Main St, Seattle, WA 98101"
work_location = "Bellevue, WA"  # Optional

# This skill will:
# 1. Assess neighborhood type and character
# 2. Evaluate commute if work location provided
# 3. Determine walkability
# 4. Return structured analysis with score
```
