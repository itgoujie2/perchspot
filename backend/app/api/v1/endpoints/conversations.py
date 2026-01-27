"""
Conversation endpoints - Chat with the analysis agent
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

from celery.result import AsyncResult
from app.services.agent.conversation_agent import ConversationAgent

logger = logging.getLogger(__name__)

router = APIRouter()

# Store conversation agents in memory (in production, use Redis or database)
conversation_agents: Dict[str, ConversationAgent] = {}


class ChatMessage(BaseModel):
    """Chat message from user"""
    message: str


class ChatResponse(BaseModel):
    """Chat response from agent"""
    response: str
    conversation_id: str


@router.post("/analysis/{analysis_id}/chat", response_model=ChatResponse)
async def chat_with_analysis(
    analysis_id: str,
    chat_message: ChatMessage
):
    """
    Chat with the agent about a completed analysis.

    This allows users to ask follow-up questions like:
    - "Why is the school score low?"
    - "Tell me more about the property condition"
    - "What if I work in Bellevue instead?"

    Args:
        analysis_id: The completed analysis ID
        chat_message: User's message

    Returns:
        Agent's response
    """
    try:
        # Get or create conversation agent for this analysis
        if analysis_id not in conversation_agents:
            # Get analysis results from Celery
            task_result = AsyncResult(analysis_id)

            if task_result.state != 'SUCCESS':
                raise HTTPException(
                    status_code=404,
                    detail=f"Analysis not complete or not found. Status: {task_result.state}"
                )

            # Get analysis data
            result = task_result.get()
            analysis_data = result.get('result', {})

            # Create conversation agent
            conversation_agents[analysis_id] = ConversationAgent(analysis_data)
            logger.info(f"Created new conversation agent for analysis {analysis_id}")

        # Get agent
        agent = conversation_agents[analysis_id]

        # Chat
        response_text = await agent.chat(chat_message.message)

        logger.info(f"Chat response for {analysis_id}: {response_text[:100]}...")

        return ChatResponse(
            response=response_text,
            conversation_id=analysis_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{analysis_id}/conversation")
async def get_conversation_history(analysis_id: str):
    """
    Get the conversation history for an analysis.

    Returns all messages exchanged between user and agent.
    """
    try:
        if analysis_id not in conversation_agents:
            raise HTTPException(
                status_code=404,
                detail="No conversation found for this analysis"
            )

        agent = conversation_agents[analysis_id]

        return {
            'analysis_id': analysis_id,
            'address': agent.analysis_results['address'],
            'message_count': len(agent.conversation_history),
            'messages': agent.conversation_history
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/analysis/{analysis_id}/conversation")
async def clear_conversation(analysis_id: str):
    """
    Clear/delete the conversation for an analysis.

    This removes the conversation agent from memory.
    """
    try:
        if analysis_id in conversation_agents:
            del conversation_agents[analysis_id]
            logger.info(f"Cleared conversation for analysis {analysis_id}")
            return {'status': 'cleared', 'analysis_id': analysis_id}
        else:
            raise HTTPException(
                status_code=404,
                detail="No conversation found for this analysis"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
