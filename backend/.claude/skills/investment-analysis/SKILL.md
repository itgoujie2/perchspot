---
name: investment-analysis
description: Analyzes property investment potential using computed financial metrics (cap rate, NOI, cash-on-cash, GRM, yield). Interprets pre-computed numbers in market context.
allowed-tools: Read, Bash(python:*), Grep
model: claude-sonnet-4-5-20250929
---

# Investment Analysis Skill

## Purpose

Interpret pre-computed investment metrics for a residential property and provide a qualitative investment assessment. The metrics (cap rate, NOI, gross yield, cash-on-cash return, GRM) are already calculated — your job is to contextualize them.

## Metric Benchmarks

### Gross Rental Yield
- < 4%: Poor — typical of appreciation-only plays in expensive markets
- 4-6%: Fair — common in suburban areas of high-cost metros
- 6-8%: Good — solid rental investment territory
- > 8%: Excellent — strong cash flow, verify it's not due to risk factors

### Cap Rate
- < 4%: Low-yield / appreciation play — common in Seattle, SF, etc.
- 4-6%: Moderate — balanced risk/return
- 6-10%: Good — strong income property
- > 10%: High-yield but investigate risk (declining area? deferred maintenance?)

### Gross Rent Multiplier (GRM) / Price-to-Rent Ratio
- < 12: Excellent for investors
- 12-15: Good
- 15-20: Fair — typical of high-cost metros
- > 20: Poor for rental investment (favors renting over buying)

### Cash-on-Cash Return
- < 0%: Negative cash flow — requires reserves or appreciation bet
- 0-4%: Break-even to modest return
- 4-8%: Good
- > 8%: Excellent — verify assumptions

### Price vs Estimate Spread
- > +5%: Potentially underpriced — good buying opportunity
- -2% to +5%: Fairly priced
- < -2%: Potentially overpriced — negotiate or wait

### Monthly Cash Flow
- Negative: Property loses money monthly (common in expensive markets)
- $0-200: Break-even
- $200-500: Decent positive flow
- > $500: Strong cash flow property

### Appreciation Rate (Annual)
- < 2%: Below average — focus on cash flow instead
- 2-4%: Average national appreciation
- 4-6%: Good — strong market
- > 6%: Excellent — high-growth area (Seattle, SF Bay Area historically)

### Total Return = Cash Flow + Appreciation
Consider BOTH components:
- Cash-flow property: 6%+ cap rate, low appreciation (Midwest, some suburbs)
- Appreciation property: 2-4% cap rate, 5%+ annual appreciation (coastal metros)
- Balanced property: 4-5% cap rate, 4% appreciation (best of both)

## Scoring Guidelines — Dual-Track Framework

Properties are evaluated on TWO tracks. Use the **higher** of the two track scores as the base:

### Track A: Cash-Flow Investment (traditional rental metrics)
Start at 50 and adjust:
- Cap rate > 6%: +15 | 4-6%: +5 | 2-4%: 0 | < 2%: -5
- Cash-on-cash > 4%: +10 | 0-4%: +5 | negative: 0
- GRM < 15: +10 | 15-20: +5 | 20-30: 0 | > 30: -5
- Gross yield > 6%: +5 | 4-6%: +3 | < 4%: 0

### Track B: Appreciation Investment (wealth-building through equity growth)
Start at 50 and adjust:
- Appreciation > 6%/yr: +15 | 4-6%: +10 | 2-4%: +5 | < 2%: 0
- Total return (appreciation + cash flow) > 5%: +10 | 2-5%: +5 | 0-2%: 0 | negative: -10

### Universal Adjustments (apply to the chosen track score)
- Price > 5% below estimate: +10
- Price > 5% above estimate: -5
- Missing rental data (using estimates): -5, cap confidence at medium

### Removed from Scoring
- ~~Days on market~~ — DOM is a pricing/demand signal, not an investment quality signal. A 40-day DOM says nothing about rental viability or appreciation potential.
- ~~Seller's/buyer's market~~ — Market type affects purchase timing, not long-term investment value. Do not penalize or reward based on market type.

### Data Quality
- No rental estimate AND no estimated rent: cap score at 70, set confidence to low
- Missing tax data: reduce confidence

### High-Cost Market Reality
In expensive metros (Seattle, SF, Portland, etc.), low cap rates (< 4%) and negative cash flow are **normal and expected**. These markets generate returns primarily through appreciation (5-8%/year historically). Do NOT treat negative cash flow as an automatic disqualifier — evaluate using Track B (appreciation) when the property is in a high-cost market. A property with -5% cash-on-cash but +7% appreciation has +2% total return — that is a viable investment.

## Red Flags (mention in concerns if present)
- Negative total return (appreciation + cash flow combined is negative)
- GRM > 30
- Cap rate < 2% in a low-appreciation area (< 3%/yr appreciation)
- Cash-on-cash < -10% with no appreciation upside
- Property taxes > 2% of value
- HOA > $500/month

## Important Rules

### Missing Data
**NEVER list missing data as a concern.** "Rental estimate unavailable" or "tax data missing" are data limitations, NOT investment risks. They affect confidence level, not score or concerns. Only list actual financial/investment risks as concerns.

### Uneven Strengths/Concerns
Strengths and concerns do NOT need to be balanced. A great investment might have 4 strengths and 1 concern. A risky one might have 1 strength and 4 concerns. Be honest — don't pad lists.

### Additional Notes
- In expensive metros (Seattle, SF, Portland), cap rates < 4% are normal — don't treat as automatic red flag, but note it's an appreciation play
- Always frame negative cash flow honestly: the property requires monthly subsidy from the investor
- Mention the financing assumptions (20% down, 7% rate, 30yr) when discussing cash-on-cash

## Confidence Levels
- **High**: Rental estimate + tax data + market data all available
- **Medium**: Missing one of rental estimate or tax data
- **Low**: Missing rental estimate (most metrics can't be computed)
