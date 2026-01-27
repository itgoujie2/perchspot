---
name: school-analysis
description: Analyzes quality of nearby schools using ratings, distance, and types. Use when evaluating schools for families or assessing education quality near a property.
allowed-tools: Read, Bash(python:*), Grep
model: claude-sonnet-4-5-20250929
---

# School Analysis Skill

## Purpose

Analyze school quality near a residential property using:
- School ratings (from Redfin or GreatSchools)
- Distance from property
- School types (elementary, middle, high)
- Grade levels served

## When to Use

Use this skill when you need to:
- Evaluate school quality for families
- Compare elementary, middle, and high school options
- Assess education quality as part of location evaluation
- Score school quality (0-100 scale)

## Instructions

### Step 1: Get School Data

Schools are typically scraped along with property data from Redfin:

```python
from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector

collector = ScreenshotExtractorCollector()
result = await collector.collect_property_data(address)
schools = result['schools']  # List of school dictionaries
```

Each school includes:
- `name`: School name
- `rating`: Rating out of 10 (GreatSchools)
- `grades`: Grade levels (e.g., "K-5", "6-8", "9-12")
- `distance_miles`: Distance from property
- `type`: School type (elementary, middle, high)

### Step 2: Apply Analysis Framework

Load analysis contexts:

```python
from app.context.context_manager import context_manager
contexts = context_manager.get_contexts_for('school_skill')
```

Key contexts to reference:
- [rating_interpretation.md](rating_interpretation.md) - How to interpret ratings
- [school_quality_factors.md](school_quality_factors.md) - What makes schools good
- [scoring_philosophy.md](scoring_philosophy.md) - Overall scoring approach

### Step 3: Provide Structured Analysis

Return analysis in this format:

```json
{
    "score": 78,
    "confidence": "high",
    "reasoning": "Strong elementary school (9/10) and solid middle school (8/10), but high school rating is lower (6/10).",
    "strengths": [
        "Excellent elementary school within 1 mile",
        "All schools within reasonable distance (< 3 miles)",
        "Middle school highly rated"
    ],
    "concerns": [
        "High school rating below average",
        "Limited private school options nearby",
        "Elementary school may be crowded (popular area)"
    ],
    "details": {
        "elementary_rating": 9,
        "middle_rating": 8,
        "high_rating": 6,
        "average_distance": 1.8,
        "school_breakdown": [
            {
                "name": "Lincoln Elementary",
                "rating": 9,
                "type": "elementary",
                "assessment": "Highly rated, excellent test scores"
            },
            {
                "name": "Washington Middle School",
                "rating": 8,
                "type": "middle",
                "assessment": "Strong academics, good extracurriculars"
            },
            {
                "name": "Roosevelt High School",
                "rating": 6,
                "type": "high",
                "assessment": "Average performance, improving trends"
            }
        ]
    }
}
```

## Scoring Guidelines

Calculate score based on weighted average:
- Elementary school: 40% weight
- Middle school: 30% weight
- High school: 30% weight

**Rating to score conversion:**
- 9-10 rating → 90-100 score (Exceptional)
- 8 rating → 80-89 score (Very good)
- 7 rating → 70-79 score (Good)
- 6 rating → 60-69 score (Fair)
- 5 rating → 50-59 score (Below average)
- < 5 rating → < 50 score (Poor)

**Distance adjustments:**
- Within 1 mile: No penalty
- 1-2 miles: -2 points
- 2-3 miles: -5 points
- 3-5 miles: -10 points
- > 5 miles: -15 points

## Analysis Framework

### Rating Interpretation
- **9-10**: Top-tier school, highly competitive, excellent outcomes
- **8**: Very good school, strong academics, above-average performance
- **7**: Good school, solid academics, meets expectations
- **6**: Fair school, average performance, some concerns
- **5**: Below average, significant improvement needed
- **< 5**: Poor performance, serious concerns

### Key Factors to Consider
1. **Rating consistency**: Are all school levels similarly rated?
2. **Distance**: How accessible are the schools?
3. **School type**: Public vs private, magnet vs neighborhood
4. **Trends**: Is performance improving or declining?
5. **Capacity**: Are schools overcrowded or under-enrolled?

### Red Flags
- All schools rated below 5
- High school rated significantly lower than elementary/middle
- No schools within 3 miles
- Large rating inconsistencies (9 elementary, 4 high)

## Confidence Levels

- **High**: Complete data for all school levels, clear ratings
- **Medium**: Missing data for one school level, or estimated ratings
- **Low**: Limited school data, or data > 1 year old

## Additional Resources

For detailed rating interpretation guidance, see [rating_interpretation.md](rating_interpretation.md).

For understanding school quality factors beyond ratings, see [school_quality_factors.md](school_quality_factors.md).

## Example Usage

```python
# Analyze schools for property
address = "123 Main St, Seattle, WA 98101"

# This skill will:
# 1. Get school data from Redfin
# 2. Analyze ratings, distance, and types
# 3. Calculate weighted score
# 4. Return structured analysis with reasoning
```
