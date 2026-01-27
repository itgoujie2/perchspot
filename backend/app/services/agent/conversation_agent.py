"""
Conversation Agent - Phase 2: Handles user questions about analysis

This agent:
1. Has full context from Phase 1 analysis results
2. Can answer follow-up questions
3. Can re-invoke skills if user asks for new analysis (e.g., different work location)
4. Uses conversation-specific contexts
"""
import json
from typing import Dict, Any, List
import logging
import anthropic
import os

from app.services.agent.skills.property_skill import PropertySkill
from app.services.agent.skills.school_skill import SchoolSkill
from app.services.agent.skills.location_skill import LocationSkill
from app.services.agent.skills.investment_skill import InvestmentSkill

logger = logging.getLogger(__name__)


class ConversationAgent:
    """
    Handles conversational interactions about property analysis.
    """

    def __init__(self, analysis_results: Dict[str, Any]):
        """
        Initialize with analysis results from Phase 1.

        Args:
            analysis_results: Full analysis from AnalysisOrchestrator
        """
        self.analysis_results = analysis_results
        self.conversation_history: List[Dict] = []

        # Initialize Claude client
        self.claude_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )

        # Initialize skills (for re-invocation if needed)
        self.skills = {
            'property': PropertySkill(),
            'school': SchoolSkill(),
            'location': LocationSkill(),
            'investment': InvestmentSkill()
        }

        logger.info(f"ConversationAgent initialized for {analysis_results.get('address')}")

    async def chat(self, user_message: str) -> str:
        """
        Handle a user message and return a response.

        Args:
            user_message: User's question or comment

        Returns:
            Agent's response as text
        """
        logger.info(f"User message: {user_message[:100]}...")

        # Add to conversation history
        self.conversation_history.append({
            'role': 'user',
            'content': user_message
        })

        # Build prompt with full context
        prompt = self._build_prompt(user_message)

        # Call Claude
        try:
            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                messages=self._format_conversation_history()
            )

            assistant_message = response.content[0].text

            # Add to conversation history
            self.conversation_history.append({
                'role': 'assistant',
                'content': assistant_message
            })

            logger.info(f"Assistant response: {assistant_message[:100]}...")

            return assistant_message

        except Exception as e:
            logger.error(f"Chat failed: {e}", exc_info=True)
            return f"I apologize, but I encountered an error: {str(e)}"

    def _build_prompt(self, user_message: str) -> str:
        """Build prompt with contexts and analysis results."""

        # Format analysis results nicely
        analysis_summary = json.dumps({
            'address': self.analysis_results['address'],
            'overall_score': self.analysis_results['overall_score'],
            'overall_grade': self.analysis_results['overall_grade'],
            'property': {
                'score': self.analysis_results['property']['score'],
                'confidence': self.analysis_results['property']['confidence'],
                'reasoning': self.analysis_results['property']['reasoning'],
                'strengths': self.analysis_results['property']['strengths'],
                'concerns': self.analysis_results['property']['concerns']
            },
            'schools': {
                'score': self.analysis_results['schools']['score'],
                'confidence': self.analysis_results['schools']['confidence'],
                'reasoning': self.analysis_results['schools']['reasoning'],
                'strengths': self.analysis_results['schools']['strengths'],
                'concerns': self.analysis_results['schools']['concerns']
            },
            'location': {
                'score': self.analysis_results['location']['score'],
                'confidence': self.analysis_results['location']['confidence'],
                'reasoning': self.analysis_results['location']['reasoning'],
                'strengths': self.analysis_results['location']['strengths'],
                'concerns': self.analysis_results['location']['concerns']
            },
            'investment': {
                'score': self.analysis_results['investment']['score'],
                'confidence': self.analysis_results['investment']['confidence'],
                'reasoning': self.analysis_results['investment']['reasoning'],
                'strengths': self.analysis_results['investment']['strengths'],
                'concerns': self.analysis_results['investment']['concerns']
            }
        }, indent=2)

        prompt = f"""
You are a helpful real estate analysis assistant. The user has received a comprehensive property analysis and may have questions.

PROPERTY ANALYSIS RESULTS:
{analysis_summary}

---

Guidelines:
1. Answer based on the analysis results above
2. Be helpful, clear, and concise
3. If you don't have enough information, say so
4. Never provide financial advice - present data objectively
5. Explain concepts in simple terms that homebuyers can understand

USER QUESTION: {user_message}

Provide a helpful, clear answer.
"""
        return prompt

    def _format_conversation_history(self) -> List[Dict]:
        """Format conversation history for Claude API."""
        # For the first message, include the full prompt
        if len(self.conversation_history) == 1:
            return [{
                'role': 'user',
                'content': self._build_prompt(self.conversation_history[0]['content'])
            }]

        # For subsequent messages, just include the conversation
        messages = []
        for msg in self.conversation_history:
            messages.append({
                'role': msg['role'],
                'content': msg['content']
            })

        return messages

    async def re_analyze(self, skill_name: str, **kwargs) -> Dict[str, Any]:
        """
        Re-invoke a specific skill with new parameters.

        Example: User asks "What if I work in Bellevue instead?"
                -> re_analyze('location', work_location='Bellevue')

        Args:
            skill_name: 'property', 'school', 'location', or 'investment'
            **kwargs: Parameters for the skill

        Returns:
            Updated analysis results
        """
        if skill_name not in self.skills:
            raise ValueError(f"Unknown skill: {skill_name}")

        address = self.analysis_results['address']
        logger.info(f"Re-analyzing {skill_name} for {address} with params: {kwargs}")

        # Run the skill
        new_result = await self.skills[skill_name].analyze(address, **kwargs)

        # Update analysis results
        self.analysis_results[skill_name] = new_result

        # Recalculate overall score
        weights = self.analysis_results['category_weights']
        overall_score = int(
            self.analysis_results['property']['score'] * weights['property'] +
            self.analysis_results['schools']['score'] * weights['schools'] +
            self.analysis_results['location']['score'] * weights['location'] +
            self.analysis_results['investment']['score'] * weights['investment']
        )

        self.analysis_results['overall_score'] = overall_score
        self.analysis_results['overall_grade'] = self._calculate_grade(overall_score)

        logger.info(f"Re-analysis complete. New {skill_name} score: {new_result['score']}")

        return self.analysis_results

    def _calculate_grade(self, score: int) -> str:
        """Convert score to letter grade."""
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'

    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation."""
        if not self.conversation_history:
            return "No conversation yet."

        return f"Conversation about {self.analysis_results['address']} - {len(self.conversation_history)} messages"
