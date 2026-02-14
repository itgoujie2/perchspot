"""
Auto-Tagging Service — Use LLM to automatically suggest @applies_when tags for knowledge points

Analyzes each knowledge point's content and suggests appropriate attribute-based tags
for better knowledge retrieval during property analysis.
"""
import json
import logging
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

from anthropic import Anthropic

from app.config import settings
from app.services.knowledge.storage_service import get_storage_service

logger = logging.getLogger(__name__)

# LLM prompt for tag suggestion
TAG_SUGGESTION_PROMPT = """You are a real estate knowledge tagging assistant. Your job is to analyze knowledge content and suggest @applies_when tags that determine when this knowledge should surface during property analysis.

## Available Attributes and Operators

| Attribute | Type | Operators | Examples |
|-----------|------|-----------|----------|
| year_built | number | <, >, <=, >=, = | year_built<1990, year_built>=2000 |
| has_hoa | boolean | = | has_hoa=true, has_hoa=false |
| hoa_fee | number | <, >, <=, >= | hoa_fee>300, hoa_fee<100 |
| property_type | string | =, contains | property_type=condo, property_type contains townhome |
| lot_size_sqft | number | <, >, <=, >= | lot_size_sqft<5000, lot_size_sqft>10000 |
| square_feet | number | <, >, <=, >= | square_feet<1500, square_feet>3000 |
| bedrooms | number | <, >, <=, >=, = | bedrooms>=4, bedrooms=1 |
| bathrooms | number | <, >, <=, >=, = | bathrooms>=3 |
| stories | number | =, >, < | stories=2, stories>1 |
| garage_spaces | number | =, >, <, >= | garage_spaces=0, garage_spaces>=2 |
| has_pool | boolean | = | has_pool=true |
| has_basement | boolean | = | has_basement=true |

## Guidelines

1. **Only add tags if the knowledge CLEARLY applies to specific property attributes**
   - "Homes built before 1980 may have lead paint" → year_built<1980
   - "HOA fees can vary widely" → NO TAG (too generic)

2. **Be conservative** - if uncertain, don't add a tag. Better to miss a match than to surface irrelevant knowledge.

3. **Multiple tags mean ALL must match** - use sparingly for narrow conditions

4. **Priority levels**:
   - high: Critical safety, legal, or major financial concerns
   - medium: Important considerations but not critical
   - low: Nice-to-know information

## Examples

Knowledge: "Galvanized steel pipes were commonly used before 1960 and are prone to corrosion and reduced water pressure after 50+ years."
Tags: [{"attribute": "year_built", "operator": "<", "value": 1960}]
Priority: high

Knowledge: "Townhomes share walls with neighbors, which can lead to noise transfer issues."
Tags: [{"attribute": "property_type", "operator": "contains", "value": "townhome"}]
Priority: medium

Knowledge: "Seattle has excellent public transportation options."
Tags: [] (no property-specific attributes apply)
Priority: medium

Knowledge: "Small HOA communities (under 50 units) often have higher per-unit fees due to fewer members sharing costs."
Tags: [{"attribute": "has_hoa", "operator": "=", "value": true}]
Priority: medium

## Your Task

Analyze the following knowledge content and return a JSON response:

```json
{
  "applies_when": [
    {"attribute": "...", "operator": "...", "value": ...}
  ],
  "priority": "high|medium|low",
  "reasoning": "Brief explanation of why these tags apply or why no tags apply"
}
```

If no tags apply, return an empty array for applies_when.

---

KNOWLEDGE CONTENT:
{content}

KNOWLEDGE CATEGORY: {category}
SOURCE FILE: {source_file}

Return ONLY the JSON response, no other text."""


@dataclass
class TagSuggestion:
    """Suggested tags for a knowledge point."""
    applies_when: List[Dict[str, Any]]
    priority: str
    reasoning: str


@dataclass
class AutoTagResult:
    """Result of auto-tagging a single point."""
    point_id: str
    text_preview: str
    old_tags: List[Dict[str, Any]]
    new_tags: List[Dict[str, Any]]
    old_priority: str
    new_priority: str
    reasoning: str
    success: bool
    error: Optional[str] = None


class AutoTaggingService:
    """Service for automatically tagging knowledge points using LLM."""

    def __init__(self):
        self.storage = get_storage_service()
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def _call_llm(self, content: str, category: str, source_file: str) -> TagSuggestion:
        """Call LLM to suggest tags for a knowledge point."""
        prompt = TAG_SUGGESTION_PROMPT.format(
            content=content,
            category=category,
            source_file=source_file,
        )

        try:
            response = self.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as api_err:
            logger.error(f"Anthropic API error: {api_err}")
            return TagSuggestion(
                applies_when=[],
                priority="medium",
                reasoning=f"API error: {str(api_err)[:100]}"
            )

        # Parse JSON response
        try:
            response_text = response.content[0].text.strip()
            logger.debug(f"LLM raw response: {response_text[:200]}")
        except Exception as resp_err:
            logger.error(f"Error accessing response content: {resp_err}")
            return TagSuggestion(
                applies_when=[],
                priority="medium",
                reasoning=f"Response error: {str(resp_err)[:100]}"
            )

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1).strip()

        # Also try to find JSON object directly if no code block
        if not response_text.startswith('{'):
            # Find the first { and try to extract balanced JSON
            start_idx = response_text.find('{')
            if start_idx != -1:
                # Count braces to find matching closing brace
                depth = 0
                end_idx = start_idx
                for i, char in enumerate(response_text[start_idx:], start_idx):
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            end_idx = i
                            break
                if depth == 0:
                    response_text = response_text[start_idx:end_idx + 1]

        try:
            data = json.loads(response_text)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}\nResponse: {response_text[:500]}")
            # Return empty suggestion on parse error
            return TagSuggestion(
                applies_when=[],
                priority="medium",
                reasoning=f"Parse error: {str(e)[:100]}"
            )

        # Validate and normalize applies_when
        try:
            raw_applies_when = data.get("applies_when", [])
            validated_applies_when = []

            if isinstance(raw_applies_when, list):
                for item in raw_applies_when:
                    try:
                        if isinstance(item, dict):
                            # Normalize keys (strip quotes, lowercase)
                            normalized = {}
                            for k, v in item.items():
                                clean_key = str(k).strip().strip('"\'').lower()
                                normalized[clean_key] = v

                            # Ensure required keys exist
                            if "attribute" in normalized and "operator" in normalized and "value" in normalized:
                                validated_applies_when.append({
                                    "attribute": str(normalized["attribute"]).lower().strip(),
                                    "operator": str(normalized["operator"]).lower().strip(),
                                    "value": normalized["value"],
                                })
                            else:
                                logger.debug(f"Skipping applies_when item missing keys: {item}")
                    except Exception as item_err:
                        logger.warning(f"Error processing applies_when item {item}: {item_err}")
                        continue

            # Validate priority
            priority = str(data.get("priority", "medium")).lower().strip()
            if priority not in ("high", "medium", "low"):
                priority = "medium"

            reasoning = str(data.get("reasoning", ""))

            return TagSuggestion(
                applies_when=validated_applies_when,
                priority=priority,
                reasoning=reasoning,
            )

        except Exception as e:
            logger.warning(f"Error validating LLM response data: {e}\nData: {data}")
            return TagSuggestion(
                applies_when=[],
                priority="medium",
                reasoning=f"Validation error: {str(e)[:100]}"
            )

    def auto_tag_point(self, point_id: str, text: str, category: str, source_file: str,
                       current_tags: List[Dict], current_priority: str,
                       dry_run: bool = False) -> AutoTagResult:
        """
        Auto-tag a single knowledge point.

        Args:
            point_id: Qdrant point ID
            text: Knowledge point text content
            category: Knowledge category
            source_file: Source file name
            current_tags: Current applies_when tags
            current_priority: Current priority
            dry_run: If True, don't actually update the point

        Returns:
            AutoTagResult with old/new tags and status
        """
        try:
            suggestion = self._call_llm(text, category, source_file)

            result = AutoTagResult(
                point_id=point_id,
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                old_tags=current_tags,
                new_tags=suggestion.applies_when,
                old_priority=current_priority,
                new_priority=suggestion.priority,
                reasoning=suggestion.reasoning,
                success=True,
            )

            if not dry_run and (suggestion.applies_when or suggestion.priority != current_priority):
                # Update the point's payload
                self.storage.update_point_payload(
                    point_id=point_id,
                    payload_updates={
                        "applies_when": suggestion.applies_when,
                        "priority": suggestion.priority,
                    }
                )

            return result

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Error auto-tagging point {point_id}: {e}\n{tb}")
            return AutoTagResult(
                point_id=point_id,
                text_preview=text[:100] + "..." if len(text) > 100 else text,
                old_tags=current_tags,
                new_tags=[],
                old_priority=current_priority,
                new_priority=current_priority,
                reasoning="",
                success=False,
                error=str(e),
            )

    def auto_tag_all(
        self,
        dry_run: bool = False,
        only_untagged: bool = True,
        source_filter: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Auto-tag all knowledge points (or those matching filters).

        Args:
            dry_run: If True, don't actually update points, just return suggestions
            only_untagged: If True, only process points without existing tags
            source_filter: Optional source file filter
            progress_callback: Optional callback(current, total, result) for progress

        Returns:
            Summary of tagging results
        """
        results = []
        total_processed = 0
        total_tagged = 0
        total_skipped = 0
        total_errors = 0

        # First, count total points for progress
        total_points = 0
        for point in self.storage.scroll_all_points(batch_size=1000, with_payload=True):
            payload = point.payload or {}

            # Apply filters
            if source_filter and payload.get("source_file") != source_filter:
                continue

            if only_untagged:
                existing_tags = payload.get("applies_when", [])
                if existing_tags:
                    continue

            total_points += 1

        logger.info(f"Auto-tagging {total_points} knowledge points (dry_run={dry_run})")

        # Process points
        current = 0
        for point in self.storage.scroll_all_points(batch_size=100, with_payload=True):
            payload = point.payload or {}

            # Apply filters
            if source_filter and payload.get("source_file") != source_filter:
                continue

            existing_tags = payload.get("applies_when", [])
            if only_untagged and existing_tags:
                total_skipped += 1
                continue

            current += 1
            total_processed += 1

            text = payload.get("text", "")
            category = payload.get("category", "")
            source_file = payload.get("source_file", "")
            current_priority = payload.get("priority", "medium")

            result = self.auto_tag_point(
                point_id=str(point.id),
                text=text,
                category=category,
                source_file=source_file,
                current_tags=existing_tags,
                current_priority=current_priority,
                dry_run=dry_run,
            )

            results.append(result)

            if result.success and result.new_tags:
                total_tagged += 1
            elif not result.success:
                total_errors += 1

            if progress_callback:
                progress_callback(current, total_points, result)

        return {
            "total_processed": total_processed,
            "total_tagged": total_tagged,
            "total_skipped": total_skipped,
            "total_errors": total_errors,
            "dry_run": dry_run,
            "results": [
                {
                    "point_id": r.point_id,
                    "text_preview": r.text_preview,
                    "old_tags": r.old_tags,
                    "new_tags": r.new_tags,
                    "old_priority": r.old_priority,
                    "new_priority": r.new_priority,
                    "reasoning": r.reasoning,
                    "success": r.success,
                    "error": r.error,
                }
                for r in results
            ],
        }


_instance = None


def get_auto_tagging_service() -> AutoTaggingService:
    """Get or create the singleton AutoTaggingService."""
    global _instance
    if _instance is None:
        _instance = AutoTaggingService()
    return _instance
