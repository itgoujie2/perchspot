"""
Investment value analyzer
"""
import logging
from typing import Dict, Any, List

from app.config import settings
from app.services.llm_services.openai_client import OpenAIClient
from app.services.llm_services.prompt_templates import (
    format_investment_analysis_prompt,
    MARKET_ANALYST_SYSTEM
)

logger = logging.getLogger(__name__)


class InvestmentValueAnalyzer:
    """
    Analyze investment potential and market value
    """

    def __init__(self, llm_client: OpenAIClient = None):
        self.llm = llm_client or OpenAIClient()

    async def analyze(
        self,
        property_data: Dict[str, Any],
        comparables: List[Dict[str, Any]] = None,
        market_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze investment value

        Args:
            property_data: Property information
            comparables: List of comparable properties
            market_data: Market trends and data

        Returns:
            Analysis result with scores and insights
        """
        try:
            logger.info(f"Analyzing investment value for {property_data.get('address')}")

            # Format data for prompt
            comparables_str = self._format_comparables_data(comparables or [])
            market_str = self._format_market_data(market_data or {})

            # Format prompt
            prompt = format_investment_analysis_prompt(
                property_data=property_data,
                comparables_data=comparables_str,
                market_data=market_str
            )

            # Call OpenAI API
            result = await self.llm.analyze_text(
                prompt=prompt,
                system_prompt=MARKET_ANALYST_SYSTEM,
                model=settings.LLM_MODEL  # Use GPT-4o for complex financial analysis
            )

            # Extract analysis
            analysis = result['response']

            # Validate response
            required_fields = ['overall_score', 'reasoning', 'confidence']
            if not all(field in analysis for field in required_fields):
                logger.error(f"Invalid analysis response: {analysis}")
                raise ValueError("Analysis response missing required fields")

            # Add metadata
            analysis['llm_cost'] = result.get('cost', 0)
            analysis['tokens_used'] = result.get('usage', {}).get('total_tokens', 0)
            analysis['model'] = result.get('model')

            logger.info(
                f"Investment analysis complete: "
                f"score={analysis['overall_score']}, cost=${analysis['llm_cost']:.4f}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing investment value: {e}", exc_info=True)
            # Try rule-based analysis
            return self._rule_based_analysis(property_data, comparables or [])

    def _format_comparables_data(self, comparables: List[Dict[str, Any]]) -> str:
        """Format comparable properties data"""
        if not comparables:
            return "No comparable properties data available"

        formatted = []
        for comp in comparables[:5]:  # Limit to 5 comps
            comp_str = f"""
Address: {comp.get('address', 'Unknown')}
Price: ${comp.get('price', 0):,.0f}
Square Feet: {comp.get('square_feet', 0):,}
Price/SqFt: ${comp.get('price_per_sqft', 0):.0f}
Bedrooms: {comp.get('bedrooms', 'N/A')}
Bathrooms: {comp.get('bathrooms', 'N/A')}
Distance: {comp.get('distance_miles', 'N/A')} miles
"""
            formatted.append(comp_str.strip())

        return "\n\n".join(formatted)

    def _format_market_data(self, market_data: Dict[str, Any]) -> str:
        """Format market trends data"""
        if not market_data:
            return "Limited market data available"

        formatted = []
        for key, value in market_data.items():
            formatted.append(f"- {key}: {value}")

        return "\n".join(formatted) if formatted else "No market data available"

    def _rule_based_analysis(
        self,
        property_data: Dict[str, Any],
        comparables: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Rule-based investment analysis

        Calculate score based on:
        - Price per sqft vs market
        - Property age and condition
        - Location factors
        """
        logger.info("Using rule-based investment analysis")

        price = property_data.get('price', 0)
        sqft = property_data.get('square_feet', 1)
        price_per_sqft = price / sqft if sqft > 0 else 0

        # Calculate market average price per sqft
        if comparables:
            comp_prices_per_sqft = [
                c.get('price_per_sqft', 0) for c in comparables
                if c.get('price_per_sqft', 0) > 0
            ]
            avg_comp_price_per_sqft = (
                sum(comp_prices_per_sqft) / len(comp_prices_per_sqft)
                if comp_prices_per_sqft else price_per_sqft
            )
        else:
            avg_comp_price_per_sqft = price_per_sqft

        # Calculate price value score (0-100)
        # More generous scoring: 75 = at market (fair value), 90+ = below market (great deal)
        # 60 = 10% above market, 40 = 20% above market
        if avg_comp_price_per_sqft > 0:
            price_ratio = price_per_sqft / avg_comp_price_per_sqft
            # At market (ratio=1.0) = 75, below market = higher, above = lower
            price_value_score = max(30, min(95, 75 + (1.0 - price_ratio) * 100))
        else:
            price_value_score = 70  # Unknown defaults to reasonable

        # Appreciation potential (more generous scoring)
        year_built = property_data.get('year_built', 2000)
        age = 2026 - year_built
        if age < 5:
            appreciation_score = 85  # New construction
        elif age < 15:
            appreciation_score = 80  # Modern home
        elif age < 30:
            appreciation_score = 75  # Established home
        elif age < 50:
            appreciation_score = 70  # Older but solid
        else:
            appreciation_score = 65  # Vintage/historic

        # Overall score (weighted average) - more balanced
        overall_score = (
            price_value_score * 0.35 +
            appreciation_score * 0.35 +
            75 * 0.30  # Base market/rental score (most areas have decent fundamentals)
        )

        # Determine market comparison
        price_diff_pct = ((price_per_sqft / avg_comp_price_per_sqft) - 1) * 100 if avg_comp_price_per_sqft > 0 else 0
        if price_diff_pct < -10:
            market_comparison = f"below market by {abs(price_diff_pct):.1f}%"
        elif price_diff_pct > 10:
            market_comparison = f"above market by {price_diff_pct:.1f}%"
        else:
            market_comparison = "at market value"

        return {
            'overall_score': round(overall_score, 1),
            'sub_scores': {
                'price_value': round(price_value_score, 1),
                'appreciation': round(appreciation_score, 1),
                'rental_potential': 65,
                'investment_quality': round(overall_score, 1)
            },
            'reasoning': f'Property is {market_comparison}. Price per sqft: ${price_per_sqft:.0f} vs market ${avg_comp_price_per_sqft:.0f}.',
            'price_per_sqft': round(price_per_sqft, 2),
            'market_comparison': market_comparison,
            'estimated_rental_income': 'Data not available',
            'estimated_appreciation': '3-5% annually (average)',
            'pros': self._get_pros(price_value_score, age),
            'cons': self._get_cons(price_value_score, age),
            'recommendations': self._get_recommendations(overall_score),
            'risk_factors': ['Market data limited', 'Estimate based on comparable properties'],
            'confidence': 'medium' if comparables else 'low',
            'llm_cost': 0,
            'tokens_used': 0,
            'rule_based': True
        }

    def _get_pros(self, price_value_score: float, age: int) -> List[str]:
        """Generate pros based on analysis"""
        pros = []
        if price_value_score > 70:
            pros.append("Priced below market - good value")
        if age < 10:
            pros.append("Relatively new property")
        return pros if pros else ["Property has standard characteristics"]

    def _get_cons(self, price_value_score: float, age: int) -> List[str]:
        """Generate cons based on analysis"""
        cons = []
        if price_value_score < 30:
            cons.append("Priced above market average")
        if age > 50:
            cons.append("Older property may require updates")
        return cons if cons else ["No significant concerns identified"]

    def _get_recommendations(self, score: float) -> List[str]:
        """Generate recommendations based on score"""
        if score >= 80:
            return ["Strong investment opportunity", "Consider making competitive offer"]
        elif score >= 70:
            return ["Good investment potential", "Negotiate for best price"]
        elif score >= 60:
            return ["Fair investment", "Ensure thorough inspection before purchase"]
        else:
            return ["Below average investment", "Consider other options or significant price reduction"]
