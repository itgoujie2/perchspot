"""
Prompt templates for Claude AI analysis
"""

# System prompts
PROPERTY_ANALYST_SYSTEM = """You are a professional real estate analyst and property inspector with 20+ years of experience. You provide detailed, objective assessments of properties based on available data and images."""

MARKET_ANALYST_SYSTEM = """You are an experienced real estate market analyst and investment advisor. You analyze market trends, property values, and investment potential with data-driven insights."""

EDUCATION_ANALYST_SYSTEM = """You are an education consultant specializing in school quality assessment and family relocation advice."""


# Property Condition Analysis Template
PROPERTY_CONDITION_PROMPT = """Analyze this property's condition based on the provided information and images.

PROPERTY INFORMATION:
Address: {address}
Year Built: {year_built}
Square Footage: {sqft}
Property Type: {property_type}
Description: {description}

IMAGES PROVIDED:
{image_count} property photos including exterior, interior, and key rooms

ANALYSIS TASK:
Provide a comprehensive assessment of the property's physical condition. Analyze:

1. **Exterior Condition** (0-100):
   - Overall appearance and curb appeal
   - Roof condition (look for age, wear, missing shingles)
   - Siding/exterior walls (paint, damage, maintenance)
   - Foundation (visible cracks, settling)
   - Landscaping and grounds

2. **Interior Condition** (0-100):
   - Floors (condition, quality, wear)
   - Walls and ceilings (paint, damage, water stains)
   - Overall maintenance level
   - Cleanliness and presentation

3. **Kitchen & Bathrooms** (0-100):
   - Appliances (age, condition, quality)
   - Fixtures and fittings
   - Countertops and cabinets
   - Overall functionality and modernity

4. **Systems & Infrastructure** (0-100):
   - HVAC age and condition (from description or visible units)
   - Electrical (outlets, fixtures visible)
   - Plumbing (fixtures, potential issues)
   - Windows and doors

SCORING GUIDELINES:
- 90-100: Excellent condition, recently updated, minimal maintenance needed
- 75-89: Good condition, well-maintained, minor updates may be desired
- 60-74: Average condition, normal wear, some updates recommended
- 45-59: Fair condition, visible wear, updates needed soon
- 0-44: Poor condition, significant issues, major repairs required

Respond in this exact JSON format:
{{
  "overall_score": <0-100>,
  "sub_scores": {{
    "exterior": <0-100>,
    "interior": <0-100>,
    "kitchen_bath": <0-100>,
    "systems": <0-100>
  }},
  "reasoning": "<detailed explanation of assessment>",
  "highlights": ["<positive aspect 1>", "<positive aspect 2>", ...],
  "concerns": ["<concern 1>", "<concern 2>", ...],
  "maintenance_priorities": ["<priority 1>", "<priority 2>", ...],
  "estimated_repair_costs": "<rough estimate if major issues found>",
  "confidence": "<high|medium|low>"
}}

Be objective and thorough. Base your assessment on visible evidence."""


# Location Quality Analysis Template
LOCATION_QUALITY_PROMPT = """Analyze the location quality for this property.

PROPERTY LOCATION:
Address: {address}
City: {city}
State: {state}
ZIP Code: {zip_code}

NEIGHBORHOOD DATA:
{neighborhood_data}

NEARBY AMENITIES:
{amenities_data}

ANALYSIS TASK:
Provide a comprehensive location quality assessment covering:

1. **Neighborhood Quality** (0-100):
   - Safety and crime rates (if data available)
   - Housing market stability
   - Community character and appeal
   - Future development prospects

2. **Amenities Access** (0-100):
   - Grocery stores and shopping (within 1 mile)
   - Restaurants and entertainment
   - Parks and recreation
   - Healthcare facilities
   - Overall convenience

3. **Transportation** (0-100):
   - Public transit access and quality
   - Major highway/freeway access
   - Commute times to employment centers
   - Walkability for daily errands

4. **Overall Livability** (0-100):
   - Quality of life factors
   - Environmental quality (noise, air quality)
   - Community services
   - Growth potential

SCORING GUIDELINES:
- 90-100: Premium location, highly desirable, excellent access to everything
- 75-89: Very good location, good amenities, convenient
- 60-74: Good location, adequate amenities, some limitations
- 45-59: Average location, basic amenities, may require driving
- 0-44: Below average location, limited amenities, inconvenient

Respond in this exact JSON format:
{{
  "overall_score": <0-100>,
  "sub_scores": {{
    "neighborhood": <0-100>,
    "amenities": <0-100>,
    "transportation": <0-100>,
    "livability": <0-100>
  }},
  "reasoning": "<detailed explanation>",
  "nearby_amenities": ["<amenity 1>", "<amenity 2>", ...],
  "transit_options": ["<option 1>", "<option 2>", ...],
  "strengths": ["<strength 1>", "<strength 2>", ...],
  "limitations": ["<limitation 1>", "<limitation 2>", ...],
  "confidence": "<high|medium|low>"
}}"""


# School Analysis Template
SCHOOL_ANALYSIS_PROMPT = """Analyze the school quality for families considering this property.

PROPERTY LOCATION:
Address: {address}
City: {city}, {state} {zip_code}

NEARBY SCHOOLS:
{schools_data}

ANALYSIS TASK:
Assess the educational opportunities available to families at this location:

1. **Overall School Quality** (0-100):
   - Average ratings of nearby schools
   - Variety of school options (public, charter, private)
   - Special programs and opportunities

2. **School Access** (0-100):
   - Proximity to quality schools
   - Transportation options
   - Elementary, middle, and high school coverage

3. **Educational Environment** (0-100):
   - Teacher quality and resources
   - Student-teacher ratios
   - Extracurricular opportunities
   - School facilities and technology

SCORING GUIDELINES:
- 90-100: Excellent schools, top-rated district, many options
- 75-89: Very good schools, strong district, good options
- 60-74: Good schools, solid district, adequate options
- 45-59: Average schools, basic education, limited options
- 0-44: Below average schools, weak district, few options

Respond in this exact JSON format:
{{
  "overall_score": <0-100>,
  "schools": [
    {{
      "name": "<school name>",
      "type": "<elementary|middle|high>",
      "rating": <0-10>,
      "distance_miles": <distance>,
      "assessment": "<brief assessment>"
    }}
  ],
  "reasoning": "<detailed explanation>",
  "highlights": ["<positive 1>", "<positive 2>", ...],
  "concerns": ["<concern 1>", "<concern 2>", ...],
  "recommendation": "<recommendation for families>",
  "confidence": "<high|medium|low>"
}}

Consider both quantity and quality of schools. Distance matters - closer is better."""


# Investment Value Analysis Template
INVESTMENT_VALUE_PROMPT = """Analyze the investment potential of this property.

PROPERTY DETAILS:
Address: {address}
Listed Price: ${price}
Bedrooms: {bedrooms}
Bathrooms: {bathrooms}
Square Feet: {sqft}
Year Built: {year_built}
Property Type: {property_type}

COMPARABLE PROPERTIES:
{comparables_data}

MARKET DATA:
{market_data}

ANALYSIS TASK:
Provide an investment analysis covering:

1. **Price vs Market** (0-100):
   - Price per square foot vs comparables
   - Position in market (below/at/above market)
   - Negotiation potential
   Score: 100 = significantly below market, 50 = fair market value, 0 = overpriced

2. **Appreciation Potential** (0-100):
   - Historical price trends in area
   - Development and growth indicators
   - Market momentum
   - Future value prospects

3. **Rental Income Potential** (0-100):
   - Estimated rental yield
   - Rental demand in area
   - Cash flow potential
   - Landlord-friendliness

4. **Overall Investment Quality** (0-100):
   - Risk-adjusted returns
   - Holding period considerations
   - Exit strategy potential
   - Market timing

SCORING GUIDELINES:
- 90-100: Excellent investment, strong upside, low risk
- 75-89: Very good investment, good returns expected
- 60-74: Fair investment, moderate returns
- 45-59: Below average investment, limited upside
- 0-44: Poor investment, high risk or overpriced

Respond in this exact JSON format:
{{
  "overall_score": <0-100>,
  "sub_scores": {{
    "price_value": <0-100>,
    "appreciation": <0-100>,
    "rental_potential": <0-100>,
    "investment_quality": <0-100>
  }},
  "reasoning": "<detailed analysis>",
  "price_per_sqft": <calculated value>,
  "market_comparison": "<below|at|above> market by X%",
  "estimated_rental_income": "<monthly estimate if applicable>",
  "estimated_appreciation": "<annual % estimate>",
  "pros": ["<pro 1>", "<pro 2>", ...],
  "cons": ["<con 1>", "<con 2>", ...],
  "recommendations": ["<recommendation 1>", "<recommendation 2>", ...],
  "risk_factors": ["<risk 1>", "<risk 2>", ...],
  "confidence": "<high|medium|low>"
}}

Be realistic and data-driven. Consider both short and long-term perspectives."""


def format_property_condition_prompt(property_data: dict, image_count: int) -> str:
    """Format property condition analysis prompt"""
    return PROPERTY_CONDITION_PROMPT.format(
        address=property_data.get('address', 'Unknown'),
        year_built=property_data.get('year_built', 'Unknown'),
        sqft=property_data.get('square_feet', 'Unknown'),
        property_type=property_data.get('property_type', 'Unknown'),
        description=property_data.get('description', 'No description available'),
        image_count=image_count
    )


def format_location_quality_prompt(property_data: dict, neighborhood_data: str, amenities_data: str) -> str:
    """Format location quality analysis prompt"""
    return LOCATION_QUALITY_PROMPT.format(
        address=property_data.get('address', 'Unknown'),
        city=property_data.get('city', 'Unknown'),
        state=property_data.get('state', 'Unknown'),
        zip_code=property_data.get('zip_code', 'Unknown'),
        neighborhood_data=neighborhood_data,
        amenities_data=amenities_data
    )


def format_school_analysis_prompt(property_data: dict, schools_data: str) -> str:
    """Format school analysis prompt"""
    return SCHOOL_ANALYSIS_PROMPT.format(
        address=property_data.get('address', 'Unknown'),
        city=property_data.get('city', 'Unknown'),
        state=property_data.get('state', 'Unknown'),
        zip_code=property_data.get('zip_code', 'Unknown'),
        schools_data=schools_data
    )


def format_investment_analysis_prompt(property_data: dict, comparables_data: str, market_data: str) -> str:
    """Format investment analysis prompt"""
    return INVESTMENT_VALUE_PROMPT.format(
        address=property_data.get('address', 'Unknown'),
        price=property_data.get('price', 'Unknown'),
        bedrooms=property_data.get('bedrooms', 'Unknown'),
        bathrooms=property_data.get('bathrooms', 'Unknown'),
        sqft=property_data.get('square_feet', 'Unknown'),
        year_built=property_data.get('year_built', 'Unknown'),
        property_type=property_data.get('property_type', 'Unknown'),
        comparables_data=comparables_data,
        market_data=market_data
    )
