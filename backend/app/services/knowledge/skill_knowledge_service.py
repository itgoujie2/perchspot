"""
Skill Knowledge Service — Lightweight file-based knowledge retrieval

Replaces the embedding model + Qdrant pipeline with direct file loading.
Each skill declares which knowledge files it needs; files are cached in memory (~170KB total).

Also provides attribute matching via @applies_when tags parsed directly from files.
"""
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Knowledge files location (mounted in Docker at /app/knowledge)
KNOWLEDGE_DIR = Path("/app/knowledge")
if not KNOWLEDGE_DIR.exists():
    KNOWLEDGE_DIR = Path("./knowledge")
if not KNOWLEDGE_DIR.exists():
    KNOWLEDGE_DIR = Path("./backend/knowledge")

# File key → relative path within KNOWLEDGE_DIR
KNOWLEDGE_FILE_MAP = {
    "foundation": "property/01_Foundation_Structure.md",
    "roof": "property/02_Roof_Roofing_Systems.md",
    "siding": "property/03_Siding_Exterior.md",
    "hvac": "property/04_HVAC_Systems.md",
    "schools": "property/05_School_Districts_Location.md",
    "hoa": "property/06_HOA_Considerations.md",
    "home_age": "property/07_Home_Age_Considerations.md",
    "property_types": "property/08_Property_Types.md",
    "hot_zip_codes": "location/HOT_ZIP_CODES_2025_2026.md",
    "market_seattle": "location/sea+bay/MARKET_Seattle.md",
    "market_bayarea": "location/sea+bay/MARKET_BayArea_SanFrancisco.md",
    "market_newyork": "location/la+austin+ny/MARKET_NewYork_NYC.md",
    "market_austin": "location/la+austin+ny/MARKET_Austin.md",
    "market_la": "location/la+austin+ny/MARKET_LosAngeles.md",
}

# Region name → market file key
REGION_MARKET_MAP = {
    # Washington
    "Eastside": "market_seattle",
    "Seattle Core": "market_seattle",
    "North Sound": "market_seattle",
    "South King County": "market_seattle",
    "Tacoma": "market_seattle",
    # California - Bay Area
    "San Francisco": "market_bayarea",
    "Peninsula & South Bay": "market_bayarea",
    "East Bay": "market_bayarea",
    # California - LA
    "LA Westside": "market_la",
    "LA Metro": "market_la",
    # New York
    "Manhattan": "market_newyork",
    "Brooklyn": "market_newyork",
    # Texas
    "Austin Core": "market_austin",
    # Oregon (served by Seattle for now — closest metro)
    "Portland Core": "market_seattle",
    "Portland Suburbs": "market_seattle",
}

# City keyword → market file key (fallback when region is unknown)
CITY_MARKET_MAP = {
    # WA
    "seattle": "market_seattle", "bellevue": "market_seattle",
    "redmond": "market_seattle", "kirkland": "market_seattle",
    "sammamish": "market_seattle", "issaquah": "market_seattle",
    "bothell": "market_seattle", "woodinville": "market_seattle",
    "renton": "market_seattle", "kent": "market_seattle",
    "tacoma": "market_seattle", "everett": "market_seattle",
    "lynnwood": "market_seattle", "shoreline": "market_seattle",
    "mercer island": "market_seattle", "kenmore": "market_seattle",
    "burien": "market_seattle", "federal way": "market_seattle",
    "covington": "market_seattle", "maple valley": "market_seattle",
    # CA - Bay Area
    "san francisco": "market_bayarea", "oakland": "market_bayarea",
    "berkeley": "market_bayarea", "san jose": "market_bayarea",
    "palo alto": "market_bayarea", "mountain view": "market_bayarea",
    "sunnyvale": "market_bayarea", "cupertino": "market_bayarea",
    "santa clara": "market_bayarea", "fremont": "market_bayarea",
    "hayward": "market_bayarea", "walnut creek": "market_bayarea",
    "concord": "market_bayarea", "pleasanton": "market_bayarea",
    "livermore": "market_bayarea", "san ramon": "market_bayarea",
    "dublin": "market_bayarea", "menlo park": "market_bayarea",
    "redwood city": "market_bayarea", "san mateo": "market_bayarea",
    "milpitas": "market_bayarea",
    # CA - LA
    "los angeles": "market_la", "pasadena": "market_la",
    "glendale": "market_la", "long beach": "market_la",
    "santa monica": "market_la", "burbank": "market_la",
    "torrance": "market_la", "irvine": "market_la",
    "anaheim": "market_la", "costa mesa": "market_la",
    "huntington beach": "market_la",
    # NY
    "new york": "market_newyork", "manhattan": "market_newyork",
    "brooklyn": "market_newyork", "queens": "market_newyork",
    "bronx": "market_newyork", "jersey city": "market_newyork",
    "hoboken": "market_newyork",
    # TX
    "austin": "market_austin", "round rock": "market_austin",
    "cedar park": "market_austin", "pflugerville": "market_austin",
    "georgetown": "market_austin", "san marcos": "market_austin",
    "kyle": "market_austin", "leander": "market_austin",
    "lakeway": "market_austin",
    # OR (fallback to Seattle)
    "portland": "market_seattle", "beaverton": "market_seattle",
    "hillsboro": "market_seattle", "lake oswego": "market_seattle",
    "tigard": "market_seattle", "gresham": "market_seattle",
}


# ---------------------------------------------------------------------------
# Parsed knowledge point
# ---------------------------------------------------------------------------

@dataclass
class KnowledgePoint:
    """A single knowledge point parsed from a markdown file."""
    text: str
    category: str
    source_file: str
    priority: str = "medium"
    applies_when: List[Dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# In-memory file cache
# ---------------------------------------------------------------------------

_file_cache: Dict[str, str] = {}
_parsed_cache: Dict[str, List[KnowledgePoint]] = {}

# Regex for parsing @applies_when conditions
CONDITION_PATTERN = re.compile(
    r'^(\w+)\s*(<=|>=|<|>|=|contains)\s*(.+)$',
    re.IGNORECASE,
)


def preload_all_files() -> int:
    """
    Pre-load all knowledge files into memory at startup.
    Returns the number of files loaded.
    """
    loaded = 0
    for key, rel_path in KNOWLEDGE_FILE_MAP.items():
        content = _load_file(key)
        if content:
            loaded += 1
    total_bytes = sum(len(c) for c in _file_cache.values())
    logger.info(f"Pre-loaded {loaded}/{len(KNOWLEDGE_FILE_MAP)} knowledge files ({total_bytes:,} bytes)")
    return loaded


def _load_file(key: str) -> Optional[str]:
    """Load a knowledge file by key, with caching."""
    if key in _file_cache:
        return _file_cache[key]

    rel_path = KNOWLEDGE_FILE_MAP.get(key)
    if not rel_path:
        logger.warning(f"Unknown knowledge file key: {key}")
        return None

    full_path = KNOWLEDGE_DIR / rel_path
    if not full_path.exists():
        logger.warning(f"Knowledge file not found: {full_path}")
        return None

    try:
        content = full_path.read_text(encoding="utf-8")
        _file_cache[key] = content
        return content
    except Exception as e:
        logger.error(f"Failed to read knowledge file {full_path}: {e}")
        return None


def load_files(file_keys: List[str]) -> str:
    """
    Load multiple knowledge files by key and concatenate them.

    Returns a formatted context string with section headers.
    """
    sections = []
    for key in file_keys:
        content = _load_file(key)
        if content:
            sections.append(content)

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Market file resolution
# ---------------------------------------------------------------------------

def get_market_file_key(
    region: Optional[str] = None,
    address: Optional[str] = None,
) -> Optional[str]:
    """
    Resolve which market file to load based on region or address.
    Region takes priority; falls back to city keyword matching from address.
    """
    if region and region in REGION_MARKET_MAP:
        return REGION_MARKET_MAP[region]

    if address:
        addr_lower = address.lower()
        for city, key in CITY_MARKET_MAP.items():
            if city in addr_lower:
                return key

    return None


# ---------------------------------------------------------------------------
# Attribute matching — parse @applies_when from files
# ---------------------------------------------------------------------------

def _parse_condition_value(raw: str) -> Any:
    """Parse a condition value string into typed Python value."""
    raw = raw.strip()
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw) if "." not in raw else float(raw)
    except ValueError:
        return raw.lower()


def _parse_markdown_to_points(content: str, source_file: str) -> List[KnowledgePoint]:
    """
    Parse markdown content into knowledge points.
    Mirrors the logic from ingestion_service._parse_markdown().
    """
    points: List[KnowledgePoint] = []
    current_category = ""
    current_applies_when: List[Dict[str, Any]] = []
    current_priority = "medium"
    current_paragraph_lines: List[str] = []

    def flush_paragraph():
        if current_paragraph_lines and current_category:
            text = " ".join(current_paragraph_lines).strip()
            if text:
                points.append(KnowledgePoint(
                    text=text,
                    category=current_category,
                    source_file=source_file,
                    priority=current_priority,
                    applies_when=list(current_applies_when),
                ))
        current_paragraph_lines.clear()

    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Category heading
        heading_match = (
            re.match(r'^##\s+(?:\d+\.\s+)?(.+)$', stripped) or
            re.match(r'^\d+\.\s+(.+)$', stripped)
        )
        if heading_match:
            flush_paragraph()
            current_category = heading_match.group(1).strip()

            # Look ahead for @tags
            tag_lines = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith('@'):
                    tag_lines.append(next_line)
                    j += 1
                elif not next_line:
                    j += 1
                else:
                    break

            if tag_lines:
                current_applies_when, current_priority = _extract_tags(tag_lines)
                i = j - 1
            else:
                current_applies_when = []
                current_priority = "medium"

            i += 1
            continue

        # Skip top-level heading
        if stripped.startswith("# ") and not stripped.startswith("## "):
            i += 1
            continue

        # Separator ---
        if stripped == "---":
            flush_paragraph()
            tag_lines = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line.startswith('@'):
                    tag_lines.append(next_line)
                    j += 1
                elif not next_line:
                    j += 1
                else:
                    break

            if tag_lines:
                current_applies_when, current_priority = _extract_tags(tag_lines)
                i = j - 1
            else:
                current_applies_when = []
                current_priority = "medium"

            i += 1
            continue

        # Skip stray @ tag lines
        if stripped.startswith('@'):
            i += 1
            continue

        # Empty line = paragraph boundary
        if not stripped:
            flush_paragraph()
            i += 1
            continue

        # Bullet point
        bullet_match = re.match(r'^[-*]\s+(.+)$', stripped)
        if bullet_match and current_category:
            flush_paragraph()
            bullet_text = bullet_match.group(1).strip()
            if bullet_text:
                points.append(KnowledgePoint(
                    text=bullet_text,
                    category=current_category,
                    source_file=source_file,
                    priority=current_priority,
                    applies_when=list(current_applies_when),
                ))
            i += 1
            continue

        # Regular paragraph text
        if current_category:
            current_paragraph_lines.append(stripped)

        i += 1

    flush_paragraph()
    return points


def _extract_tags(tag_lines: List[str]) -> tuple[List[Dict[str, Any]], str]:
    """Extract @applies_when conditions and @priority from tag lines."""
    applies_when: List[Dict[str, Any]] = []
    priority = "medium"

    for line in tag_lines:
        stripped = line.strip()
        if stripped.startswith("@applies_when:"):
            condition_str = stripped.replace("@applies_when:", "").strip()
            match = CONDITION_PATTERN.match(condition_str)
            if match:
                applies_when.append({
                    "attribute": match.group(1).lower(),
                    "operator": match.group(2).lower(),
                    "value": _parse_condition_value(match.group(3)),
                })
        elif stripped.startswith("@priority:"):
            p = stripped.replace("@priority:", "").strip().lower()
            if p in ("high", "medium", "low"):
                priority = p

    return applies_when, priority


def _get_parsed_points(file_key: str) -> List[KnowledgePoint]:
    """Get parsed knowledge points for a file, with caching."""
    if file_key in _parsed_cache:
        return _parsed_cache[file_key]

    content = _load_file(file_key)
    if not content:
        return []

    rel_path = KNOWLEDGE_FILE_MAP.get(file_key, file_key)
    points = _parse_markdown_to_points(content, os.path.basename(rel_path))
    _parsed_cache[file_key] = points
    return points


# Attribute evaluation paths
ATTRIBUTE_PATHS = {
    "year_built": ("details", "year_built"),
    "has_hoa": ("hoa", "has_hoa"),
    "hoa_fee": ("hoa", "fee"),
    "property_type": ("details", "property_type"),
    "lot_size_sqft": ("details", "lot_size_sqft"),
    "living_area_sqft": ("details", "living_area_sqft"),
    "bedrooms": ("details", "bedrooms"),
    "bathrooms": ("details", "bathrooms"),
    "stories": ("details", "stories"),
    "has_pool": ("details", "has_pool"),
    "has_garage": ("details", "has_garage"),
}


def _get_property_value(attribute: str, property_data: Dict[str, Any]) -> Any:
    """Navigate property data to get a value by attribute name."""
    path = ATTRIBUTE_PATHS.get(attribute)
    if not path:
        return None
    current = property_data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _evaluate_condition(condition: Dict[str, Any], property_data: Dict[str, Any]) -> bool:
    """Evaluate a single @applies_when condition against property data."""
    if not isinstance(condition, dict):
        return False

    attribute = condition.get("attribute", "")
    operator = condition.get("operator", "=")
    target_value = condition.get("value")

    actual_value = _get_property_value(attribute, property_data)
    if actual_value is None:
        return False

    try:
        if operator == "=":
            if isinstance(target_value, bool):
                return bool(actual_value) == target_value
            elif isinstance(target_value, str):
                return str(actual_value).lower() == target_value.lower()
            else:
                return actual_value == target_value
        elif operator == "<":
            return float(actual_value) < float(target_value)
        elif operator == ">":
            return float(actual_value) > float(target_value)
        elif operator == "<=":
            return float(actual_value) <= float(target_value)
        elif operator == ">=":
            return float(actual_value) >= float(target_value)
        elif operator == "contains":
            return str(target_value).lower() in str(actual_value).lower()
        else:
            return False
    except (ValueError, TypeError):
        return False


def get_attribute_knowledge(
    property_data: Dict[str, Any],
    file_keys: Optional[List[str]] = None,
    limit: int = 20,
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Find knowledge points matching property attributes via @applies_when tags.

    Args:
        property_data: Property data dict with 'details', 'hoa', etc.
        file_keys: Specific file keys to search (default: all property files)
        limit: Maximum results to return

    Returns:
        (formatted_context_str, debug_list)
    """
    if file_keys is None:
        file_keys = [
            "foundation", "roof", "siding", "hvac", "hoa",
            "home_age", "property_types",
        ]

    matched: List[KnowledgePoint] = []

    for key in file_keys:
        points = _get_parsed_points(key)
        for point in points:
            if not point.applies_when:
                continue
            # All conditions must match
            if all(_evaluate_condition(c, property_data) for c in point.applies_when):
                matched.append(point)

    # Sort by priority: high > medium > low
    priority_order = {"high": 0, "medium": 1, "low": 2}
    matched.sort(key=lambda p: priority_order.get(p.priority, 1))
    matched = matched[:limit]

    if not matched:
        return "", []

    # Build debug info
    debug_list = [
        {
            "text": p.text,
            "category": p.category,
            "priority": p.priority,
            "source_file": p.source_file,
        }
        for p in matched
    ]

    # Group by category for formatted context
    by_category: Dict[str, List[str]] = defaultdict(list)
    for p in matched:
        by_category[p.category].append(p.text)

    sections = []
    for category, texts in by_category.items():
        lines = [f"### {category}"]
        for text in texts:
            lines.append(f"- {text}")
        sections.append("\n".join(lines))

    combined = "\n\n".join(sections)
    logger.info(f"Attribute knowledge: found {len(matched)} matching points")
    return combined, debug_list


def get_attribute_knowledge_with_details(
    property_data: Dict[str, Any],
    file_keys: Optional[List[str]] = None,
    limit: int = 15,
) -> List[Dict[str, Any]]:
    """
    Find knowledge points matching property attributes, including match details.

    Used for Property Insights section.
    """
    if file_keys is None:
        file_keys = [
            "foundation", "roof", "siding", "hvac", "hoa",
            "home_age", "property_types",
        ]

    results: List[Dict[str, Any]] = []

    for key in file_keys:
        points = _get_parsed_points(key)
        for point in points:
            if not point.applies_when:
                continue

            all_match = True
            matched_conditions = []

            for condition in point.applies_when:
                if not _evaluate_condition(condition, property_data):
                    all_match = False
                    break
                actual_value = _get_property_value(
                    condition.get("attribute", ""), property_data
                )
                matched_conditions.append({
                    "attribute": condition.get("attribute"),
                    "operator": condition.get("operator"),
                    "value": condition.get("value"),
                    "actual_value": actual_value,
                })

            if all_match and matched_conditions:
                results.append({
                    "text": point.text,
                    "category": point.category,
                    "priority": point.priority,
                    "matched_conditions": matched_conditions,
                })

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda p: priority_order.get(p.get("priority", "medium"), 1))

    logger.info(f"Attribute knowledge with details: {len(results)} points (returning top {limit})")
    return results[:limit]
