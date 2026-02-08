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

Schools come from pre-extracted property data (passed as `property_data` kwarg).
The skill then enriches each school with GreatSchools data via `GreatSchoolsService`.

Each school starts with Redfin fields:
- `name`: School name
- `rating`: Rating out of 10
- `grades`: Grade levels (e.g., "K-5", "6-8", "9-12")
- `distance_miles`: Distance from property
- `type`: School type (elementary, middle, high)

After enrichment, schools may also have:
- `gs_rating`: GreatSchools summary rating (1-10)
- `gs_test_scores_rating`: Test Scores sub-rating (1-10)
- `gs_student_progress_rating`: Student Progress sub-rating (1-10)
- `gs_equity_rating`: Equity sub-rating (1-10)
- `gs_college_readiness_rating`: College Readiness (high schools only)
- `gs_test_scores`: `{subject: {school_pct, state_avg_pct}}` breakdown
- `gs_enrollment`: Student count
- `gs_student_teacher_ratio`: Student-teacher ratio
- `gs_review_count`: Number of parent reviews
- `gs_review_avg`: Average review stars
- `gs_url`: Link to GreatSchools page

### Step 2: Apply Analysis Framework

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

## Important Rules

### Missing Data
**NEVER list missing data as a concern.** "GreatSchools data unavailable", "distance not provided", or "private school not rated" are data limitations, NOT school quality issues. They affect confidence level, not score or concerns. Only list actual school quality issues as concerns.

### Uneven Strengths/Concerns
Strengths and concerns do NOT need to be balanced. Excellent schools might have 4 strengths and 0-1 concerns. Poor schools might have 1 strength and 4 concerns. Be honest — don't pad lists.

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

### Rating Interpretation (Redfin / Summary Rating)
- **9-10**: Top-tier school, highly competitive, excellent outcomes
- **8**: Very good school, strong academics, above-average performance
- **7**: Good school, solid academics, meets expectations
- **6**: Fair school, average performance, some concerns
- **5**: Below average, significant improvement needed
- **< 5**: Poor performance, serious concerns

### GreatSchools Sub-Rating Interpretation

When GreatSchools enrichment data is available, use sub-ratings for deeper analysis:

- **Test Scores Rating (1-10)**: Measures absolute proficiency — what percentage of students are meeting grade-level standards on state assessments. A high score means most students are proficient. This is the most commonly cited metric.
- **Student Progress Rating (1-10)**: Measures academic growth over time — how much students improve year-over-year regardless of starting point. A school with low test scores but high progress is actively improving. This is often more meaningful than raw test scores for assessing school quality.
- **Equity Rating (1-10)**: Measures the achievement gap between student subgroups (income, race, disability status). Higher = smaller gaps = more equitable outcomes across all students.
- **College Readiness Rating (1-10)**: High schools only. Based on AP course participation, SAT/ACT scores, graduation rates, and college enrollment. Missing for elementary/middle schools.

**Important notes:**
- GreatSchools data may be missing for private schools (they don't participate in state testing)
- Test score breakdowns by subject (with state averages) are more informative than summary ratings
- Student-teacher ratio below 20:1 is generally favorable; above 25:1 is a concern
- When Redfin rating and GS rating differ, GS is usually more current and detailed

### Key Factors to Consider
1. **Rating consistency**: Are all school levels similarly rated?
2. **Distance**: How accessible are the schools?
3. **School type**: Public vs private, magnet vs neighborhood
4. **Trends**: Is performance improving or declining? (Student Progress rating is key here)
5. **Capacity**: Are schools overcrowded or under-enrolled?
6. **Test scores vs state averages**: Schools above state average are doing well even if summary rating is moderate

### Red Flags
- All schools rated below 5
- High school rated significantly lower than elementary/middle
- No schools within 3 miles
- Large rating inconsistencies (9 elementary, 4 high)
- Low equity rating combined with low test scores
- Very high student-teacher ratio (>28:1)

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
