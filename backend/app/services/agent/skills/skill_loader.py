"""
Skill Loader - Loads Claude Skills from .claude/skills/ directory

This loader reads SKILL.md files which contain:
- YAML frontmatter with metadata
- Instructions for Claude
- References to supporting .md files

The .md files are the source of truth for skill behavior.
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class SkillLoader:
    """
    Loads Claude Skills from filesystem.

    Skills follow this structure:
    .claude/skills/skill-name/
        ├── SKILL.md          # Main skill file (metadata + instructions)
        ├── reference.md      # Supporting documentation
        └── scripts/          # Executable utilities
    """

    def __init__(self, skills_dir: str = None):
        self.skills_dir = Path(skills_dir or "/app/.claude/skills")
        self.cache: Dict[str, Dict] = {}

    def load_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        Load a skill by name.

        Args:
            skill_name: Name of the skill (e.g., "property-analysis")

        Returns:
            Dict with:
            {
                'name': str,
                'description': str,
                'metadata': Dict (from YAML frontmatter),
                'content': str (skill instructions),
                'full_context': str (skill + supporting files)
            }
        """
        if skill_name in self.cache:
            return self.cache[skill_name]

        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            raise FileNotFoundError(f"Skill not found: {skill_name} at {skill_path}")

        # Read SKILL.md
        with open(skill_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse YAML frontmatter
        metadata, instructions = self._parse_frontmatter(content)

        # Load supporting .md files referenced in the skill
        supporting_files = self._find_referenced_files(instructions, self.skills_dir / skill_name)

        # Build full context (skill + supporting files)
        full_context = self._build_full_context(skill_name, instructions, supporting_files)

        skill_data = {
            'name': metadata.get('name', skill_name),
            'description': metadata.get('description', ''),
            'metadata': metadata,
            'content': instructions,
            'full_context': full_context
        }

        self.cache[skill_name] = skill_data
        logger.info(f"Loaded skill: {skill_name} ({len(full_context)} chars)")

        return skill_data

    def _parse_frontmatter(self, content: str) -> tuple[Dict, str]:
        """Parse YAML frontmatter from markdown file."""
        # Match YAML frontmatter pattern: --- ... ---
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            # No frontmatter found
            return {}, content

        yaml_content = match.group(1)
        markdown_content = match.group(2)

        try:
            metadata = yaml.safe_load(yaml_content)
            return metadata or {}, markdown_content
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML frontmatter: {e}")
            return {}, content

    def _find_referenced_files(self, content: str, skill_dir: Path) -> Dict[str, str]:
        """Find and load .md files referenced in the skill content."""
        supporting_files = {}

        # Find markdown link references: [text](file.md)
        pattern = r'\[([^\]]+)\]\(([^)]+\.md)\)'
        matches = re.findall(pattern, content)

        for link_text, filename in matches:
            file_path = skill_dir / filename

            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                        supporting_files[filename] = file_content
                        logger.debug(f"Loaded supporting file: {filename}")
                except Exception as e:
                    logger.warning(f"Could not load {filename}: {e}")
            else:
                logger.warning(f"Referenced file not found: {filename}")

        return supporting_files

    def _build_full_context(self, skill_name: str, instructions: str, supporting_files: Dict[str, str]) -> str:
        """Build full context by combining skill instructions and supporting files."""
        parts = [
            f"# {skill_name.replace('-', ' ').title()} Skill",
            "",
            instructions
        ]

        # Add supporting files
        if supporting_files:
            parts.append("")
            parts.append("---")
            parts.append("")
            parts.append("# Supporting Documentation")
            parts.append("")

            for filename, content in supporting_files.items():
                parts.append(f"## From {filename}")
                parts.append("")
                parts.append(content)
                parts.append("")

        return "\n".join(parts)

    def list_skills(self) -> list[str]:
        """List all available skills."""
        if not self.skills_dir.exists():
            return []

        skills = []
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                skills.append(skill_dir.name)

        return sorted(skills)

    def clear_cache(self):
        """Clear the skill cache."""
        self.cache.clear()
        logger.info("Skill cache cleared")


# Global instance
skill_loader = SkillLoader()
