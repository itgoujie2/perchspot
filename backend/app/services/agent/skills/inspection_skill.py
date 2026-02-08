"""
Inspection Skill - Analyzes home inspection reports
"""
import logging
from typing import Dict, Any

from app.services.agent.skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)


class InspectionSkill(BaseSkill):
    """
    Analyzes home inspection report text to extract:
    - Issues by system (roof, HVAC, plumbing, electrical, foundation, etc.)
    - Severity classification
    - Estimated repair costs
    - Overall property condition score
    """

    def __init__(self):
        super().__init__()
        # Override skill name since it doesn't follow the standard pattern
        self.skill_name = "inspection-analysis"

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze inspection report text.

        Args:
            address: Property address
            **kwargs:
                - document_text: Required - full text from inspection report PDF
                - filename: Optional - original filename

        Returns:
            Structured analysis with score, issues, costs, etc.
        """
        try:
            self._reset_cost_tracking()
            self._load_skill()

            document_text = kwargs.get('document_text')
            if not document_text:
                return self._error_result("No document text provided")

            filename = kwargs.get('filename', 'inspection_report.pdf')
            logger.info(f"InspectionSkill: Analyzing inspection report for {address} ({filename})")

            analysis = await self._analyze_inspection(address, document_text, filename)
            analysis['cost_summary'] = self.get_cost_summary()

            logger.info(
                f"InspectionSkill: Analysis complete. Score: {analysis.get('score')}, "
                f"Issues: {len(analysis.get('details', {}).get('issues', []))}, "
                f"Cost: ${self.total_cost:.6f}"
            )
            return analysis

        except Exception as e:
            logger.error(f"InspectionSkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    async def _analyze_inspection(
        self, address: str, document_text: str, filename: str
    ) -> Dict[str, Any]:
        """Build prompt and send to Claude for analysis."""

        # Truncate very long documents to stay within context limits
        # Keep first 30k chars which should cover most inspection reports
        max_chars = 30000
        if len(document_text) > max_chars:
            document_text = document_text[:max_chars] + "\n\n[... document truncated ...]"

        prompt = f"""{self.skill_data['full_context']}

---

PROPERTY ADDRESS: {address}
DOCUMENT: {filename}

INSPECTION REPORT TEXT:
---
{document_text}
---

Analyze this inspection report and extract all issues, categorize by system, assess severity, and estimate repair costs.

Provide your analysis in the JSON format specified in the skill documentation.

Return ONLY valid JSON, no other text.
"""

        response_text = await self._call_claude(prompt=prompt, max_tokens=4096)
        analysis = self._parse_json_response(response_text)

        # Add metadata
        analysis['raw_data'] = {
            'address': address,
            'filename': filename,
            'document_chars': len(document_text),
        }

        return analysis

    def _error_result(self, error_message: str) -> Dict[str, Any]:
        """Return error result structure."""
        return {
            'score': 0,
            'confidence': 'low',
            'reasoning': f'Analysis failed: {error_message}',
            'strengths': [],
            'concerns': ['Inspection analysis could not be completed'],
            'details': {
                'issues': [],
                'total_estimated_repairs': 'Unknown',
            },
            'error': error_message
        }
