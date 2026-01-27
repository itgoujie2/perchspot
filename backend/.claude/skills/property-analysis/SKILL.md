---
name: property-analysis
description: Analyzes property condition from photos and listing data. Use when evaluating property quality, maintenance, updates, or visual condition. Requires Redfin data and property photos.
allowed-tools: Read, Bash(python:*), Grep
model: claude-sonnet-4-5-20250929
---

# Property Analysis Skill

## Purpose

Analyze residential property condition using:
- Property photos (vision AI analysis)
- Listing details (price, beds, baths, sqft)
- Property description
- Days on market

## When to Use

Use this skill when you need to:
- Evaluate property condition and maintenance
- Identify visible issues or red flags
- Assess renovation quality and updates
- Score property condition (0-100 scale)

## Instructions

### Step 1: Gather Property Data

Use the Redfin collector to scrape property data:

```python
from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector

collector = ScreenshotExtractorCollector()
result = await collector.collect_property_data(address)
property_data = result['data']
photos = property_data.get('image_urls', [])
```

### Step 2: Analyze with Context

Load the analysis contexts:

```python
from app.context.context_manager import context_manager
contexts = context_manager.get_contexts_for('property_skill')
```

Key contexts to reference:
- [photo_analysis_guide.md](photo_analysis_guide.md) - How to evaluate photos
- [condition_scoring_rubric.md](condition_scoring_rubric.md) - Scoring methodology
- [scoring_philosophy.md](scoring_philosophy.md) - Overall scoring approach

### Step 3: Provide Structured Analysis

Return analysis in this format:

```json
{
    "score": 85,
    "confidence": "high",
    "reasoning": "Well-maintained property with recent kitchen updates. Minor exterior maintenance needed.",
    "strengths": [
        "Recently updated kitchen (2022)",
        "Well-maintained landscaping",
        "New roof (2021)"
    ],
    "concerns": [
        "Siding shows some weathering",
        "Deck needs refinishing",
        "HVAC system age unknown"
    ],
    "details": {
        "exterior_condition": "Good overall, minor maintenance items",
        "interior_condition": "Excellent, recently updated",
        "updates_renovations": "Kitchen remodel 2022, new roof 2021",
        "maintenance_issues": ["Siding weathering", "Deck refinishing needed"]
    }
}
```

## Scoring Guidelines

- **90-100**: Exceptional condition, recent updates, no visible issues
- **80-89**: Very good condition, well-maintained, minor cosmetic items
- **70-79**: Good condition, some deferred maintenance visible
- **60-69**: Fair condition, multiple maintenance items needed
- **50-59**: Below average, significant repairs needed
- **< 50**: Poor condition, major renovations required

## Photo Analysis Checklist

### Exterior
- Roof condition (shingles, sagging, moss)
- Siding/exterior walls (cracks, paint, warping)
- Foundation (visible cracks, settling)
- Landscaping maintenance level
- Driveway/walkways condition

### Interior
- Kitchen: Appliances age, counters, cabinets
- Bathrooms: Fixtures, tile, signs of water damage
- Flooring: Type, condition, consistency
- Walls/ceilings: Paint, cracks, water stains
- Windows: Condition, style, age

### Red Flags
- Heavy staging hiding issues
- Odd camera angles
- Missing key rooms (bathrooms, kitchen)
- Very few photos (< 10 for a house)
- Visible water damage or structural issues

## Confidence Levels

- **High**: 15+ photos, clear views, recent listing, consistent quality
- **Medium**: 10-14 photos, some rooms missing, or older photos
- **Low**: < 10 photos, poor quality, or significant data gaps

## Additional Resources

For detailed photo analysis techniques, see [photo_analysis_guide.md](photo_analysis_guide.md).

For complete scoring rubric and examples, see [condition_scoring_rubric.md](condition_scoring_rubric.md).

## Example Usage

```python
# Analyze property at given address
address = "123 Main St, Seattle, WA 98101"

# This skill will:
# 1. Scrape Redfin for property data and photos
# 2. Analyze photos using vision AI
# 3. Evaluate condition against scoring rubric
# 4. Return structured analysis with score and reasoning
```
