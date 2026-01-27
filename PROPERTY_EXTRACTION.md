# Property Data Extraction Guide

This document defines the standard process for extracting property data from Redfin screenshots for LLM analysis.

## Output Files

For each property analyzed, create two files in `property_data/`:

1. **JSON file** (`{address_slug}.json`) - Structured data for programmatic/LLM analysis
2. **Markdown file** (`{address_slug}.md`) - Human-readable summary

## Extraction Process

### Step 1: Screenshot Collection

Capture full-page screenshots from Redfin property pages at these scroll positions:

| Position | Section | Key Data |
|----------|---------|----------|
| 0-700px | Overview | Photos, address, price, beds/baths/sqft, status |
| 700-1400px | About This Home | **Description**, property type, year built, lot size |
| 1400-2100px | Redfin Estimate | Current estimate, appreciation, comps |
| 2100-2800px | Sale Earnings | Mortgage, closing costs, profit estimate |
| 2800-3500px | Market Trends | Market type, sale-to-list, median price, DOM |
| 3500-4200px | Sale/Tax History | Rental estimate, sale history, tax history |
| 4200-7000px | Property Details | Parking, interior, exterior, utilities, schools |
| 7000-8400px | Neighborhood | Map, schools detail, lifestyle scores |
| 8400-9800px | Climate | Flood, fire, heat, wind, air quality risks |
| 9800-12000px | Similar Homes | Nearby listings, home values |
| 12000px+ | Footer | Listing info, MLS data, disclaimers |

### Step 2: Data Extraction Categories

Extract data in these categories (see `property_extraction_schema.json` for full schema):

#### Required Categories
- `property` - Address, status, **description** (from "About this home")
- `pricing` - Sale history, estimates, price/sqft, rental estimate
- `property_details` - Type, year, beds, baths, sqft, lot size
- `parking` - Garage spaces, type
- `interior` - Rooms, features, appliances
- `heating_cooling` - HVAC info
- `hoa` - Fees and frequency
- `taxes` - Current and historical
- `schools` - District, ratings, distances
- `lifestyle_scores` - Walk/bike/transit scores
- `climate_risks` - All 5 factors
- `market_trends` - Local market context

#### Optional Categories
- `construction` - Builder, materials, foundation
- `utilities` - Providers, connections
- `green_features` - Energy efficiency
- `exterior_features` - Views, lot features
- `comparable_sales` - Recent nearby sales
- `financial_analysis` - Profit projections

### Step 3: Save Extracted Data

```
property_data/
├── {address_slug}.json    # Full structured data
└── {address_slug}.md      # Human-readable summary
```

Example naming: `522_glacier_walk_se.json`

## JSON Structure

```json
{
  "extraction_metadata": {
    "source": "Redfin",
    "extraction_date": "YYYY-MM-DD",
    "screenshots_analyzed": 22
  },
  "property": {
    "address": {...},
    "listing_status": {...},
    "description": "Full listing description text"
  },
  "pricing": {...},
  "property_details": {...},
  // ... all other categories
}
```

## Key Fields Often Missed

1. **Description** - The "About this home" narrative text
2. **Rental Estimate** - Monthly rental value
3. **Climate Risks** - All 5 factors from First Street
4. **Lifestyle Scores** - Walk Score data
5. **Tax History** - Multi-year trend
6. **Comparable Sales** - Recent nearby transactions

## Usage for LLM Analysis

The extracted JSON files can be used for:

- Investment analysis (appreciation, rental yield)
- Location quality assessment (schools, walkability)
- Risk evaluation (climate, market conditions)
- Comparative analysis across properties
- Automated report generation

Load the JSON and pass to LLM with specific analysis prompts.
