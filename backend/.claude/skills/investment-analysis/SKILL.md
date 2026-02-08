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

## Scoring Guidelines

Start at 50 and adjust:

**Metrics-based adjustments:**
- Cap rate > 6%: +15 | 4-6%: +5 | < 4%: -5 | < 2%: -15
- Cash-on-cash > 4%: +10 | 0-4%: +0 | negative: -10
- GRM < 15: +10 | 15-20: +0 | > 20: -10
- Gross yield > 6%: +5 | 4-6%: +0 | < 4%: -5

**Market adjustments:**
- Days on market < 7: +5 (hot property)
- Days on market > 90: -5 (weak demand)
- Buyer's market: +5 (negotiation leverage)
- Seller's market: -5 (limited upside)

**Price assessment:**
- Price > 5% below estimate: +10
- Price > 5% above estimate: -10

**Data quality:**
- No rental estimate: cap score at 60, set confidence to low
- Missing tax data: reduce confidence

## Red Flags (mention in concerns if present)
- Negative monthly cash flow
- GRM > 20
- Cap rate < 3% (unless in known appreciation market)
- Cash-on-cash < -5%
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
