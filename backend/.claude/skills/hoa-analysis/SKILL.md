---
name: hoa-analysis
description: Analyzes HOA documents (CC&Rs, bylaws, budgets, reserve studies) to extract fees, restrictions, financial health, and risk factors.
allowed-tools: Read
model: claude-sonnet-4-5-20250929
---

# HOA Document Analysis Skill

## Purpose

Analyze HOA documents (CC&Rs, bylaws, budgets, reserve studies) to extract:
- Monthly/annual fees and what they cover
- Reserve fund health (% funded)
- Rental restrictions
- Pet restrictions
- Special assessment history and risk
- Pending litigation
- Architectural restrictions
- Overall HOA financial health score

## Document Types

### CC&Rs (Covenants, Conditions & Restrictions)
- Property use restrictions
- Architectural guidelines
- Pet policies
- Rental/lease restrictions
- Enforcement procedures

### Bylaws
- Board governance
- Voting procedures
- Meeting requirements
- Amendment procedures

### Budget/Financial Statements
- Monthly dues breakdown
- Reserve fund balance
- Operating expenses
- Special assessments

### Reserve Study
- Reserve fund adequacy
- Projected major expenses
- Funding plan

## Key Metrics to Extract

### Fees
- Monthly dues amount
- What's included (water, garbage, insurance, etc.)
- Expected increases
- Special assessment history

### Reserve Fund Health
- **Excellent (80%+ funded)**: Well-prepared for future repairs
- **Good (60-79% funded)**: Adequate with some risk
- **Fair (40-59% funded)**: Underfunded, special assessments likely
- **Poor (< 40% funded)**: High risk of special assessments

### Restrictions
- Rental restrictions (minimum lease term, % cap, waiting periods)
- Pet restrictions (size limits, breed restrictions, number limits)
- Architectural restrictions (approval process, exterior changes)
- Parking/vehicle restrictions

### Red Flags
- Pending litigation
- Multiple recent special assessments
- Declining reserve fund
- High delinquency rate
- Unresolved maintenance issues
- Reserve fund < 40%
- No reserve study in past 5 years

## Scoring Guidelines

Start at 70 (average HOA) and adjust:

**Financial adjustments:**
- Reserve 80%+ funded: +15
- Reserve 60-79% funded: +5
- Reserve 40-59% funded: -5
- Reserve < 40% funded: -15
- Recent special assessment: -10
- Multiple special assessments (2+ in 5 years): -20
- Pending litigation: -15
- High delinquency (> 10%): -10

**Fee adjustments:**
- Fees < $200/mo: +5
- Fees $200-400/mo: +0
- Fees $400-600/mo: -5
- Fees > $600/mo: -10

**Restriction adjustments:**
- No rental restrictions: +5
- Some rental restrictions: +0
- Strict rental restrictions (no rentals or 1yr+ minimum): -10
- Owner-occupancy requirement: -15

**Score interpretation:**
- 80-100: Excellent HOA, financially healthy, reasonable rules
- 60-79: Good HOA, typical restrictions and finances
- 40-59: Fair HOA, some concerns about finances or restrictions
- 20-39: Poor HOA, significant financial or governance issues
- 0-19: High-risk HOA, avoid or investigate thoroughly

## Output Format

Return analysis as JSON:

```json
{
    "score": 65,
    "confidence": "medium",
    "reasoning": "HOA is financially stable with 75% reserve funding. Monthly fees of $450 are above average but include water and exterior maintenance. Rental restrictions may limit investment potential.",
    "strengths": [
        "Reserve fund 75% funded",
        "No pending litigation",
        "Professional management company",
        "Well-maintained common areas"
    ],
    "concerns": [
        "High monthly fees ($450/mo)",
        "90-day minimum lease restriction",
        "Special assessment in 2023 ($2,500)"
    ],
    "details": {
        "monthly_fee": 450,
        "fee_includes": ["water", "garbage", "exterior maintenance", "common area insurance"],
        "reserve_fund": {
            "funded_percentage": 75,
            "balance": 250000,
            "assessment": "adequate"
        },
        "rental_restrictions": {
            "allowed": true,
            "minimum_lease": "90 days",
            "cap": null,
            "waiting_period": null
        },
        "pet_restrictions": {
            "allowed": true,
            "size_limit": "50 lbs",
            "breed_restrictions": true,
            "max_pets": 2
        },
        "special_assessments": [
            {
                "year": 2023,
                "amount": 2500,
                "purpose": "roof replacement"
            }
        ],
        "litigation": {
            "pending": false,
            "history": null
        },
        "management": {
            "type": "professional",
            "company": "ABC Management"
        },
        "governance": {
            "board_size": 5,
            "meetings": "monthly",
            "financials_available": true
        }
    }
}
```

## Important Rules

1. **Look for hidden costs** - Special assessments, fee increases, delinquencies
2. **Rental restrictions matter for investors** - Flag any restrictions clearly
3. **Reserve fund is key** - Underfunded reserves = future special assessments
4. **Litigation is a major red flag** - Always note if present
5. **Don't invent data** - If document doesn't specify, use null or "not specified"
6. **Note document age** - Older documents may have outdated information
7. **Consider investor perspective** - Restrictions that don't affect owner-occupants may impact investors significantly
