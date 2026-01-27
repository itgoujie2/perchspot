"""
Claude API client for property analysis
"""
import logging
import json
import base64
from typing import Dict, Any, List, Optional
from anthropic import AsyncAnthropic

from app.config import settings

logger = logging.getLogger(__name__)


class ClaudeClient:
    """
    Wrapper for Anthropic Claude API with cost tracking
    """

    # Pricing (per million tokens) - update as needed
    PRICING = {
        "claude-3-5-sonnet-20241022": {
            "input": 3.00,
            "output": 15.00,
        },
        "claude-3-haiku-20240307": {
            "input": 0.25,
            "output": 1.25,
        },
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.client = AsyncAnthropic(api_key=self.api_key)
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    async def analyze_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send text-only prompt to Claude

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            temperature: Override default temperature
            model: Override default model

        Returns:
            Dictionary with response and usage info
        """
        try:
            if temperature is None:
                temperature = self.temperature

            if model is None:
                model = self.model

            if system_prompt is None:
                system_prompt = "You are a professional real estate analyst."

            message = await self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )

            # Extract response text
            response_text = message.content[0].text

            # Calculate cost
            cost = self._calculate_cost(
                model=model,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
            )

            logger.info(
                f"Claude API call: {message.usage.input_tokens} in, "
                f"{message.usage.output_tokens} out, ${cost:.4f}"
            )

            # Try to parse JSON response
            try:
                parsed_response = self._parse_json_response(response_text)
            except json.JSONDecodeError:
                logger.warning("Response is not valid JSON, returning as text")
                parsed_response = {"response": response_text}

            return {
                "response": parsed_response,
                "raw_response": response_text,
                "usage": {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                    "total_tokens": message.usage.input_tokens + message.usage.output_tokens,
                },
                "cost": cost,
                "model": model,
            }

        except Exception as e:
            logger.error(f"Claude API error: {e}", exc_info=True)
            raise

    async def analyze_with_images(
        self,
        prompt: str,
        images: List[bytes],
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send prompt with images to Claude Vision API

        Args:
            prompt: Text prompt
            images: List of image bytes
            system_prompt: System prompt (optional)
            model: Override default model

        Returns:
            Dictionary with response and usage info
        """
        try:
            if model is None:
                model = self.model

            if system_prompt is None:
                system_prompt = "You are a professional real estate analyst with expertise in property inspection."

            # Prepare image content
            content = []

            for img_bytes in images:
                # Encode image to base64
                b64_image = base64.standard_b64encode(img_bytes).decode('utf-8')

                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64_image,
                    }
                })

            # Add text prompt
            content.append({
                "type": "text",
                "text": prompt
            })

            message = await self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": content}]
            )

            # Extract response
            response_text = message.content[0].text

            # Calculate cost (images add to input tokens)
            cost = self._calculate_cost(
                model=model,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                num_images=len(images),
            )

            logger.info(
                f"Claude Vision API call: {len(images)} images, "
                f"{message.usage.input_tokens} in, {message.usage.output_tokens} out, "
                f"${cost:.4f}"
            )

            # Try to parse JSON response
            try:
                parsed_response = self._parse_json_response(response_text)
            except json.JSONDecodeError:
                logger.warning("Response is not valid JSON, returning as text")
                parsed_response = {"response": response_text}

            return {
                "response": parsed_response,
                "raw_response": response_text,
                "usage": {
                    "input_tokens": message.usage.input_tokens,
                    "output_tokens": message.usage.output_tokens,
                    "total_tokens": message.usage.input_tokens + message.usage.output_tokens,
                },
                "cost": cost,
                "model": model,
            }

        except Exception as e:
            logger.error(f"Claude Vision API error: {e}", exc_info=True)
            raise

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Extract JSON from Claude response

        Claude sometimes wraps JSON in markdown code blocks
        """
        # Try direct JSON parse first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
            return json.loads(json_str)
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()
            return json.loads(json_str)
        else:
            raise json.JSONDecodeError("No JSON found in response", response_text, 0)

    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        num_images: int = 0,
    ) -> float:
        """
        Calculate API call cost

        Args:
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
            num_images: Number of images (approximate cost)

        Returns:
            Cost in USD
        """
        if model not in self.PRICING:
            logger.warning(f"Unknown model pricing: {model}, using Sonnet pricing")
            model = "claude-3-5-sonnet-20241022"

        pricing = self.PRICING[model]

        cost = (
            input_tokens * pricing["input"] / 1_000_000 +
            output_tokens * pricing["output"] / 1_000_000
        )

        # Add approximate cost for images (~$0.005 per image)
        if num_images > 0:
            cost += num_images * 0.005

        return cost
