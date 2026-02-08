"""
Notes Manager for incremental analysis storage.

Instead of keeping all analysis data in memory, we write intermediate results
to a markdown notes file. This enables:
- Memory efficiency (no large objects in RAM)
- Transparency (inspect intermediate results)
- Resumability (continue from checkpoint if analysis fails)
- Caching (reuse previous analysis for same address)
- Auditability (keep history in S3)
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class NotesManager:
    """
    Manages markdown notes files for property analysis.

    Development mode: Keep notes in temp folder for debugging
    Production mode: Upload to S3 and delete local file after report generation
    """

    def __init__(
        self,
        notes_dir: Optional[Path] = None,
        environment: str = "development"
    ):
        """
        Initialize notes manager.

        Args:
            notes_dir: Directory for notes files (default: ./analysis_notes)
            environment: "development" or "production"
        """
        self.environment = environment

        # Set notes directory
        if notes_dir is None:
            # Default to backend/analysis_notes/
            backend_dir = Path(__file__).parent.parent.parent.parent
            self.notes_dir = backend_dir / "analysis_notes"
        else:
            self.notes_dir = Path(notes_dir)

        # Create directory if it doesn't exist
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"NotesManager initialized. Dir: {self.notes_dir}, Env: {environment}")

    def normalize_address(self, address: str) -> str:
        """
        Normalize address into a valid filename.

        Examples:
            "522 Glacier Walk SE" -> "522_glacier_walk_se"
            "123 Main St, San Francisco, CA" -> "123_main_st_san_francisco_ca"
        """
        # Convert to lowercase
        normalized = address.lower()

        # Remove special characters, keep alphanumeric and spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)

        # Replace spaces with underscores
        normalized = re.sub(r'\s+', '_', normalized)

        # Remove consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)

        # Remove leading/trailing underscores
        normalized = normalized.strip('_')

        return normalized

    def get_notes_path(self, address: str) -> Path:
        """Get full path to notes file for an address."""
        filename = f"{self.normalize_address(address)}.md"
        return self.notes_dir / filename

    def notes_exist(self, address: str) -> bool:
        """Check if notes file exists for this address."""
        notes_path = self.get_notes_path(address)
        exists = notes_path.exists()

        if exists:
            logger.info(f"Found existing notes for: {address} at {notes_path}")
        else:
            logger.info(f"No existing notes for: {address}")

        return exists

    def create_notes(self, address: str, property_info: Dict[str, Any]) -> Path:
        """
        Create new notes file with header.

        Args:
            address: Property address
            property_info: Basic property information

        Returns:
            Path to created notes file
        """
        notes_path = self.get_notes_path(address)

        # Create header
        header = f"""# Property Analysis Notes

**Address:** {address}
**Analysis Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Status:** In Progress

---

## Property Information

"""

        # Add property info
        if property_info:
            for key, value in property_info.items():
                header += f"- **{key.replace('_', ' ').title()}:** {value}\n"

        header += "\n---\n\n"

        # Write header
        with open(notes_path, 'w', encoding='utf-8') as f:
            f.write(header)

        logger.info(f"Created notes file: {notes_path}")

        return notes_path

    def append_section(
        self,
        address: str,
        section_title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Append a new section to the notes file.

        Args:
            address: Property address
            section_title: Title for this section (e.g., "School Quality Analysis")
            content: Content to append
            metadata: Optional metadata to include (timestamps, scores, etc.)
        """
        notes_path = self.get_notes_path(address)

        if not notes_path.exists():
            logger.warning(f"Notes file doesn't exist, creating: {notes_path}")
            self.create_notes(address, {})

        # Build section
        section = f"## {section_title}\n\n"

        # Add metadata if provided
        if metadata:
            section += "**Metadata:**\n"
            for key, value in metadata.items():
                section += f"- {key}: {value}\n"
            section += "\n"

        # Add content
        section += content + "\n\n---\n\n"

        # Append to file
        with open(notes_path, 'a', encoding='utf-8') as f:
            f.write(section)

        logger.debug(f"Appended section '{section_title}' to {notes_path}")

    def append_tool_result(
        self,
        address: str,
        tool_name: str,
        result: Dict[str, Any]
    ):
        """
        Append a tool analysis result to notes.

        Args:
            address: Property address
            tool_name: Name of the tool that produced this result
            result: Tool result dictionary
        """
        # Format tool name as section title
        section_title = f"{tool_name.replace('_', ' ').title()}"

        # Build content
        content = f"**Score:** {result.get('score', 'N/A')}/100\n"
        content += f"**Grade:** {result.get('grade', 'N/A')}\n"
        content += f"**Confidence:** {result.get('confidence', 'N/A')}\n\n"

        # Analysis
        content += "### Analysis\n\n"
        content += result.get('analysis', 'No analysis available.') + "\n\n"

        # Key findings
        if result.get('key_findings'):
            content += "### Key Findings\n\n"
            for finding in result['key_findings']:
                content += f"- ✓ {finding}\n"
            content += "\n"

        # Concerns
        if result.get('concerns'):
            content += "### Concerns\n\n"
            for concern in result['concerns']:
                content += f"- ⚠️ {concern}\n"
            content += "\n"

        # Data points
        if result.get('data_points'):
            content += "### Key Data Points\n\n"
            for key, value in result['data_points'].items():
                content += f"- **{key.replace('_', ' ').title()}:** {value}\n"
            content += "\n"

        # Metadata
        metadata = {
            "Tool": tool_name,
            "Timestamp": datetime.now().strftime("%H:%M:%S"),
            "Context File": result.get('context_file', 'N/A')
        }

        self.append_section(address, section_title, content, metadata)

    def append_raw_scraped_data(
        self,
        address: str,
        scraped_data: Dict[str, Any],
        source: str = "redfin"
    ):
        """
        Append raw scraped data to notes (for debugging/reference).

        Args:
            address: Property address
            scraped_data: Raw data dictionary from scraper
            source: Data source (e.g., "redfin", "zillow")
        """
        section_title = f"Raw Scraped Data ({source.title()})"

        # Format the scraped data as readable markdown
        content = "```json\n"
        content += json.dumps(scraped_data, indent=2, default=str)
        content += "\n```\n"

        metadata = {
            "Source": source,
            "Timestamp": datetime.now().strftime("%H:%M:%S"),
            "Fields Count": len(scraped_data)
        }

        self.append_section(address, section_title, content, metadata)

        logger.info(f"Appended {len(scraped_data)} raw fields from {source}")

    def append_summary(
        self,
        address: str,
        overall_score: float,
        overall_grade: str,
        category_scores: Dict[str, float],
        recommendation: str
    ):
        """
        Append final summary to notes.

        Args:
            address: Property address
            overall_score: Overall score (0-100)
            overall_grade: Overall grade (A-F)
            category_scores: Scores by category
            recommendation: Overall recommendation
        """
        content = f"**Overall Score:** {overall_score}/100\n"
        content += f"**Overall Grade:** {overall_grade}\n\n"

        content += "### Category Scores\n\n"
        for category, score in category_scores.items():
            content += f"- **{category.replace('_', ' ').title()}:** {score}/100\n"

        content += f"\n### Recommendation\n\n{recommendation}\n"

        metadata = {
            "Status": "Complete",
            "Completion Time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        self.append_section(address, "Final Summary", content, metadata)

    def read_notes(self, address: str) -> Optional[str]:
        """
        Read complete notes file content.

        Args:
            address: Property address

        Returns:
            Notes content as string, or None if file doesn't exist
        """
        notes_path = self.get_notes_path(address)

        if not notes_path.exists():
            logger.warning(f"Notes file not found: {notes_path}")
            return None

        with open(notes_path, 'r', encoding='utf-8') as f:
            content = f.read()

        logger.info(f"Read notes file: {notes_path} ({len(content)} chars)")

        return content

    def parse_notes_for_report(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Parse notes file to extract structured data for report generation.

        Args:
            address: Property address

        Returns:
            Dictionary with parsed sections, or None if notes don't exist
        """
        content = self.read_notes(address)

        if not content:
            return None

        # Extract sections using regex
        sections = {}

        # Extract overall summary
        summary_match = re.search(
            r'## Final Summary.*?Overall Score:\*\* ([\d.]+)/100.*?Overall Grade:\*\* ([A-F])',
            content,
            re.DOTALL
        )

        if summary_match:
            sections['overall_score'] = float(summary_match.group(1))
            sections['overall_grade'] = summary_match.group(2)

        # Extract category scores from Final Summary
        category_scores = {}
        category_pattern = r'- \*\*(\w+(?:\s+\w+)*):\*\* ([\d.]+)/100'
        for match in re.finditer(category_pattern, content):
            category_name = match.group(1).lower().replace(' ', '_')
            category_scores[category_name] = float(match.group(2))
        sections['category_scores'] = category_scores

        # Extract recommendation from Final Summary
        recommendation_match = re.search(
            r'### Recommendation\n\n(.+?)(?:\n\n|$)',
            content,
            re.DOTALL
        )
        if recommendation_match:
            sections['recommendation'] = recommendation_match.group(1).strip()
        else:
            sections['recommendation'] = "No specific recommendation provided."

        # Extract detailed tool results with analysis, key findings, and concerns
        sections['tool_results'] = []

        # Split content by tool sections (## headers that aren't "Property Information" or "Final Summary")
        tool_section_pattern = r'## ([^#\n]+?)\n\n\*\*Metadata:\*\*(.*?)(?=\n## |\Z)'

        for match in re.finditer(tool_section_pattern, content, re.DOTALL):
            tool_name = match.group(1).strip()
            tool_content = match.group(2)

            # Skip non-tool sections
            if tool_name in ['Property Information', 'Final Summary']:
                continue

            # Extract score, grade, confidence
            score_match = re.search(r'\*\*Score:\*\* ([\d.]+)/100', tool_content)
            grade_match = re.search(r'\*\*Grade:\*\* ([A-F])', tool_content)
            confidence_match = re.search(r'\*\*Confidence:\*\* (\w+)', tool_content)

            # Extract analysis text
            analysis_match = re.search(r'### Analysis\n\n(.+?)(?=\n###|\Z)', tool_content, re.DOTALL)

            # Extract key findings
            key_findings = []
            findings_section = re.search(r'### Key Findings\n\n(.+?)(?=\n###|\Z)', tool_content, re.DOTALL)
            if findings_section:
                # Extract bullet points
                findings_text = findings_section.group(1)
                for finding in re.findall(r'- ✓ (.+?)(?=\n-|\Z)', findings_text, re.DOTALL):
                    key_findings.append(finding.strip())

            # Extract concerns
            concerns = []
            concerns_section = re.search(r'### Concerns\n\n(.+?)(?=\n###|\Z)', tool_content, re.DOTALL)
            if concerns_section:
                # Extract bullet points
                concerns_text = concerns_section.group(1)
                for concern in re.findall(r'- ⚠️ (.+?)(?=\n-|\Z)', concerns_text, re.DOTALL):
                    concerns.append(concern.strip())

            tool_result = {
                'tool_name': tool_name,
                'score': float(score_match.group(1)) if score_match else 0,
                'grade': grade_match.group(1) if grade_match else 'F',
                'confidence': confidence_match.group(1) if confidence_match else 'low',
                'analysis': analysis_match.group(1).strip() if analysis_match else '',
                'key_findings': key_findings,
                'concerns': concerns
            }

            sections['tool_results'].append(tool_result)

        sections['full_content'] = content

        logger.info(f"Parsed notes for {address}: {len(sections['tool_results'])} tool results, "
                   f"{len(sections.get('category_scores', {}))} category scores")

        return sections

    async def upload_to_s3(self, address: str, s3_client=None, bucket: str = None) -> Optional[str]:
        """
        Upload notes file to S3.

        Args:
            address: Property address
            s3_client: Boto3 S3 client (optional, will create if not provided)
            bucket: S3 bucket name (optional, will use config if not provided)

        Returns:
            S3 URL of uploaded file, or None if upload failed
        """
        if self.environment != "production":
            logger.info("Skipping S3 upload in development mode")
            return None

        notes_path = self.get_notes_path(address)

        if not notes_path.exists():
            logger.error(f"Cannot upload - notes file doesn't exist: {notes_path}")
            return None

        try:
            # Import S3 dependencies only when needed
            import boto3
            from app.config import settings

            # Use provided client or create new one
            if s3_client is None:
                s3_client = boto3.client('s3')

            # Use provided bucket or get from settings
            if bucket is None:
                bucket = getattr(settings, 'S3_BUCKET', 'housing-analysis-notes')

            # S3 key format: analysis_notes/2025/01/522_glacier_walk_se.md
            s3_key = f"analysis_notes/{datetime.now().strftime('%Y/%m')}/{notes_path.name}"

            # Upload file
            s3_client.upload_file(str(notes_path), bucket, s3_key)

            s3_url = f"s3://{bucket}/{s3_key}"
            logger.info(f"Uploaded notes to S3: {s3_url}")

            return s3_url

        except Exception as e:
            logger.error(f"Failed to upload notes to S3: {e}")
            return None

    def cleanup_notes(self, address: str, uploaded_to_s3: bool = False):
        """
        Clean up notes file based on environment.

        Development: Keep file
        Production: Delete file (only if uploaded to S3)

        Args:
            address: Property address
            uploaded_to_s3: Whether file was successfully uploaded to S3
        """
        notes_path = self.get_notes_path(address)

        if self.environment == "development":
            logger.info(f"Development mode - keeping notes file: {notes_path}")
            return

        # Production mode - delete if uploaded to S3
        if self.environment == "production":
            if uploaded_to_s3:
                try:
                    notes_path.unlink()
                    logger.info(f"Deleted notes file after S3 upload: {notes_path}")
                except Exception as e:
                    logger.error(f"Failed to delete notes file: {e}")
            else:
                logger.warning(f"Not deleting notes file - S3 upload failed or skipped")

    def list_all_notes(self) -> list[Path]:
        """
        List all notes files in the directory.

        Returns:
            List of Path objects for all .md files
        """
        notes_files = list(self.notes_dir.glob("*.md"))
        logger.info(f"Found {len(notes_files)} notes files in {self.notes_dir}")
        return notes_files

    def get_notes_summary(self) -> Dict[str, Any]:
        """
        Get summary of all notes files.

        Returns:
            Dictionary with stats about notes files
        """
        notes_files = self.list_all_notes()

        summary = {
            "total_files": len(notes_files),
            "notes_directory": str(self.notes_dir),
            "environment": self.environment,
            "files": []
        }

        for notes_file in notes_files:
            stat = notes_file.stat()
            summary["files"].append({
                "filename": notes_file.name,
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "address": notes_file.stem.replace('_', ' ').title()
            })

        return summary

    def append_document_analysis(
        self,
        address: str,
        document_type: str,
        analysis: Dict[str, Any],
        filename: str
    ):
        """
        Append document analysis results (inspection or HOA) to notes.

        Args:
            address: Property address
            document_type: "inspection" or "hoa"
            analysis: Analysis result dictionary from skill
            filename: Original filename of uploaded document
        """
        # Determine section title
        if document_type == "inspection":
            section_title = "Inspection Report Analysis"
        elif document_type == "hoa":
            section_title = "HOA Document Analysis"
        else:
            section_title = f"{document_type.title()} Document Analysis"

        # Build content
        content = f"**Source Document:** {filename}\n\n"
        content += f"**Score:** {analysis.get('score', 'N/A')}/100\n"
        content += f"**Confidence:** {analysis.get('confidence', 'N/A')}\n\n"

        # Reasoning/summary
        if analysis.get('reasoning'):
            content += f"### Summary\n\n{analysis['reasoning']}\n\n"

        # Strengths
        if analysis.get('strengths'):
            content += "### Strengths\n\n"
            for strength in analysis['strengths']:
                content += f"- ✓ {strength}\n"
            content += "\n"

        # Concerns
        if analysis.get('concerns'):
            content += "### Concerns\n\n"
            for concern in analysis['concerns']:
                content += f"- ⚠️ {concern}\n"
            content += "\n"

        # Document-type specific details
        details = analysis.get('details', {})

        if document_type == "inspection" and details.get('issues'):
            content += "### Issues Found\n\n"
            for issue in details['issues']:
                severity = issue.get('severity', 'unknown').upper()
                system = issue.get('system', 'Unknown')
                desc = issue.get('description', '')
                cost = issue.get('estimated_cost', 'N/A')
                urgency = issue.get('urgency', 'N/A')
                content += f"- **[{severity}] {system}**: {desc}\n"
                content += f"  - Cost: {cost}, Urgency: {urgency}\n"
            content += "\n"

            if details.get('total_estimated_repairs'):
                content += f"**Total Estimated Repairs:** {details['total_estimated_repairs']}\n\n"

        elif document_type == "hoa":
            if details.get('monthly_fee') is not None:
                content += f"### Fees\n\n"
                content += f"- **Monthly Fee:** ${details['monthly_fee']}\n"
                if details.get('fee_includes'):
                    content += f"- **Includes:** {', '.join(details['fee_includes'])}\n"
                content += "\n"

            reserve = details.get('reserve_fund', {})
            if reserve:
                content += "### Reserve Fund\n\n"
                if reserve.get('funded_percentage') is not None:
                    content += f"- **Funded:** {reserve['funded_percentage']}%\n"
                if reserve.get('balance') is not None:
                    content += f"- **Balance:** ${reserve['balance']:,}\n"
                if reserve.get('assessment'):
                    content += f"- **Assessment:** {reserve['assessment']}\n"
                content += "\n"

            rental = details.get('rental_restrictions', {})
            if rental:
                content += "### Rental Restrictions\n\n"
                content += f"- **Allowed:** {'Yes' if rental.get('allowed') else 'No'}\n"
                if rental.get('minimum_lease'):
                    content += f"- **Minimum Lease:** {rental['minimum_lease']}\n"
                if rental.get('cap'):
                    content += f"- **Cap:** {rental['cap']}\n"
                content += "\n"

            if details.get('litigation', {}).get('pending'):
                content += "### ⚠️ Litigation\n\n"
                content += "- **Pending litigation reported**\n\n"

        # Append raw JSON for reference
        content += "### Raw Analysis Data\n\n"
        content += "```json\n"
        content += json.dumps(analysis, indent=2, default=str)
        content += "\n```\n"

        # Metadata
        metadata = {
            "Document Type": document_type,
            "Filename": filename,
            "Analyzed": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        self.append_section(address, section_title, content, metadata)
        logger.info(f"Appended {document_type} analysis for {address} from {filename}")


# Global instance
_notes_manager = None


def get_notes_manager(environment: str = "development") -> NotesManager:
    """Get global notes manager instance (singleton)."""
    global _notes_manager
    if _notes_manager is None:
        _notes_manager = NotesManager(environment=environment)
    return _notes_manager
