"""
Calculates and analyzes investment metrics for real estate properties.
"""

import json
import logging
from typing import Dict, Any
from ..base_tool import BaseTool

logger = logging.getLogger(__name__)


class CalculateInvestmentMetrics(BaseTool):
    """
    Calculates investment performance metrics using real estate investment methodology.

    Context: investment/investment_metrics.md
    Input: Property financials, rental data, market comparables
    Output: Comprehensive investment analysis with 10 key metrics
    """

    def __init__(self):
        super().__init__()
        # Load context on initialization
        self.load_context("investment/investment_metrics.md")

    async def analyze(self, data: Dict[str, Any], llm_client: Any) -> Dict[str, Any]:
        """
        Calculate investment metrics and provide analysis.

        Expected data structure:
        {
            "address": "123 Main St, City, State",
            "property_info": {
                "price": 450000,
                "bedrooms": 3,
                "bathrooms": 2,
                "square_feet": 1800,
                "property_type": "Single Family"
            },
            "financial_data": {
                "estimated_monthly_rent": 2800,
                "property_taxes_annual": 5400,
                "insurance_annual": 1200,
                "hoa_monthly": 0,
                "maintenance_annual_estimate": 4500,
                "property_management_percent": 10
            },
            "financing": {
                "down_payment_percent": 20,
                "interest_rate": 7.0,
                "loan_term_years": 30,
                "closing_costs": 9000
            },
            "market_data": {
                "median_price_neighborhood": 475000,
                "median_rent_neighborhood": 2750,
                "price_per_sqft": 250,
                "neighborhood_cap_rate_avg": 5.5,
                "appreciation_rate_5yr": 3.2
            }
        }
        """
        try:
            # Extract data
            property_info = data.get("property_info", {})
            financial_data = data.get("financial_data", {})
            financing = data.get("financing", {})
            market_data = data.get("market_data", {})

            if not property_info or "price" not in property_info:
                return {
                    "score": 0,
                    "grade": "F",
                    "confidence": "low",
                    "analysis": "Insufficient financial data for investment analysis.",
                    "key_findings": [],
                    "concerns": ["Missing critical property and financial information"],
                    "data_points": {}
                }

            # Pre-calculate some basic metrics to include in the prompt
            price = property_info.get("price", 0)
            monthly_rent = financial_data.get("estimated_monthly_rent", 0)
            annual_rent = monthly_rent * 12

            # Calculate GRM (Gross Rent Multiplier)
            grm = price / annual_rent if annual_rent > 0 else 0

            # Calculate down payment
            down_payment_pct = financing.get("down_payment_percent", 20) / 100
            down_payment = price * down_payment_pct
            loan_amount = price - down_payment

            # Calculate monthly mortgage payment
            interest_rate = financing.get("interest_rate", 7.0) / 100
            monthly_rate = interest_rate / 12
            num_payments = financing.get("loan_term_years", 30) * 12

            if monthly_rate > 0:
                monthly_mortgage = loan_amount * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)
            else:
                monthly_mortgage = 0

            # Calculate operating expenses
            annual_taxes = financial_data.get("property_taxes_annual", 0)
            annual_insurance = financial_data.get("insurance_annual", 0)
            annual_maintenance = financial_data.get("maintenance_annual_estimate", 0)
            monthly_hoa = financial_data.get("hoa_monthly", 0)
            pm_percent = financial_data.get("property_management_percent", 10) / 100

            annual_operating_expenses = (
                annual_taxes +
                annual_insurance +
                annual_maintenance +
                (monthly_hoa * 12) +
                (annual_rent * pm_percent)
            )

            # Calculate NOI
            noi = annual_rent - annual_operating_expenses

            # Calculate Cap Rate
            cap_rate = (noi / price * 100) if price > 0 else 0

            # Calculate Cash Flow
            annual_debt_service = monthly_mortgage * 12
            annual_cash_flow = noi - annual_debt_service
            monthly_cash_flow = annual_cash_flow / 12

            # Calculate Cash-on-Cash Return
            total_cash_invested = down_payment + financing.get("closing_costs", 0)
            coc_return = (annual_cash_flow / total_cash_invested * 100) if total_cash_invested > 0 else 0

            # Calculate DSCR
            dscr = noi / annual_debt_service if annual_debt_service > 0 else 0

            # Calculate LTV
            ltv = (loan_amount / price * 100) if price > 0 else 0

            # Add calculated metrics to data
            calculated_metrics = {
                "noi": round(noi, 2),
                "cap_rate": round(cap_rate, 2),
                "grm": round(grm, 2),
                "monthly_cash_flow": round(monthly_cash_flow, 2),
                "annual_cash_flow": round(annual_cash_flow, 2),
                "cash_on_cash_return": round(coc_return, 2),
                "dscr": round(dscr, 2),
                "ltv": round(ltv, 2),
                "monthly_mortgage": round(monthly_mortgage, 2),
                "total_cash_invested": round(total_cash_invested, 2),
                "annual_operating_expenses": round(annual_operating_expenses, 2)
            }

            # Create LLM instruction
            instruction = f"""
Analyze the investment potential of this property using the investment metrics methodology provided in the context.

I have pre-calculated the 10 key investment metrics:

1. NOI (Net Operating Income): ${calculated_metrics['noi']:,.2f}/year
2. Cap Rate: {calculated_metrics['cap_rate']:.2f}%
3. Cash Flow: ${calculated_metrics['monthly_cash_flow']:,.2f}/month (${calculated_metrics['annual_cash_flow']:,.2f}/year)
4. Cash-on-Cash Return: {calculated_metrics['cash_on_cash_return']:.2f}%
5. GRM (Gross Rent Multiplier): {calculated_metrics['grm']:.1f}
6. DSCR (Debt Service Coverage Ratio): {calculated_metrics['dscr']:.2f}
7. LTV (Loan-to-Value): {calculated_metrics['ltv']:.1f}%

Additional context:
- Total cash invested: ${calculated_metrics['total_cash_invested']:,.2f}
- Monthly mortgage: ${calculated_metrics['monthly_mortgage']:,.2f}
- Operating expenses: ${calculated_metrics['annual_operating_expenses']:,.2f}/year

Using the investment metrics context, provide comprehensive analysis covering:

1. **Investment Grade** (A-D scale from context):
   - A (Excellent): Cap rate 6%+, CoC 12%+, DSCR 1.3+
   - B (Good): Cap rate 5-6%, CoC 8-12%, DSCR 1.2-1.3
   - C (Fair): Cap rate 4-5%, CoC 5-8%, DSCR 1.1-1.2
   - D (Poor): Cap rate <4%, CoC <5%, DSCR <1.1

2. **Cash Flow Analysis**:
   - Is the monthly cash flow positive or negative?
   - Does it meet the $200-500+ monthly target?
   - What's the vacancy risk impact?

3. **Return Metrics**:
   - How does CoC return compare to alternative investments?
   - Is the cap rate appropriate for the market?
   - Compare to neighborhood average cap rate

4. **Risk Assessment**:
   - DSCR adequacy (lenders want 1.20-1.25 minimum)
   - LTV ratio and equity position
   - Cash flow sustainability

5. **Investment Strategy Fit**:
   - Buy and hold viability
   - Appreciation potential
   - Rental income reliability

Calculate an overall investment score (0-100) based on:
- Cash flow positivity (30%)
- Cash-on-cash return quality (25%)
- Cap rate competitiveness (20%)
- DSCR strength (15%)
- Market comparison (10%)

Provide specific recommendations and red flags.
"""

            # Create prompt with context
            enriched_data = {
                **data,
                "calculated_metrics": calculated_metrics
            }

            prompt = self.create_llm_prompt(instruction, enriched_data)

            # Call LLM for analysis (OpenAI format)
            response = await llm_client.chat.completions.create(
                model="gpt-4o",
                max_tokens=2500,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Parse response
            response_text = response.choices[0].message.content

            # Try to extract JSON from response
            result = self._parse_llm_response(response_text)

            # Add all calculated metrics to data points
            result["data_points"] = {
                **result.get("data_points", {}),
                **calculated_metrics
            }

            # Add raw data
            result["raw_data"] = {
                "property_info": property_info,
                "financial_data": financial_data,
                "financing": financing,
                "market_data": market_data
            }

            return result

        except Exception as e:
            logger.error(f"Error in investment metrics analysis: {e}")
            raise

    def _parse_llm_response(self, response_text: str) -> Dict[str, Any]:
        """Parse LLM response to extract JSON result."""
        try:
            # Try to find JSON in the response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                result = json.loads(json_str)
                return result
            else:
                # If no JSON found, create structured response
                return {
                    "score": 50,
                    "grade": "C",
                    "confidence": "low",
                    "analysis": response_text,
                    "key_findings": ["Analysis completed but structured data unavailable"],
                    "concerns": [],
                    "data_points": {}
                }

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from LLM response: {e}")
            return {
                "score": 50,
                "grade": "C",
                "confidence": "low",
                "analysis": response_text,
                "key_findings": ["Analysis completed but structured data unavailable"],
                "concerns": [],
                "data_points": {}
            }
