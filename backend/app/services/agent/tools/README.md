# Granular Analysis Tools Architecture

## Overview

This directory contains the **granular tool architecture** for property analysis. Instead of using a single large system prompt with broad tools, this system breaks down analysis into 40+ specialized tools, each focused on one specific aspect of property evaluation.

### Key Benefits

1. **Focused Analysis**: Each tool analyzes one specific aspect (e.g., school quality, crime risk, investment metrics)
2. **Context-Driven**: Each tool loads its own methodology/context from markdown files
3. **Scalable**: Easy to add new tools without modifying existing code
4. **Maintainable**: Each tool is self-contained with clear inputs/outputs
5. **Transparent**: Each tool documents its methodology and reasoning

## Architecture

```
tools/
├── base_tool.py                    # Base class for all tools
├── tool_registry.py                # Central registry for tool discovery
├── tool_orchestrator.py            # Coordinates multi-tool execution
│
├── property_quality/               # Category: Property condition tools
│   └── (future tools)
│
├── location_commute/               # Category: Location & accessibility tools
│   ├── analyze_walkability.py      # Walk/Transit/Bike score analysis
│   └── (future tools)
│
├── neighborhood/                   # Category: Neighborhood quality tools
│   ├── analyze_crime_risk.py       # Crime risk assessment
│   └── (future tools)
│
├── education/                      # Category: School quality tools
│   ├── analyze_school_quality.py   # GreatSchools rating analysis
│   └── (future tools)
│
├── environmental/                  # Category: Environmental risk tools
│   └── (future tools)
│
└── investment/                     # Category: Financial analysis tools
    ├── calculate_investment_metrics.py  # 10 key investment metrics
    └── (future tools)

context_prompts/
├── education/
│   └── greatschools_methodology.md
├── neighborhood/
│   └── crime_risk_assessment.md
├── location_commute/
│   └── walkability_scores.md
└── investment/
    └── investment_metrics.md
```

## Core Components

### 1. BaseTool (base_tool.py)

Abstract base class that all tools inherit from.

**Key Methods:**
- `load_context(file_path)` - Loads methodology from markdown file
- `create_llm_prompt(instruction, data)` - Combines context + instruction + data
- `analyze(data, llm_client)` - Performs the analysis (implemented by each tool)
- `execute(data, llm_client)` - Main execution method with validation
- `validate_result(result)` - Ensures consistent output structure

**Expected Output Structure:**
```python
{
    "tool_name": str,
    "score": float (0-100),
    "grade": str (A-F),
    "confidence": str (high/medium/low),
    "analysis": str,
    "key_findings": List[str],
    "concerns": List[str],
    "data_points": Dict[str, Any],
    "raw_data": Dict[str, Any]
}
```

### 2. ToolRegistry (tool_registry.py)

Central registry for discovering and managing tools.

**Key Methods:**
- `register_tool(name, tool_class, category)` - Register a new tool
- `get_tool(name)` - Get instance of specific tool
- `get_tools_by_category(category)` - Get all tools in category
- `list_tool_names(category=None)` - List available tools
- `get_category_summary()` - Get tool count per category

**Usage:**
```python
from app.services.agent.tools.tool_registry import get_tool_registry

registry = get_tool_registry()
school_tool = registry.get_tool("analyze_school_quality")
```

### 3. ToolOrchestrator (tool_orchestrator.py)

Coordinates execution of multiple tools and aggregates results.

**Key Methods:**
- `analyze_property(property_data)` - Run comprehensive analysis
- `set_progress_callback(callback)` - Set progress tracking callback
- `_determine_applicable_tools(data)` - Auto-detect which tools to run
- `_execute_tools(tools, data)` - Execute tools in parallel
- `_aggregate_results(results, data)` - Combine into final report

**Usage:**
```python
from app.services.agent.tools.tool_orchestrator import ToolOrchestrator

orchestrator = ToolOrchestrator(llm_client)
orchestrator.set_progress_callback(lambda msg, pct: print(f"{pct}% {msg}"))

report = await orchestrator.analyze_property(property_data)
```

## Implemented Tools

### Education Tools

#### AnalyzeSchoolQuality
- **Context**: `education/greatschools_methodology.md`
- **Purpose**: Analyzes school quality using GreatSchools 1-10 rating system
- **Methodology**:
  - Evaluates Student Progress rating (highest weight)
  - Considers College Readiness and Test Score ratings
  - Factors distance to schools (walking distance is premium)
  - Compares to district/state averages
  - Assesses impact on home value
- **Input**: List of nearby schools with ratings, types, distances
- **Output**: Score 0-100 based on school quality and accessibility

### Neighborhood Tools

#### AnalyzeCrimeRisk
- **Context**: `neighborhood/crime_risk_assessment.md`
- **Purpose**: Assesses crime risk using NeighborhoodScout 1-100 scale
- **Methodology**:
  - Evaluates overall crime risk (100 = safest)
  - Separates violent vs. property crime
  - Analyzes crime trends (improving/stable/declining)
  - Compares to city and national averages
  - Calculates home value impact (high crime can reduce 10-30%)
- **Input**: Crime statistics, risk ratings, trend data
- **Output**: Score 0-100 reflecting neighborhood safety

### Location & Commute Tools

#### AnalyzeWalkability
- **Context**: `location_commute/walkability_scores.md`
- **Purpose**: Evaluates walkability, transit, and bike infrastructure
- **Methodology**:
  - Interprets Walk Score 0-100 (90-100 = Walker's Paradise)
  - Evaluates Transit Score and service frequency
  - Assesses Bike Score and infrastructure quality
  - Identifies nearby amenities and distances
  - Determines lifestyle fit for different buyer profiles
- **Input**: Walk/Transit/Bike scores, amenities, transit options
- **Output**: Score 0-100 for overall mobility and accessibility

### Investment Tools

#### CalculateInvestmentMetrics
- **Context**: `investment/investment_metrics.md`
- **Purpose**: Calculates 10 key real estate investment metrics
- **Metrics Calculated**:
  1. NOI (Net Operating Income)
  2. Cap Rate (4-12% typical range)
  3. Cash Flow (monthly and annual)
  4. Cash-on-Cash Return (8-20%+ target)
  5. GRM (Gross Rent Multiplier, 4-15 range)
  6. IRR (Internal Rate of Return, 10-20%)
  7. DSCR (Debt Service Coverage, >1.25 ideal)
  8. LTV (Loan-to-Value, 70-80% target)
  9. ROI (Return on Investment)
  10. Occupancy Rate (90-100% ideal)
- **Methodology**:
  - Pre-calculates financial metrics using formulas
  - LLM interprets metrics using investment grade scale (A-D)
  - Assesses cash flow sustainability
  - Evaluates investment strategy fit
- **Input**: Property price, rental estimates, financials, market data
- **Output**: Score 0-100 with investment grade (A-D) and detailed metrics

## How to Create a New Tool

### Step 1: Create Context Prompt File

Create a markdown file in `context_prompts/<category>/` with methodology:

```markdown
# Tool Name - Methodology

## Overview
Brief description of what this tool analyzes.

## Rating Scale
- Define the scoring scale (e.g., 1-10, 0-100)
- Interpretation of each range

## Key Metrics
- List of metrics to evaluate
- How to interpret each metric

## Analysis Guidelines
- What to look for
- Red flags vs. positive indicators
- How to weight different factors

## Context for Interpretation
- Comparison benchmarks
- Buyer profile considerations
- Impact on home value
```

### Step 2: Create Tool Class

Create a Python file in `tools/<category>/`:

```python
from typing import Dict, Any
from ..base_tool import BaseTool

class YourToolName(BaseTool):
    """
    Brief description of what this tool does.

    Context: category/your_context_file.md
    Input: Description of expected input data
    Output: Description of output structure
    """

    def __init__(self):
        super().__init__()
        # Load context on initialization
        self.load_context("category/your_context_file.md")

    async def analyze(self, data: Dict[str, Any], llm_client: Any) -> Dict[str, Any]:
        """
        Perform the analysis.

        Args:
            data: Input data specific to this analysis
            llm_client: LLM client for making API calls

        Returns:
            Analysis result following standard structure
        """
        # 1. Extract relevant data
        relevant_data = data.get("your_data_key", {})

        if not relevant_data:
            return {
                "score": 0,
                "grade": "F",
                "confidence": "low",
                "analysis": "No data available for analysis.",
                "key_findings": [],
                "concerns": ["Missing required data"],
                "data_points": {}
            }

        # 2. Create instruction for LLM
        instruction = """
        Analyze the [aspect] using the methodology in the context.

        Consider:
        1. [Key factor 1]
        2. [Key factor 2]
        3. [Key factor 3]

        Calculate a score (0-100) based on [criteria].
        """

        # 3. Create prompt with context
        prompt = self.create_llm_prompt(instruction, data)

        # 4. Call LLM
        response = await llm_client.create_message(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        # 5. Parse and return result
        result = self._parse_llm_response(response.content[0].text)
        result["raw_data"] = relevant_data

        return result

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response to extract JSON result."""
        # Implementation similar to existing tools
        # Extract JSON from response
        # Handle parsing errors gracefully
        pass
```

### Step 3: Register Tool

Add to `tools/<category>/__init__.py`:

```python
from .your_tool_name import YourToolName

__all__ = ["YourToolName", ...]
```

Add to `tool_registry.py` in `_register_default_tools()`:

```python
self.register_tool("your_tool_name", YourToolName, "category")
```

### Step 4: Update Orchestrator (if needed)

If the tool should run automatically, add logic to `tool_orchestrator.py`:

```python
def _determine_applicable_tools(self, property_data: Dict[str, Any]) -> List[tuple[str, BaseTool]]:
    # Add condition for your tool
    if property_data.get("your_data_type"):
        tool = self.registry.get_tool("your_tool_name")
        if tool:
            tools_to_run.append(("your_tool_name", tool))
```

## Notes-Based Analysis System

### Overview

Instead of keeping all analysis data in memory, the system writes incremental results to markdown notes files. This provides:

1. **Memory Efficiency**: No large objects held in RAM during analysis
2. **Transparency**: Inspect intermediate results in human-readable markdown
3. **Resumability**: Continue from checkpoint if analysis fails
4. **Caching**: Reuse previous analysis for same address (instant results)
5. **Auditability**: Keep history in S3 for compliance/review

### How It Works

**File Naming:**
- Address normalized to filename: `"522 Glacier Walk SE"` → `522_glacier_walk_se.md`
- Stored in `backend/analysis_notes/` directory

**Development Mode:**
- Notes files kept in local directory for debugging
- Can inspect intermediate results
- Perfect for development and testing

**Production Mode:**
- Notes uploaded to S3 after analysis completes
- Local notes file deleted after successful upload
- S3 location: `s3://bucket/analysis_notes/2025/01/522_glacier_walk_se.md`

**Note Reuse:**
- When analyzing same address again, checks for existing notes
- If found, parses notes and returns cached report (instant)
- Skips expensive LLM calls and data collection
- Saves time and money

### Notes File Structure

```markdown
# Property Analysis Notes

**Address:** 522 Glacier Walk SE
**Analysis Date:** 2025-01-15 14:30:00
**Status:** In Progress

---

## Property Information

- Price: $450,000
- Bedrooms: 3
- Bathrooms: 2

---

## Analyze School Quality

**Metadata:**
- Tool: analyze_school_quality
- Timestamp: 14:30:15
- Context File: .../education/greatschools_methodology.md

**Score:** 85/100
**Grade:** B
**Confidence:** high

### Analysis

Lincoln Elementary (rating 8/10) is within ideal walking distance...

### Key Findings

- ✓ Elementary school highly rated (8/10)
- ✓ Walking distance to school (0.3 miles)

### Concerns

- ⚠️ Middle school rating below average (6/10)

### Key Data Points

- School Breakdown: {"elementary": [...], "middle": [...]}

---

## Analyze Crime Risk

[... more tool results ...]

---

## Final Summary

**Overall Score:** 82/100
**Overall Grade:** B

### Category Scores

- Education: 85/100
- Neighborhood: 75/100
- Location Commute: 90/100
- Investment: 78/100

### Recommendation

Good property with solid performance in most areas...
```

## Running Analysis

### Option 1: Use Orchestrator (Recommended)

```python
from app.services.agent.tools.tool_orchestrator import ToolOrchestrator
from anthropic import AsyncAnthropic

# Initialize
llm_client = AsyncAnthropic(api_key="your-key")
orchestrator = ToolOrchestrator(
    llm_client,
    environment="development",  # or "production"
    reuse_notes=True  # Enable caching
)

# Optional progress tracking
def progress_callback(message: str, progress: int):
    print(f"[{progress}%] {message}")

orchestrator.set_progress_callback(progress_callback)

# Run analysis
property_data = {
    "address": "522 Glacier Walk SE",
    "schools": [...],
    "crime_data": {...},
    "walkability_data": {...},
    # ... other data
}

# First run: Creates notes file and runs full analysis
report = await orchestrator.analyze_property(property_data)

print(f"Overall Score: {report['overall_score']}/100")
print(f"Grade: {report['overall_grade']}")

# Second run with same address: Loads from cached notes (instant!)
report2 = await orchestrator.analyze_property(property_data)
print(f"Cached: {report2['metadata']['cached']}")  # True
```

### Option 2: Use Individual Tools

```python
from app.services.agent.tools.tool_registry import get_tool_registry
from anthropic import AsyncAnthropic

# Get tool
registry = get_tool_registry()
school_tool = registry.get_tool("analyze_school_quality")

# Prepare data
data = {
    "address": "123 Main St",
    "schools": [
        {"name": "Lincoln Elementary", "rating": 8, "distance_miles": 0.3, ...}
    ]
}

# Execute
llm_client = AsyncAnthropic(api_key="your-key")
result = await school_tool.execute(data, llm_client)

print(f"School Quality Score: {result['score']}/100")
print(f"Analysis: {result['analysis']}")
```

## Example Usage

See `granular_analysis_example.py` for a complete working example with:
- Example property data structure
- Progress tracking
- Full analysis with all tools
- Result interpretation

Run the example:
```bash
cd backend
python -m app.services.agent.granular_analysis_example
```

## Future Tools to Implement

### Property Quality Category (7 tools)
- [ ] analyze_property_type - Evaluate property type pros/cons
- [ ] analyze_foundation - Foundation type and condition
- [ ] analyze_roofing - Roof material, age, condition
- [ ] analyze_hvac - HVAC system quality and age
- [ ] analyze_plumbing_electrical - System condition
- [ ] analyze_interior_condition - Interior quality assessment
- [ ] analyze_kitchen_bathrooms - Kitchen/bath quality

### Location & Commute (3 more tools)
- [ ] calculate_commute_times - Commute analysis
- [ ] analyze_highway_access - Highway proximity and noise
- [ ] evaluate_nearby_essentials - Grocery, pharmacy, services

### Neighborhood (2 more tools)
- [ ] analyze_noise_levels - Noise pollution assessment
- [ ] evaluate_community_character - Neighborhood vibe

### Environmental (5 tools)
- [ ] assess_flood_risk - Flood zone and risk analysis
- [ ] assess_earthquake_risk - Seismic hazard evaluation
- [ ] assess_wildfire_risk - Fire danger assessment
- [ ] analyze_air_quality - AQI and pollution levels
- [ ] evaluate_climate_risks - Long-term climate impact

### Investment (5 more tools)
- [ ] compare_market_comps - Comparable properties analysis
- [ ] analyze_price_history - Historical pricing trends
- [ ] evaluate_rental_potential - Rental income assessment
- [ ] calculate_appreciation_forecast - Future value projection
- [ ] assess_carrying_costs - Ongoing cost analysis

### Legal & Regulatory (3 tools)
- [ ] analyze_zoning - Zoning regulations and permitted uses
- [ ] evaluate_hoa_rules - HOA restrictions and fees
- [ ] check_permits_compliance - Permit history and issues

## Testing

Create tests in `tests/test_tools/`:

```python
import pytest
from app.services.agent.tools.education import AnalyzeSchoolQuality

@pytest.mark.asyncio
async def test_school_quality_analysis():
    tool = AnalyzeSchoolQuality()

    data = {
        "schools": [
            {"name": "Test School", "rating": 8, "distance_miles": 0.3}
        ]
    }

    result = await tool.execute(data, mock_llm_client)

    assert result["score"] >= 0
    assert result["score"] <= 100
    assert result["grade"] in ["A", "B", "C", "D", "F"]
    assert "analysis" in result
```

## Performance Considerations

- **Parallel Execution**: Orchestrator runs independent tools in parallel
- **Context Caching**: Context files loaded once per tool instance
- **LLM Costs**: Each tool makes 1-2 LLM API calls (~$0.02-0.05 per tool)
- **Total Analysis Cost**: ~$0.10-0.20 for all 4 current tools
- **Execution Time**: 10-30 seconds for complete analysis (parallel execution)

## Migration from Old System

The old system used:
- Single large system prompt
- 11 broad tools (scrape_zillow, get_school_ratings, etc.)
- OpenAI function calling
- One big analysis in one LLM call

The new system uses:
- 40+ specialized tools
- Each tool has focused context
- Claude for analysis (better at reasoning)
- Parallel execution with aggregation

**Benefits of Migration:**
- More accurate analysis (specialized context per tool)
- Better transparency (each tool explains its reasoning)
- Easier to maintain (add/modify tools independently)
- Scalable (add new tools without touching existing code)
- Cost-efficient (smaller, focused prompts)
