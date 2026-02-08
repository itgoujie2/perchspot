---
name: inspection-analysis
description: Analyzes home inspection reports to extract issues, severities, estimated repair costs, and overall property condition assessment.
allowed-tools: Read
model: claude-sonnet-4-5-20250929
---

# Inspection Report Analysis Skill

## Purpose

Analyze a home inspection report PDF text to extract:
- Issues organized by system (roof, HVAC, plumbing, electrical, foundation, etc.)
- Severity classification for each issue
- Estimated repair costs
- Urgency timeline
- Overall property condition score

## Severity Levels (in order of seriousness)

1. **safety** - Immediate safety hazards requiring urgent attention
   - Examples: Exposed wiring, gas leaks, structural instability, fire hazards, mold with health risk
   - Cost range: Varies, but must be addressed before purchase or immediately after

2. **major** - Significant issues requiring professional repair soon
   - Examples: Roof replacement needed, HVAC failure, foundation cracks, water intrusion
   - Cost range: Typically $5,000 - $30,000+

3. **moderate** - Notable issues that should be addressed within 1-2 years
   - Examples: Aging water heater, minor roof repairs, outdated electrical panel
   - Cost range: Typically $1,000 - $5,000

4. **minor** - Small issues that can be deferred
   - Examples: Caulking needs replacement, minor grading issues, weatherstripping
   - Cost range: Typically $100 - $1,000

5. **cosmetic** - Aesthetic issues only, no functional impact
   - Examples: Paint, minor drywall cracks, worn carpet
   - Cost range: Typically $0 - $500 per item

## Systems to Evaluate

- **Roof** - Condition, age, remaining life, leaks, flashing, gutters
- **Foundation** - Cracks, settling, moisture, drainage
- **Exterior** - Siding, trim, windows, doors, grading
- **Electrical** - Panel condition, wiring type, GFCI, code compliance
- **Plumbing** - Pipes, water heater, fixtures, water pressure, drainage
- **HVAC** - Age, condition, efficiency, maintenance history
- **Interior** - Walls, ceilings, floors, stairs, railings
- **Attic** - Insulation, ventilation, moisture, pests
- **Crawl Space/Basement** - Moisture, structure, insulation, pests

## Scoring Guidelines

Start at 70 (average condition) and adjust:

**Safety issues:** -25 per issue (cap at -50)
**Major issues:** -10 per issue
**Moderate issues:** -5 per issue
**Minor issues:** -2 per issue
**Cosmetic issues:** -0 (don't penalize)

**Positive adjustments:**
- Recently updated roof (< 5 years): +5
- New HVAC system: +5
- Updated electrical panel: +3
- No foundation issues: +5
- Overall well-maintained: +5

**Score interpretation:**
- 80-100: Excellent condition, minimal repairs needed
- 60-79: Good condition, typical maintenance items
- 40-59: Fair condition, significant repairs needed
- 20-39: Poor condition, major rehabilitation required
- 0-19: Severe issues, may not be financeable

## Cost Estimation Guidelines

When estimating costs, provide ranges and use these benchmarks:

- Roof replacement (asphalt, 2000 sqft): $8,000 - $15,000
- HVAC replacement: $5,000 - $12,000
- Water heater replacement: $1,000 - $2,500
- Electrical panel upgrade: $1,500 - $3,000
- Foundation repair (minor cracks): $2,000 - $5,000
- Foundation repair (major): $10,000 - $30,000
- Plumbing repipe: $5,000 - $15,000
- Window replacement (per window): $300 - $800
- Sewer line repair: $3,000 - $10,000

## Output Format

Return analysis as JSON:

```json
{
    "score": 72,
    "confidence": "high",
    "reasoning": "Property is in good overall condition with typical maintenance items. Roof is aging but serviceable. HVAC is newer.",
    "strengths": [
        "Updated electrical panel (2020)",
        "New HVAC system (2022)",
        "No foundation issues",
        "Well-maintained interior"
    ],
    "concerns": [
        "Roof approaching end of life (15 years old)",
        "Minor moisture in crawl space",
        "Water heater at end of service life"
    ],
    "details": {
        "issues": [
            {
                "system": "Roof",
                "description": "Asphalt shingles showing wear, estimated 5-7 years remaining",
                "severity": "moderate",
                "estimated_cost": "$8,000-$15,000",
                "urgency": "2-5 years"
            },
            {
                "system": "Plumbing",
                "description": "Water heater is 12 years old, showing corrosion",
                "severity": "minor",
                "estimated_cost": "$1,500-$2,500",
                "urgency": "1-2 years"
            }
        ],
        "total_estimated_repairs": "$10,000-$20,000",
        "immediate_repairs": "$0",
        "deferred_maintenance": "$10,000-$20,000",
        "systems_summary": {
            "roof": "aging but serviceable",
            "foundation": "excellent",
            "electrical": "updated",
            "plumbing": "good",
            "hvac": "excellent",
            "structure": "sound"
        }
    }
}
```

## Important Rules

1. **Be honest about issues** - Don't minimize real problems
2. **Use ranges for costs** - Never give single-point estimates
3. **Distinguish severity accurately** - Safety issues must be flagged as such
4. **Note what's NOT found** - Absence of issues in major systems is a strength
5. **Consider property age** - Adjust expectations based on year built
6. **Don't invent issues** - Only report what's in the inspection text
