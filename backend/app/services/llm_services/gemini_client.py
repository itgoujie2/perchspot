"""
Gemini API client for property analysis
"""
import logging
import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Wrapper for Google Gemini API with cost tracking
    """

    # Pricing (per million tokens) for Gemini 2.0 Flash
    PRICING = {
        "gemini-2.0-flash-exp": {
            "input": 0.10,  # $0.10 per 1M tokens
            "output": 0.40,  # $0.40 per 1M tokens
        },
        "gemini-1.5-flash": {
            "input": 0.075,
            "output": 0.30,
        },
    }

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash-exp"):
        """
        Initialize Gemini client.

        Args:
            api_key: Optional Gemini API key. Uses settings.GEMINI_API_KEY if not provided.
            model: Model to use. Defaults to gemini-2.0-flash-exp.
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set in config or passed to constructor")

        genai.configure(api_key=self.api_key)
        self.model_name = model
        self.model = genai.GenerativeModel(model)

    async def analyze_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Send text-only prompt to Gemini for analysis.

        Args:
            prompt: User prompt
            system_prompt: Optional system instructions
            temperature: Generation temperature (0-1)
            max_tokens: Maximum output tokens

        Returns:
            {
                'content': str,  # Generated text
                'tokens_used': {'input': int, 'output': int, 'total': int},
                'cost': float,
                'model': str
            }
        """
        try:
            # Build full prompt with system instructions if provided
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            # Configure generation
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            # Generate response
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )

            # Extract text
            content = response.text

            # Calculate costs (Note: Gemini API doesn't provide exact token counts in free tier)
            # For estimation, we approximate tokens
            input_tokens = len(full_prompt.split()) * 1.3  # Rough approximation
            output_tokens = len(content.split()) * 1.3

            pricing = self.PRICING.get(self.model_name, self.PRICING["gemini-2.0-flash-exp"])
            cost = (input_tokens * pricing["input"] / 1_000_000 +
                   output_tokens * pricing["output"] / 1_000_000)

            tokens_used = {
                "input": int(input_tokens),
                "output": int(output_tokens),
                "total": int(input_tokens + output_tokens)
            }

            logger.info(f"Gemini analysis complete: {tokens_used['total']} tokens, ${cost:.6f}")

            return {
                "content": content,
                "tokens_used": tokens_used,
                "cost": cost,
                "model": self.model_name
            }

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            raise

    async def analyze_with_images(
        self,
        prompt: str,
        image_urls: List[str],
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Send text + image prompt to Gemini for multimodal analysis.

        Args:
            prompt: User prompt
            image_urls: List of image URLs
            system_prompt: Optional system instructions
            temperature: Generation temperature
            max_tokens: Maximum output tokens

        Returns:
            Same format as analyze_text()
        """
        try:
            # Build prompt parts
            prompt_parts = []

            if system_prompt:
                prompt_parts.append(system_prompt)

            prompt_parts.append(prompt)

            # Add images (Gemini supports URLs directly)
            for url in image_urls:
                prompt_parts.append({
                    "mime_type": "image/jpeg",
                    "data": url  # Gemini can handle URLs
                })

            # Configure generation
            generation_config = genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            # Generate response
            response = self.model.generate_content(
                prompt_parts,
                generation_config=generation_config,
            )

            # Extract text
            content = response.text

            # Estimate costs (including images)
            # Images cost more - roughly 258 tokens per image
            input_tokens = len(prompt.split()) * 1.3 + len(image_urls) * 258
            output_tokens = len(content.split()) * 1.3

            pricing = self.PRICING.get(self.model_name, self.PRICING["gemini-2.0-flash-exp"])
            cost = (input_tokens * pricing["input"] / 1_000_000 +
                   output_tokens * pricing["output"] / 1_000_000)

            tokens_used = {
                "input": int(input_tokens),
                "output": int(output_tokens),
                "total": int(input_tokens + output_tokens)
            }

            logger.info(f"Gemini vision analysis complete: {tokens_used['total']} tokens, ${cost:.6f}")

            return {
                "content": content,
                "tokens_used": tokens_used,
                "cost": cost,
                "model": self.model_name
            }

        except Exception as e:
            logger.error(f"Gemini vision API error: {e}", exc_info=True)
            raise

    def get_pricing(self) -> Dict[str, float]:
        """Get pricing information for current model."""
        return self.PRICING.get(self.model_name, self.PRICING["gemini-2.0-flash-exp"])
