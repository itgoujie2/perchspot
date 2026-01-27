"""
Base class for all granular analysis tools.
Each tool loads its specific context prompt and performs focused analysis.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Base class for granular analysis tools.

    Each tool should:
    1. Load its specific context prompt from markdown file
    2. Perform focused analysis on one specific aspect
    3. Return structured results with confidence scores
    """

    def __init__(self):
        self.name = self.__class__.__name__
        self.context_content: Optional[str] = None
        self.context_path: Optional[Path] = None

    def load_context(self, context_file_path: str) -> str:
        """
        Load context prompt from markdown file.

        Args:
            context_file_path: Relative path from context_prompts/ directory

        Returns:
            Content of the context file as string
        """
        try:
            # Get the context_prompts directory
            current_file = Path(__file__)
            tools_dir = current_file.parent.parent  # Go up to agent/
            context_dir = tools_dir / "context_prompts"

            # Build full path
            full_path = context_dir / context_file_path

            if not full_path.exists():
                raise FileNotFoundError(f"Context file not found: {full_path}")

            # Read and cache the content
            with open(full_path, 'r', encoding='utf-8') as f:
                self.context_content = f.read()

            self.context_path = full_path
            logger.info(f"[{self.name}] Loaded context from {context_file_path}")

            return self.context_content

        except Exception as e:
            logger.error(f"[{self.name}] Error loading context: {e}")
            raise

    @abstractmethod
    async def analyze(self, data: Dict[str, Any], llm_client: Any) -> Dict[str, Any]:
        """
        Perform the specific analysis using loaded context and LLM.

        Args:
            data: Input data specific to this tool (property info, address, etc.)
            llm_client: LLM client for making API calls

        Returns:
            Dictionary with analysis results:
            {
                "tool_name": str,
                "score": float (0-100),
                "grade": str (A-F),
                "confidence": str (high/medium/low),
                "analysis": str,
                "key_findings": List[str],
                "concerns": List[str],
                "data_points": Dict[str, Any],
                "raw_data": Dict[str, Any]
            }
        """
        pass

    def create_llm_prompt(self, instruction: str, data: Dict[str, Any]) -> str:
        """
        Create a prompt combining context, instruction, and data.

        Args:
            instruction: Specific task instruction for the LLM
            data: Input data to analyze

        Returns:
            Formatted prompt string
        """
        if not self.context_content:
            raise ValueError(f"[{self.name}] Context not loaded. Call load_context() first.")

        prompt = f"""# Analysis Context

{self.context_content}

---

# Analysis Task

{instruction}

# Input Data

{self._format_data(data)}

# Required Output Format

Provide a JSON response with the following structure:
{{
    "score": <float 0-100>,
    "grade": "<A-F letter grade>",
    "confidence": "<high/medium/low>",
    "analysis": "<detailed analysis paragraph>",
    "key_findings": ["<finding 1>", "<finding 2>", ...],
    "concerns": ["<concern 1>", "<concern 2>", ...],
    "data_points": {{
        "<metric_name>": "<value>",
        ...
    }}
}}

Ensure your analysis strictly follows the methodology and guidelines in the context above.
"""
        return prompt

    def _format_data(self, data: Dict[str, Any]) -> str:
        """Format input data as readable text for LLM prompt."""
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"\n**{key}:**")
                for sub_key, sub_value in value.items():
                    lines.append(f"  - {sub_key}: {sub_value}")
            elif isinstance(value, list):
                lines.append(f"\n**{key}:**")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"**{key}:** {value}")
        return "\n".join(lines)

    def validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize tool result structure.

        Args:
            result: Raw result from analyze() method

        Returns:
            Validated and normalized result
        """
        required_fields = ["score", "grade", "confidence", "analysis"]

        for field in required_fields:
            if field not in result:
                logger.warning(f"[{self.name}] Missing required field: {field}")
                result[field] = self._get_default_value(field)

        # Ensure score is in 0-100 range
        if "score" in result:
            result["score"] = max(0, min(100, float(result["score"])))

        # Add metadata
        result["tool_name"] = self.name
        result["context_file"] = str(self.context_path) if self.context_path else None

        return result

    def _get_default_value(self, field: str) -> Any:
        """Get default value for missing field."""
        defaults = {
            "score": 0,
            "grade": "F",
            "confidence": "low",
            "analysis": "Analysis unavailable",
            "key_findings": [],
            "concerns": ["Insufficient data for analysis"],
            "data_points": {}
        }
        return defaults.get(field, None)

    async def execute(self, data: Dict[str, Any], llm_client: Any) -> Dict[str, Any]:
        """
        Main execution method that orchestrates the analysis.

        Args:
            data: Input data for analysis
            llm_client: LLM client instance

        Returns:
            Validated analysis result
        """
        try:
            logger.info(f"[{self.name}] Starting analysis...")

            # Perform the analysis
            result = await self.analyze(data, llm_client)

            # Validate and normalize
            validated_result = self.validate_result(result)

            logger.info(f"[{self.name}] Analysis complete. Score: {validated_result['score']}/100")

            return validated_result

        except Exception as e:
            logger.error(f"[{self.name}] Analysis failed: {e}")
            return self.validate_result({
                "score": 0,
                "grade": "F",
                "confidence": "low",
                "analysis": f"Analysis failed: {str(e)}",
                "key_findings": [],
                "concerns": [f"Error during analysis: {str(e)}"],
                "data_points": {},
                "error": str(e)
            })
