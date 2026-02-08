"""
Chat API endpoints - Follow-up questions about property analysis
"""
import logging
import uuid
import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import anthropic
import os

from app.services.agent.tools.notes_manager import NotesManager
from app.config import settings
from app.api.v1.deps import get_optional_user
from app.database.connection import get_db
from app.models.user import User
from app.services.auth.credit_service import deduct_credits, check_balance
from app.services.memory import MemoryService, SAVE_MEMORY_TOOL, execute_save_memory
from app.services.search import SimilarHomesService, GET_RECOMMENDATIONS_TOOL

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory conversation storage
conversations: Dict[str, Dict[str, Any]] = {}

notes_manager = NotesManager()


class ChatMessage(BaseModel):
    """Chat message from user"""
    message: str = Field(..., description="User's message/question")
    address: Optional[str] = Field(None, description="Property address for context")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID to continue existing chat")


class ChatResponse(BaseModel):
    """Response from agent"""
    response: str
    conversation_id: str
    cost: float = 0.0
    credit_balance: Optional[float] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    message: ChatMessage,
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Chat with the analysis agent about a property.

    Uses analysis notes as context for informed follow-up answers.
    """
    try:
        conversation_id = message.conversation_id or str(uuid.uuid4())

        # Load user memory context if authenticated
        user_memory_context = ""
        if user:
            memory_service = MemoryService(db)
            user_memory_context = memory_service.format_memories_for_prompt(user.id)
            if user_memory_context:
                logger.info(f"Loaded user memory context ({len(user_memory_context)} chars)")

        # Load or create conversation state
        if conversation_id in conversations:
            conv = conversations[conversation_id]
        else:
            # New conversation — load analysis context from notes
            context = ""
            if message.address:
                notes_content = notes_manager.read_notes(message.address)
                if notes_content:
                    # Truncate if too long (keep under ~8k chars for context)
                    if len(notes_content) > 8000:
                        context = notes_content[:8000] + "\n\n[... notes truncated ...]"
                    else:
                        context = notes_content
                    logger.info(f"Loaded {len(context)} chars of notes for chat context")
                else:
                    logger.info(f"No notes found for address: {message.address}")

            conv = {
                "address": message.address,
                "context": context,
                "history": [],  # list of {role, content} dicts
            }
            conversations[conversation_id] = conv

        # Build messages for Claude
        system_prompt = """You are a helpful real estate analysis assistant. Answer the user's questions about the property analysis clearly and concisely. Use the analysis data provided as context.

You can search the web for current information when needed, such as:
- Current mortgage/interest rates
- Recent market conditions and trends
- Local real estate news
- Property tax rates and regulations

Always cite sources when using web search results. If you don't have enough information to answer and cannot find it via search, say so honestly."""

        # Add user memory context if available
        if user_memory_context:
            system_prompt += f"\n\n{user_memory_context}"

        # Add tool instructions for authenticated users
        if user:
            system_prompt += """

When the user shares preferences or information about themselves (budget, property needs, family situation, etc.),
use the save_user_memory tool to remember it for future conversations. Only save clear, stated preferences.
Do not acknowledge saving memories to the user - just save silently and continue the conversation naturally."""

        if conv["context"]:
            system_prompt += f"\n\nPROPERTY ANALYSIS DATA:\n{conv['context']}"

        # Build message list
        messages: List[Dict[str, Any]] = []
        for msg in conv["history"]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": message.message})

        # Build tools list - web search for all, memory and recommendations for authenticated users
        tools: List[Dict[str, Any]] = [{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 3,  # Limit searches per request to control costs
        }]
        if user:
            tools.append(SAVE_MEMORY_TOOL)
            tools.append(GET_RECOMMENDATIONS_TOOL)

        # Call Claude with tools
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

        # Track total costs across potential multiple API calls
        total_input_tokens = 0
        total_output_tokens = 0
        total_web_searches = 0

        # Agentic loop to handle tool calls
        max_iterations = 5
        for iteration in range(max_iterations):
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )

            # Accumulate usage
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens
            if hasattr(response.usage, "server_tool_use") and response.usage.server_tool_use:
                total_web_searches += getattr(response.usage.server_tool_use, "web_search_requests", 0)

            # Check if we need to handle tool use
            if response.stop_reason == "tool_use":
                # Process tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        if block.name == "save_user_memory" and user:
                            # Execute memory save
                            result = execute_save_memory(
                                db=db,
                                user_id=user.id,
                                tool_input=block.input,
                                source_context=message.message[:200],
                            )
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            })
                        elif block.name == "get_property_recommendations" and user:
                            # Get similar homes recommendations
                            similar_service = SimilarHomesService(db)
                            limit = block.input.get("limit", 5) if block.input else 5
                            recs = similar_service.get_recommendations(user.id, limit=limit)
                            # Mark as shown to avoid re-recommending
                            if recs:
                                addresses = [r["address"] for r in recs]
                                similar_service.mark_as_shown(user.id, addresses)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps({
                                    "recommendations": recs,
                                    "count": len(recs),
                                }),
                            })
                        # Web search is handled by Anthropic's server

                # Add assistant message and tool results to continue conversation
                messages.append({"role": "assistant", "content": response.content})
                if tool_results:
                    messages.append({"role": "user", "content": tool_results})
            else:
                # End turn - extract final response
                break

        # Extract text from final response (may include multiple content blocks with citations)
        assistant_text = ""
        for block in response.content:
            if block.type == "text":
                assistant_text += block.text

        # Calculate cost (Claude Haiku 4.5: $1.00/M input, $5.00/M output)
        input_cost = (total_input_tokens / 1_000_000) * 1.00
        output_cost = (total_output_tokens / 1_000_000) * 5.00

        # Add web search cost ($10/1000 = $0.01 per search)
        search_cost = total_web_searches * 0.01

        cost = input_cost + output_cost + search_cost

        if total_web_searches > 0:
            logger.info(f"Web search used {total_web_searches} times (cost: ${search_cost:.4f})")

        # Apply pricing margin for user-facing cost
        user_cost = cost / (1.0 - settings.PRICING_MARGIN) if settings.PRICING_MARGIN < 1.0 else cost

        current_balance: Optional[float] = None

        if user:
            # Authenticated: deduct credits
            deducted = deduct_credits(
                db, user.id, user_cost, "chat", conversation_id,
                description=f"Chat: {message.message[:100]}",
            )
            if not deducted:
                balance = float(check_balance(db, user.id))
                raise HTTPException(
                    status_code=402,
                    detail={
                        "message": "Insufficient credits",
                        "balance": balance,
                        "cost": user_cost,
                    },
                )
            current_balance = float(check_balance(db, user.id))
        else:
            # Anonymous: free chat (tied to their free analysis)
            user_cost = 0.0

        # Update conversation history
        conv["history"].append({"role": "user", "content": message.message})
        conv["history"].append({"role": "assistant", "content": assistant_text})

        # Keep history manageable (last 20 messages)
        if len(conv["history"]) > 20:
            conv["history"] = conv["history"][-20:]

        logger.info(f"Chat response for {conversation_id}: {assistant_text[:100]}... (cost: ${cost:.4f})")

        return ChatResponse(
            response=assistant_text,
            conversation_id=conversation_id,
            cost=user_cost,
            credit_balance=current_balance,
        )

    except HTTPException:
        raise
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error in chat: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM API error: {str(e)}")
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
