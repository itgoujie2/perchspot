"""
Chat API endpoints for interactive housing analysis
"""
import logging
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.agent.housing_agent import HousingAnalysisAgent

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message from user"""
    message: str = Field(..., description="User's message/question")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID to continue existing chat")
    conversation_history: Optional[list] = Field(None, description="Optional conversation history")


class AnalyzeRequest(BaseModel):
    """Request to analyze a property and generate full report"""
    address: str = Field(..., description="Property address to analyze")


class ChatResponse(BaseModel):
    """Response from agent"""
    response: str
    conversation_id: str
    tool_calls: list
    conversation_history: list
    tokens_used: dict
    cost: float
    iterations: int


# In-memory conversation storage (replace with database in production)
conversations = {}


@router.post("/chat/analyze", response_model=ChatResponse)
async def analyze_property(request: AnalyzeRequest):
    """
    Analyze a property and generate a comprehensive report.

    This endpoint is specifically for the hybrid interface where the agent
    automatically generates a full report when given an address.

    The agent will:
    - Scrape property details from Zillow
    - Get school ratings from GreatSchools
    - Analyze location quality
    - Generate a comprehensive summary

    Returns a conversation ID for follow-up questions.
    """
    try:
        # Create new conversation ID
        conversation_id = str(uuid.uuid4())

        # Create agent
        agent = HousingAnalysisAgent()

        # Generate comprehensive analysis prompt
        analysis_prompt = f"""Please provide a comprehensive analysis of the property at: {request.address}

I need you to:
1. Get detailed property information (price, beds, baths, size, photos)
2. Find nearby schools and their ratings
3. Analyze the location quality
4. Provide an overall summary with key insights

Please use your tools to gather this information and present it in a clear, organized format."""

        # Process analysis
        logger.info(f"Starting property analysis for: {request.address}")
        result = await agent.chat(
            user_message=analysis_prompt,
            conversation_id=conversation_id,
            conversation_history=None
        )

        # Store conversation
        conversations[conversation_id] = result['conversation_history']

        # Return response
        return ChatResponse(
            response=result['response'],
            conversation_id=conversation_id,
            tool_calls=result.get('tool_calls', []),
            conversation_history=result['conversation_history'],
            tokens_used=result.get('tokens_used', {}),
            cost=result.get('cost', 0.0),
            iterations=result.get('iterations', 1)
        )

    except Exception as e:
        logger.error(f"Property analysis error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(message: ChatMessage):
    """
    Chat with the housing analysis agent.

    The agent can dynamically call tools to answer questions about properties,
    neighborhoods, schools, commutes, and more.

    Example questions:
    - "Tell me about 123 Main St, Seattle, WA"
    - "What are the schools like near this address?"
    - "How long would my commute be to downtown?"
    - "Are there grocery stores nearby?"
    - "Compare this property with 456 Oak Ave"
    """
    try:
        # Get or create conversation ID
        conversation_id = message.conversation_id or str(uuid.uuid4())

        # Load conversation history
        if conversation_id in conversations:
            conversation_history = conversations[conversation_id]
        else:
            conversation_history = message.conversation_history

        # Create agent
        agent = HousingAnalysisAgent()

        # Process message
        logger.info(f"Processing chat message in conversation {conversation_id}")
        result = await agent.chat(
            user_message=message.message,
            conversation_id=conversation_id,
            conversation_history=conversation_history
        )

        # Store conversation
        conversations[conversation_id] = result['conversation_history']

        # Return response
        return ChatResponse(
            response=result['response'],
            conversation_id=conversation_id,
            tool_calls=result.get('tool_calls', []),
            conversation_history=result['conversation_history'],
            tokens_used=result.get('tokens_used', {}),
            cost=result.get('cost', 0.0),
            iterations=result.get('iterations', 1)
        )

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation history"""
    if conversation_id in conversations:
        del conversations[conversation_id]
        return {"message": "Conversation deleted"}
    else:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/chat/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    if conversation_id in conversations:
        return {
            "conversation_id": conversation_id,
            "history": conversations[conversation_id]
        }
    else:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.get("/chat/{conversation_id}/summary")
async def get_conversation_summary(conversation_id: str):
    """Get a summary of the conversation"""
    if conversation_id not in conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    history = conversations[conversation_id]

    # Count messages
    user_messages = [msg for msg in history if msg.get('role') == 'user']
    assistant_messages = [msg for msg in history if msg.get('role') == 'assistant']
    tool_calls = [msg for msg in history if msg.get('role') == 'tool']

    return {
        "conversation_id": conversation_id,
        "message_count": len(user_messages),
        "agent_responses": len(assistant_messages),
        "tool_calls": len(tool_calls),
        "last_message": user_messages[-1]['content'] if user_messages else None
    }
