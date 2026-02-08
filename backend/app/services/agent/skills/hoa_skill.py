"""
HOA Skill - Analyzes HOA documents (CC&Rs, bylaws, budgets, reserve studies)
"""
import logging
from typing import Dict, Any

from app.services.agent.skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)


class HOASkill(BaseSkill):
    """
    Analyzes HOA documents to extract:
    - Monthly/annual fees and what they cover
    - Reserve fund health
    - Rental restrictions
    - Pet restrictions
    - Special assessment history
    - Pending litigation
    - Overall HOA financial health score
    """

    def __init__(self):
        super().__init__()
        # Override skill name since it doesn't follow the standard pattern
        self.skill_name = "hoa-analysis"

    async def analyze(self, address: str, **kwargs) -> Dict[str, Any]:
        """
        Analyze HOA document text.

        Args:
            address: Property address
            **kwargs:
                - document_text: Required - full text from HOA document PDF
                - filename: Optional - original filename

        Returns:
            Structured analysis with score, fees, restrictions, etc.
        """
        try:
            self._reset_cost_tracking()
            self._load_skill()

            document_text = kwargs.get('document_text')
            if not document_text:
                return self._error_result("No document text provided")

            filename = kwargs.get('filename', 'hoa_document.pdf')
            logger.info(f"HOASkill: Analyzing HOA document for {address} ({filename})")

            analysis = await self._analyze_hoa(address, document_text, filename)
            analysis['cost_summary'] = self.get_cost_summary()

            logger.info(
                f"HOASkill: Analysis complete. Score: {analysis.get('score')}, "
                f"Monthly fee: ${analysis.get('details', {}).get('monthly_fee', 'N/A')}, "
                f"Cost: ${self.total_cost:.6f}"
            )
            return analysis

        except Exception as e:
            logger.error(f"HOASkill analysis failed: {e}", exc_info=True)
            return self._error_result(str(e))

    async def _analyze_hoa(
        self, address: str, document_text: str, filename: str
    ) -> Dict[str, Any]:
        """Build prompt and send to Claude for analysis."""

        # Truncate very long documents to stay within context limits
        # HOA docs can be quite long, keep first 40k chars
        max_chars = 40000
        if len(document_text) > max_chars:
            document_text = document_text[:max_chars] + "\n\n[... document truncated ...]"

        prompt = f"""{self.skill_data['full_context']}

---

PROPERTY ADDRESS: {address}
DOCUMENT: {filename}

HOA DOCUMENT TEXT:
---
{document_text}
---

Analyze this HOA document and extract all relevant information about fees, restrictions, financial health, and governance.

If specific information is not available in the document, use null for that field rather than making assumptions.

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
            'concerns': ['HOA analysis could not be completed'],
            'details': {
                'monthly_fee': None,
                'reserve_fund': {},
                'rental_restrictions': {},
                'pet_restrictions': {},
            },
            'error': error_message
        }
