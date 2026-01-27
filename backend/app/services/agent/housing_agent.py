"""
Housing Analysis Agent - Agentic approach with dynamic tool calling
"""
import logging
import json
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI

from app.config import settings
from app.services.agent.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)


class HousingAnalysisAgent:
    """
    Intelligent agent that can dynamically call tools to answer housing questions.

    Uses OpenAI's function calling to decide which tools to use based on user queries.
    """

    SYSTEM_PROMPT = """You are a professional real estate analyst assistant using a comprehensive 8-category framework to evaluate properties.

## Your Analysis Framework

When analyzing a property, you must evaluate it across these 8 major categories:

1. **Physical Quality (15-20% weight)** - Structure, materials, condition, specifications
   - Basic specs: size, bedrooms, bathrooms, year built
   - Structural components and material quality
   - Mechanical systems (HVAC, plumbing, electrical)
   - Overall condition assessment

2. **Location & Accessibility (10-15% weight)** - Commute, transportation, connectivity
   - Commute times to major areas
   - Highway access and proximity issues
   - Nearby essentials (grocery, pharmacy, services)
   - Transportation infrastructure and walkability

3. **Education (0-20% weight)** - School quality and resources
   - Elementary, middle, and high school ratings
   - School quality scores and rankings
   - Distance to schools
   - Private/charter options

4. **Neighborhood & Environment (10-20% weight)** - Safety, quality of life
   - Safety and crime statistics
   - Noise and air quality
   - Walkability scores
   - Community character

5. **Lot & Land Characteristics (5-15% weight)** - Physical land features
   - Lot size, shape, and topography
   - Sun exposure and orientation
   - Views and privacy
   - Natural features

6. **Natural Hazards & Risk (10-15% weight)** - Disaster and climate risks
   - Flood zones and risk
   - Earthquake and wildfire risk
   - Climate change projections
   - Insurance implications

7. **Financial & Investment (10-35% weight)** - Value and returns
   - Current valuation and price/sqft
   - Rental potential and cash flow
   - Appreciation trends
   - Carrying costs (taxes, insurance, HOA)

8. **Legal & Regulatory (5-10% weight)** - Zoning and restrictions
   - Zoning and permitted uses
   - HOA rules and fees
   - Permits and compliance
   - Title issues and easements

## Available Tools

You have access to these tools to gather data:
- scrape_zillow - Property details, price, photos, specs
- scrape_redfin - Alternative property data source
- get_school_ratings - GreatSchools ratings and info
- get_natural_hazards - Flood, earthquake, wildfire, climate risks
- get_walkability_scores - Walk Score, Transit Score, Bike Score
- get_environmental_quality - Air quality, noise pollution
- get_financial_analysis - Valuation, rental estimates, investment metrics
- search_nearby_places - Amenities within specified radius
- calculate_commute - Commute times to destinations
- get_crime_statistics - Safety and crime data
- compare_properties - Side-by-side comparison

## When Generating Comprehensive Reports

For initial property analysis, you should:
1. Call tools to gather data across all 8 categories
2. Synthesize the data into a structured report
3. Provide scores/ratings for each category (1-10 scale)
4. Highlight key strengths and concerns
5. Give an overall recommendation

Use this rating scale:
- 9-10: Excellent
- 7-8: Good
- 5-6: Average
- 3-4: Below Average
- 1-2: Poor

Format your comprehensive analysis in clear sections for each category.

## When Answering Follow-up Questions

Be conversational and focused. Use tools as needed to get specific information the user asks about. Reference the initial analysis and provide deeper insights on specific aspects.

Always be helpful, insightful, and data-driven. When you lack data, acknowledge it and explain what additional information would be helpful.
"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL
        self.conversation_history: List[Dict[str, Any]] = []

    async def chat(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Process a user message and return agent's response.

        Args:
            user_message: The user's question/message
            conversation_id: Optional conversation ID for persistence
            conversation_history: Optional existing conversation history

        Returns:
            Dictionary with response, tool calls, and metadata
        """
        # Initialize or load conversation history
        if conversation_history:
            self.conversation_history = conversation_history
        elif not self.conversation_history:
            self.conversation_history = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ]

        # Add user message
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Agent loop - may require multiple iterations if tools are called
        max_iterations = 5
        iteration = 0
        tool_calls_made = []

        while iteration < max_iterations:
            iteration += 1

            try:
                # Call OpenAI with function calling
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=self.conversation_history,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                    temperature=0.7,
                )

                message = response.choices[0].message

                # Check if agent wants to call tools
                if message.tool_calls:
                    logger.info(f"Agent requesting {len(message.tool_calls)} tool calls")

                    # Add assistant message with tool calls to history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    # Execute each tool call
                    for tool_call in message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)

                        logger.info(f"Executing tool: {function_name} with args: {function_args}")

                        # Execute the tool
                        tool_result = await execute_tool(function_name, function_args)

                        # Track tool calls
                        tool_calls_made.append({
                            "tool": function_name,
                            "args": function_args,
                            "result_preview": str(tool_result)[:200]
                        })

                        # Add tool result to conversation
                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": json.dumps(tool_result)
                        })

                    # Continue loop to get agent's response using the tool results
                    continue

                else:
                    # No more tool calls - agent has final response
                    final_response = message.content

                    # Add to history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": final_response
                    })

                    # Calculate cost
                    cost = self._calculate_cost(response.usage)

                    logger.info(
                        f"Agent response complete: {len(tool_calls_made)} tools used, "
                        f"${cost:.4f} cost"
                    )

                    return {
                        "response": final_response,
                        "tool_calls": tool_calls_made,
                        "conversation_history": self.conversation_history,
                        "tokens_used": {
                            "prompt": response.usage.prompt_tokens,
                            "completion": response.usage.completion_tokens,
                            "total": response.usage.total_tokens
                        },
                        "cost": cost,
                        "iterations": iteration
                    }

            except Exception as e:
                logger.error(f"Error in agent loop: {e}", exc_info=True)

                # Return error response
                error_message = f"I encountered an error: {str(e)}. Please try rephrasing your question."

                self.conversation_history.append({
                    "role": "assistant",
                    "content": error_message
                })

                return {
                    "response": error_message,
                    "tool_calls": tool_calls_made,
                    "conversation_history": self.conversation_history,
                    "error": str(e)
                }

        # Max iterations reached
        logger.warning(f"Agent reached max iterations ({max_iterations})")

        fallback_message = "I'm still processing your request. Could you try asking in a different way?"
        self.conversation_history.append({
            "role": "assistant",
            "content": fallback_message
        })

        return {
            "response": fallback_message,
            "tool_calls": tool_calls_made,
            "conversation_history": self.conversation_history,
            "warning": "Max iterations reached"
        }

    def _calculate_cost(self, usage) -> float:
        """Calculate cost based on token usage"""
        pricing = {
            "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
            "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
        }

        model_pricing = pricing.get(self.model, pricing["gpt-4o"])

        cost = (
            usage.prompt_tokens * model_pricing["input"] +
            usage.completion_tokens * model_pricing["output"]
        )

        return cost

    def reset_conversation(self):
        """Reset conversation history"""
        self.conversation_history = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]
