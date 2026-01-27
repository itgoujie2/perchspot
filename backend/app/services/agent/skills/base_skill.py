"""
Base Skill Class - Abstract base for all analysis skills

Skills load their instructions from .claude/skills/[skill-name]/SKILL.md files.
The .md files are the source of truth for skill behavior.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
import logging
import anthropic
import os

from app.services.agent.skills.skill_loader import skill_loader

logger = logging.getLogger(__name__)


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
        self.claude_client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        # Map class name to skill folder name
        # PropertySkill -> property-analysis
        class_name = self.__class__.__name__.replace('Skill', '').lower()
        self.skill_name = f"{class_name}-analysis"
        self.skill_data = None

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

    async def _call_claude(self, prompt: str, max_tokens: int = 2048, images: list = None) -> str:
        """Helper to call Claude API."""
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

            response = self.claude_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=max_tokens,
                messages=[{
                    "role": "user",
                    "content": messages_content
                }]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error in {self.skill_name} skill: {e}")
            raise

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
