"""
Memory Tool - Claude tool definition for saving user memories during chat
"""
import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.services.memory.memory_service import MemoryService

logger = logging.getLogger(__name__)

# Valid categories for memory storage
VALID_CATEGORIES = ["budget", "property_preference", "intent", "family_situation", "lifestyle"]
VALID_CONFIDENCE = ["high", "medium", "low"]

# Claude tool definition for save_user_memory
SAVE_MEMORY_TOOL = {
    "name": "save_user_memory",
    "description": """Save user preferences and information when they share relevant details during conversation.
Use this tool to remember:
- Budget information: max_price, min_price, down_payment, income, pre_approval_amount
- Property preferences: property_type, min_bedrooms, max_bedrooms, min_sqft, must_have_features, deal_breakers
- Intent/Goals: primary_purpose (primary_residence, investment, vacation), investment_strategy, timeline
- Family situation: has_children, children_ages, school_priority, pets
- Lifestyle: work_location, max_commute, commute_mode, preferred_neighborhoods

Do NOT store:
- Sensitive PII like SSN, bank account numbers, or exact addresses
- Temporary or session-specific information
- Information the user explicitly says not to remember

Only save when the user clearly states a preference. Use high confidence for explicit statements,
medium for reasonable inferences, low for uncertain interpretations.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": VALID_CATEGORIES,
                "description": "Category of the memory"
            },
            "memory_key": {
                "type": "string",
                "description": "Specific key within the category (e.g., 'max_price', 'property_type')"
            },
            "memory_value": {
                "type": "string",
                "description": "The value to remember (e.g., '$800,000', 'single family')"
            },
            "confidence": {
                "type": "string",
                "enum": VALID_CONFIDENCE,
                "default": "medium",
                "description": "Confidence level: high for explicit statements, medium for inferences, low for uncertain"
            }
        },
        "required": ["category", "memory_key", "memory_value"]
    }
}


def execute_save_memory(
    db: Session,
    user_id: str,
    tool_input: Dict[str, Any],
    source_context: str = None,
) -> Dict[str, Any]:
    """
    Execute the save_user_memory tool call.

    Args:
        db: Database session
        user_id: The authenticated user's ID
        tool_input: The input from Claude's tool call
        source_context: Optional context about what triggered this save

    Returns:
        Tool result to return to Claude
    """
    category = tool_input.get("category")
    memory_key = tool_input.get("memory_key")
    memory_value = tool_input.get("memory_value")
    confidence = tool_input.get("confidence", "medium")

    # Validate inputs
    if category not in VALID_CATEGORIES:
        return {
            "success": False,
            "error": f"Invalid category. Must be one of: {', '.join(VALID_CATEGORIES)}"
        }

    if confidence not in VALID_CONFIDENCE:
        confidence = "medium"

    if not memory_key or not memory_value:
        return {
            "success": False,
            "error": "memory_key and memory_value are required"
        }

    # Save the memory
    try:
        memory_service = MemoryService(db)
        memory = memory_service.save_memory(
            user_id=user_id,
            category=category,
            memory_key=memory_key,
            memory_value=memory_value,
            confidence=confidence,
            source="chat",
            source_context=source_context,
        )
        logger.info(f"Saved memory via tool: {category}/{memory_key}={memory_value}")
        return {
            "success": True,
            "message": f"Saved {category}/{memory_key}"
        }
    except Exception as e:
        logger.error(f"Error saving memory: {e}")
        return {
            "success": False,
            "error": str(e)
        }
