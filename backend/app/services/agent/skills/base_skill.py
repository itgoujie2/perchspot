"""
Base Skill Class - Abstract base for all analysis skills

Skills load their instructions from .claude/skills/[skill-name]/SKILL.md files.
The .md files are the source of truth for skill behavior.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import logging
import json
import asyncio
import anthropic
import os

from app.services.agent.skills.skill_loader import skill_loader

logger = logging.getLogger(__name__)

# Anthropic pricing per 1M tokens (as of 2024)
# https://www.anthropic.com/pricing
MODEL_PRICING = {
    # Claude 4 Sonnet
    "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    # Claude 3.5 Sonnet
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet-20240620": {"input": 3.00, "output": 15.00},
    # Claude 4 Haiku
    "claude-haiku-4-20250414": {"input": 0.80, "output": 4.00},
    # Claude 3 Haiku
    "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
    # Default fallback
    "_default": {"input": 3.00, "output": 15.00},
}


class BaseSkill(ABC):
    """
    Abstract base class for all analysis skills.

    Each skill:
    - Loads instructions from SKILL.md file
    - Loads supporting .md files as needed
    - Runs independently
    - Returns structured results
    """

    def __init__(self):
        # Use AsyncAnthropic for non-blocking API calls
        self.claude_client = anthropic.AsyncAnthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        # Keep sync client for methods that need it (relevance filtering)
        self._sync_claude_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        # Map class name to skill folder name
        # PropertySkill -> property-analysis
        class_name = self.__class__.__name__.replace('Skill', '').lower()
        self.skill_name = f"{class_name}-analysis"
        self.skill_data = None

        # Cost tracking
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = []  # List of {model, input_tokens, output_tokens, cost}

    def _reset_cost_tracking(self):
        """Reset cost tracking for a new analysis."""
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = []

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost for an API call."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["_default"])
        cost = (input_tokens * pricing["input"] / 1_000_000) + (output_tokens * pricing["output"] / 1_000_000)
        return cost

    def _track_api_call(self, model: str, input_tokens: int, output_tokens: int):
        """Track an API call and its cost."""
        cost = self._calculate_cost(model, input_tokens, output_tokens)
        self.total_cost += cost
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.api_calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": round(cost, 6)
        })
        logger.info(f"{self.skill_name}: API call - {model} - {input_tokens} in / {output_tokens} out = ${cost:.6f}")

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for the analysis."""
        return {
            "total_cost": round(self.total_cost, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "api_calls": self.api_calls
        }

    def _load_skill(self):
        """Load skill from SKILL.md file (lazy loading)."""
        if self.skill_data is None:
            self.skill_data = skill_loader.load_skill(self.skill_name)
            logger.info(f"Loaded skill: {self.skill_name} ({len(self.skill_data['full_context'])} chars)")

    @abstractmethod
    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze the property for this skill's domain.

        Args:
            address: Property address
            **kwargs: Additional parameters specific to the skill

        Returns:
            Dict with structure:
            {
                'score': int (0-100),
                'confidence': str ('high', 'medium', 'low'),
                'reasoning': str,
                'strengths': List[str],
                'concerns': List[str],
                'details': Dict[str, Any],
                'raw_data': Dict[str, Any]  # Optional, for reference
            }
        """
        pass

    async def _call_claude(self, prompt: str, max_tokens: int = 2048, images: list = None, model: str = "claude-sonnet-4-5-20250929") -> str:
        """Helper to call Claude API with cost tracking (async, non-blocking)."""
        try:
            messages_content = []

            # Add images if provided
            if images:
                for img_url in images[:10]:  # Limit to 10 images
                    messages_content.append({
                        "type": "image",
                        "source": {
                            "type": "url",
                            "url": img_url
                        }
                    })

            # Add text prompt
            messages_content.append({
                "type": "text",
                "text": prompt
            })

            # Use async client for non-blocking API calls
            response = await self.claude_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{
                    "role": "user",
                    "content": messages_content
                }]
            )

            # Track cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            self._track_api_call(model, input_tokens, output_tokens)

            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error in {self.skill_name} skill: {e}")
            raise

    def _get_knowledge_context(self, query: str, limit: int = 5) -> str:
        """
        Retrieve relevant knowledge context for LLM augmentation.

        Returns formatted context string, or empty string on error.
        Errors are logged but never block analysis.
        """
        try:
            from app.services.knowledge.search_service import get_search_service
            service = get_search_service()
            return service.search_for_context(query, limit=limit)
        except Exception as e:
            logger.warning(f"Knowledge search unavailable: {e}")
            return ""

    def _get_knowledge_results(self, query: str, limit: int = 5):
        """
        Retrieve raw search results for debugging/display.

        Returns (formatted_context, list of {query, text, category, score, source_file}).
        """
        try:
            from app.services.knowledge.search_service import get_search_service
            service = get_search_service()
            results = service.search(query, limit=limit)
            context = service.search_for_context(query, limit=limit)
            hits = [
                {
                    "text": r.text,
                    "category": r.category,
                    "score": round(r.score, 4),
                    "source_file": r.source_file,
                }
                for r in results
            ]
            return context, {"query": query, "results": hits}
        except Exception as e:
            logger.warning(f"Knowledge search unavailable: {e}")
            return "", {"query": query, "results": []}

    def _run_multi_query_search(self, queries: list[str], limit_per_query: int = 3):
        """
        Run multiple targeted knowledge queries, deduplicate results.

        Note: This is synchronous but fast (local vector search).
        Relevance filtering is skipped here - done async in skills if needed.

        Returns (combined_context_str, debug_list) where debug_list is a list of
        {query, results: [{text, category, score, source_file}]}.
        """
        try:
            from app.services.knowledge.search_service import get_search_service
            from collections import defaultdict
            service = get_search_service()
        except Exception as e:
            logger.warning(f"Knowledge search unavailable: {e}")
            return "", [{"query": q, "results": []} for q in queries]

        all_debug = []
        seen_texts = set()
        by_category = defaultdict(list)

        for query in queries:
            try:
                results = service.search(query, limit=limit_per_query)
                hits = []
                for r in results:
                    hits.append({
                        "text": r.text,
                        "category": r.category,
                        "score": round(r.score, 4),
                        "source_file": r.source_file,
                    })
                    if r.text not in seen_texts:
                        seen_texts.add(r.text)
                        by_category[r.category].append(r.text)
                all_debug.append({"query": query, "results": hits})
            except Exception as e:
                logger.warning(f"Knowledge query failed for '{query}': {e}")
                all_debug.append({"query": query, "results": []})

        # Skip relevance filtering here - it adds latency and blocks parallel execution
        # The knowledge search already uses semantic similarity, so results are usually relevant

        # Build combined context string grouped by category
        sections = []
        for category, texts in by_category.items():
            lines = [f"### {category}"]
            for text in texts:
                lines.append(f"- {text}")
            sections.append("\n".join(lines))

        combined = "\n\n".join(sections)
        return combined, all_debug

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response from Claude, handling markdown code blocks."""
        import json

        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response_text[:500]}")
            raise
