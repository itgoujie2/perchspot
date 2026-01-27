---
name: investment-analysis
description: Analyzes property investment potential including pricing, market trends, rental yield, and appreciation. Use when evaluating property as an investment or assessing market value.
allowed-tools: Read, Bash(python:*), Grep
model: claude-sonnet-4-5-20250929
---

# Investment Analysis Skill

## Purpose

Analyze investment potential for a residential property using:
- Property pricing (list price vs characteristics)
- Days on market (demand indicator)
- Market trends in the area
- Rental potential
- Appreciation potential

## When to Use

Use this skill when you need to:
- Evaluate property as an investment opportunity
- Assess if property is fairly priced
- Determine rental income potential
- Score investment quality (0-100 scale)

## Instructions

### Step 1: Get Property Financial Data

```python
from app.services.data_collectors.screenshot_extractor_collector import ScreenshotExtractorCollector

collector = ScreenshotExtractorCollector()
result = await collector.collect_property_data(address)
property_data = result['data']

# Key financial data:
# - price: Listing price
# - bedrooms, bathrooms, square_feet: Property characteristics
# - days_on_market: How long listed
# - property_type: House, condo, townhouse
```

### Step 2: Apply Investment Framework

Load contexts:

```python
from app.context.context_manager import context_manager
contexts = context_manager.get_contexts_for('investment_skill')
```

Key contexts:
- [market_analysis_framework.md](market_analysis_framework.md) - Market evaluation
- [price_comparison_method.md](price_comparison_method.md) - Pricing assessment
- [rental_yield_calculation.md](rental_yield_calculation.md) - Rental potential

### Step 3: Provide Structured Analysis

```json
{
    "score": 82,
    "confidence": "medium",
    "reasoning": "Property priced fairly for the area. Strong rental demand in neighborhood. Days on market suggests reasonable interest.",
    "strengths": [
        "Price per sqft in line with comps",
        "High rental demand area",
        "Desirable property type (single-family)"
    ],
    "concerns": [
        "Market showing signs of softening",
        "Property taxes above average",
        "Limited appreciation in last 2 years"
    ],
    "details": {
        "price_assessment": "fair",
        "market_demand": "medium",
        "rental_potential": "Strong - estimated $3,500/month",
        "appreciation_potential": "Moderate - 3-5% annually expected"
    }
}
```

## Scoring Guidelines

Base score calculation:
- Start with 50 (baseline)
- Price assessment: ±20 points
- Market demand: ±15 points
- Rental potential: ±10 points
- Appreciation potential: ±5 points

**Price Assessment:**
- Significantly underpriced: +20 points
- Slightly underpriced: +10 points
- Fairly priced: 0 points
- Slightly overpriced: -10 points
- Significantly overpriced: -20 points

**Market Demand (Days on Market):**
- < 7 days: High demand (+15 points)
- 7-30 days: Good demand (+5 points)
- 31-60 days: Fair demand (0 points)
- 61-90 days: Weak demand (-5 points)
- > 90 days: Very weak demand (-15 points)

**Rental Potential:**
- Strong rental market, high yield: +10 points
- Good rental market: +5 points
- Fair rental market: 0 points
- Poor rental market: -10 points

**Appreciation Potential:**
- Strong growth area: +5 points
- Moderate growth: 0 points
- Stagnant/declining: -5 points

## Analysis Framework

### Price-to-Value Assessment
Compare against these factors:
- Price per square foot vs area average
- Bedrooms/bathrooms count vs price
- Property type and lot size
- Condition and updates

### Market Demand Indicators
- Days on market trend
- Price changes/reductions
- Comparable sales velocity
- Inventory levels in area

### Rental Yield Estimation
Rough rental estimate:
- Single-family: ~0.7-1.0% of purchase price per month
- Condo/townhouse: ~0.6-0.9% of purchase price per month
- Adjust for area, condition, amenities

### Appreciation Factors
- Area economic growth
- Job market strength
- Population trends
- Infrastructure development
- School quality

## Red Flags

- Price reduced multiple times
- Days on market > 90 days
- Price significantly above comps
- Declining area/market
- Special assessments or HOA issues

## Confidence Levels

- **High**: Complete financial data, recent comps, clear market trends
- **Medium**: Limited comp data, or market trends unclear
- **Low**: Insufficient data, unique property, volatile market

## Additional Resources

For market analysis methodology, see [market_analysis_framework.md](market_analysis_framework.md).

For pricing comparison techniques, see [price_comparison_method.md](price_comparison_method.md).

For rental yield calculations, see [rental_yield_calculation.md](rental_yield_calculation.md).

## Example Usage

```python
# Analyze investment potential
address = "123 Main St, Seattle, WA 98101"

# This skill will:
# 1. Get property financial data from Redfin
# 2. Assess pricing vs market
# 3. Evaluate rental and appreciation potential
# 4. Return structured analysis with score
```
