---
name: saleprice-analysis
description: Predicts likely final sale price range considering property characteristics, days on market, neighborhood conditions, and comparable sales.
allowed-tools: Read, Bash(python:*), Grep
model: claude-sonnet-4-5-20250929
---

# Sale Price Prediction Skill

## Purpose

Predict the likely final sale price of a property as a ballpark range (+/- 5%), considering:
- Property characteristics (beds, baths, sqft, age, condition)
- Days on market (DOM) - a key pricing signal
- Current market conditions (buyer's vs seller's market)
- Mortgage rate environment
- Seasonal factors
- Comparables and neighborhood pricing

## Baseline Establishment

The prediction starts from a baseline:
1. **Redfin estimate** (if available) - best starting point
2. **List price** - use if no estimate available
3. **Derived from neighborhood median** - last resort if neither available

## Days on Market (DOM) Impact

DOM is one of the strongest predictors of final sale price relative to list:

| DOM Range | Typical Impact | Interpretation |
|-----------|----------------|----------------|
| < 7 days | +2% to +5% | Hot property - likely multiple offers, sells at/above ask |
| 7-14 days | +0% to +2% | Strong demand, may get full ask |
| 14-30 days | -1% to +1% | Normal pace, sells near ask |
| 30-45 days | -2% to -4% | Starting to stale, may need price cut |
| 45-60 days | -4% to -6% | Stale listing, significant negotiation room |
| > 60 days | -6% to -12% | Major price reduction likely, investigate why |
| > 90 days | -10% to -15%+ | Serious issues - price, condition, or market |

## Market Condition Adjustments

### Market Type
| Condition | Impact | Notes |
|-----------|--------|-------|
| Strong seller's market | +3% to +5% | Multiple offers common, limited inventory |
| Moderate seller's market | +1% to +3% | Slight seller advantage |
| Balanced market | -1% to +1% | Near list price typical |
| Moderate buyer's market | -2% to -4% | Negotiation room, inventory building |
| Strong buyer's market | -4% to -6% | Significant leverage for buyers |

### Interest Rate Environment
| Condition | Impact | Notes |
|-----------|--------|-------|
| Rates falling | +1% to +2% | Buying power increasing, more competition |
| Rates stable | 0% | Neutral |
| Rates rising slowly | -1% to -2% | Buyer urgency but declining affordability |
| Rates rising fast (>0.5%/mo) | -2% to -4% | Affordability crisis, reduced demand |

### Seasonality
| Season | Impact | Notes |
|--------|--------|-------|
| Spring (Mar-May) | +1% to +2% | Peak buying season, most competition |
| Summer (Jun-Aug) | +0% to +1% | Strong but families want settled before school |
| Fall (Sep-Nov) | -1% to 0% | Slowing market, motivated sellers |
| Winter (Dec-Feb) | -2% to -3% | Low inventory but fewer buyers, holiday effect |

## Property Feature Adjustments

Consider these relative to neighborhood averages:

### Schools
- Schools significantly above average (2+ rating points): +1% to +2%
- Schools at average: 0%
- Schools significantly below average: -1% to -2%

### Walkability/Transit (Urban Areas)
- Walk score > 80: +2% to +4% (urban premium)
- Walk score 50-80: +0% to +1%
- Walk score < 50: -1% to -2% (suburban, car-dependent)

### Lot Size (Suburban/Rural)
- Lot significantly larger than average: +1% to +3%
- Lot at average: 0%
- Lot significantly smaller: -1% to -2%

### Year Built / Condition
- New construction (< 5 years): +2% to +4%
- Updated/renovated: +1% to +2%
- Original condition, dated: -2% to -4%
- Deferred maintenance visible: -3% to -6%

### HOA Impact
- Reasonable HOA (< $300/mo): 0%
- High HOA ($300-$500/mo): -1% to -2%
- Very high HOA (> $500/mo): -2% to -4%

## Luxury Property Adjustments ($1.5M+)

Luxury properties behave DIFFERENTLY from mid-market. Do NOT apply mid-market assumptions.

### Key Realities
- **Smaller buyer pool** → less competition, not more
- **Longer time to sell** → higher DOM is normal for luxury
- **More negotiation** → sophisticated buyers, lower sale-to-list ratios
- **New construction less differentiating** → luxury buyers value location, views, uniqueness over "newness"

### Rules
1. **NEVER create a "Luxury Property Premium" factor.** Being expensive is not a premium — the baseline already reflects value.
2. **Scale down new construction premium:**
   - Under $1M: +3% to +5% (full range)
   - $1M-$2M: +2% to +3%
   - $2M-$3M: +1% to +2%
   - Over $3M: +0% to +1%
3. **Cap individual positive factors:** Max +3% per factor for >$2M, max +2% for >$3M
4. **Luxury-specific negatives to consider:** Smaller buyer pool (-1% to -2%), longer marketing time

## Scoring Guidelines (Confidence Score)

The confidence score reflects prediction reliability:

**High confidence (80-100):**
- Redfin estimate available
- DOM < 30 days
- Clear market conditions
- Good comparable data
- Typical property type for area

**Medium confidence (50-79):**
- List price only (no estimate)
- DOM 30-60 days
- Mixed market signals
- Limited comparables

**Low confidence (0-49):**
- No estimate or list price concerns
- DOM > 60 days (harder to predict)
- Unusual property type
- Market volatility
- Significant unknowns

## Important Rules

### Conservative Predictions
When uncertain, lean toward predictions closer to list price. It's better to be slightly off than dramatically wrong.

### Explain Adjustments
Always explain which factors pushed the prediction up or down from baseline. The user needs to understand the reasoning.

### Market Context Matters
A property in Seattle at 3% cap rate is normal; same in Ohio is concerning. Always interpret in regional context.

### Don't Overfit
With too many small adjustments, the model becomes unpredictable. Focus on the 3-5 biggest factors.

### Time Sensitivity
Note that predictions become less reliable the longer a property sits. A DOM > 60 days property is inherently harder to predict.

## Output Format

Return predictions with:
1. **Predicted midpoint** - single best estimate
2. **Range** - +/- 5% band around midpoint
3. **Comparison** - vs list price and vs Redfin estimate
4. **Key factors** - the 3-6 most impactful adjustments
5. **Reasoning** - 2-3 sentence explanation
6. **Confidence** - high/medium/low with score

## Supporting Documentation

- [adjustment_factors.md](adjustment_factors.md) - Detailed adjustment factor tables and ranges
- [market_timing.md](market_timing.md) - DOM analysis and market timing guidance
