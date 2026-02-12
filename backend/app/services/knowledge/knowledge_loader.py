"""
Simple keyword-based knowledge file loader for chat.

Matches user questions to relevant knowledge files and loads them as context.
No fancy search - just keyword matching to well-organized markdown files.
"""
import logging
import re
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

# Knowledge files location (mounted in Docker)
KNOWLEDGE_DIR = Path("/app/knowledge")

# Keyword to file mapping
# Each entry: (keywords_set, file_path, topic_name)
KNOWLEDGE_FILES: List[Tuple[set, str, str]] = [
    # Property knowledge
    (
        {"foundation", "foundations", "slab", "crawl space", "crawlspace", "basement",
         "pier", "beam", "footing", "footings", "structural", "load-bearing", "load bearing"},
        "property/01_Foundation_Structure.md",
        "Foundation & Structure"
    ),
    (
        {"roof", "roofing", "shingle", "shingles", "asphalt", "metal roof", "tile roof",
         "slate", "gutters", "flashing", "soffit", "fascia", "attic", "ventilation"},
        "property/02_Roof_Roofing_Systems.md",
        "Roof & Roofing Systems"
    ),
    (
        {"siding", "exterior", "vinyl", "fiber cement", "hardie", "stucco", "brick",
         "wood siding", "cladding", "paint", "trim", "weatherproofing"},
        "property/03_Siding_Exterior.md",
        "Siding & Exterior"
    ),
    (
        {"hvac", "heating", "cooling", "furnace", "air conditioning", "ac", "a/c",
         "heat pump", "ductwork", "ducts", "thermostat", "central air", "boiler",
         "radiant", "forced air", "mini split", "minisplit"},
        "property/04_HVAC_Systems.md",
        "HVAC Systems"
    ),
    (
        {"school", "schools", "district", "education", "elementary", "middle school",
         "high school", "rating", "greatschools", "test scores"},
        "property/05_School_Districts_Location.md",
        "School Districts & Location"
    ),
    # Location/market knowledge
    (
        {"seattle", "wa", "washington", "puget sound", "king county", "bellevue",
         "redmond", "kirkland", "tacoma", "everett"},
        "location/sea+bay/MARKET_Seattle.md",
        "Seattle Market"
    ),
    (
        {"san francisco", "sf", "bay area", "oakland", "berkeley", "san jose",
         "silicon valley", "palo alto", "mountain view", "fremont", "alameda"},
        "location/sea+bay/MARKET_BayArea_SanFrancisco.md",
        "Bay Area / San Francisco Market"
    ),
    (
        {"new york", "nyc", "manhattan", "brooklyn", "queens", "bronx", "staten island",
         "long island", "westchester", "jersey city"},
        "location/la+austin+ny/MARKET_NewYork_NYC.md",
        "New York City Market"
    ),
    (
        {"austin", "texas", "tx", "round rock", "cedar park", "pflugerville",
         "georgetown", "san marcos"},
        "location/la+austin+ny/MARKET_Austin.md",
        "Austin Market"
    ),
    (
        {"los angeles", "la", "southern california", "socal", "orange county",
         "pasadena", "glendale", "long beach", "santa monica", "venice", "hollywood"},
        "location/la+austin+ny/MARKET_LosAngeles.md",
        "Los Angeles Market"
    ),
]


def find_relevant_knowledge(user_message: str) -> List[Tuple[str, str]]:
    """
    Find knowledge files relevant to the user's message.

    Args:
        user_message: The user's question/message

    Returns:
        List of (topic_name, file_content) tuples for matching files
    """
    message_lower = user_message.lower()
    results = []

    for keywords, file_path, topic_name in KNOWLEDGE_FILES:
        # Check if any keyword appears in the message (word boundary match)
        for keyword in keywords:
            # Use word boundary regex to avoid partial matches (e.g., "la" in "slab")
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, message_lower):
                # Load the file
                full_path = KNOWLEDGE_DIR / file_path
                if full_path.exists():
                    try:
                        content = full_path.read_text()
                        results.append((topic_name, content))
                        logger.info(f"Loaded knowledge file: {file_path} ({len(content)} chars)")
                    except Exception as e:
                        logger.error(f"Failed to read {file_path}: {e}")
                else:
                    logger.warning(f"Knowledge file not found: {full_path}")
                break  # Only load each file once

    return results


def get_knowledge_context(user_message: str, max_chars: int = 15000) -> Optional[str]:
    """
    Get formatted knowledge context for a user message.

    Args:
        user_message: The user's question
        max_chars: Maximum total characters to return

    Returns:
        Formatted knowledge context string, or None if no relevant knowledge
    """
    matches = find_relevant_knowledge(user_message)

    if not matches:
        return None

    sections = []
    total_chars = 0

    for topic_name, content in matches:
        # Check if we have room for this file
        if total_chars + len(content) > max_chars:
            # Truncate if needed
            remaining = max_chars - total_chars
            if remaining > 1000:  # Only include if we can fit a meaningful chunk
                content = content[:remaining] + "\n\n[... truncated ...]"
            else:
                continue

        sections.append(f"## {topic_name}\n\n{content}")
        total_chars += len(content)

    if not sections:
        return None

    header = "# Expert Knowledge Base\n\nUse this reference information to provide accurate, detailed answers:\n\n"
    return header + "\n\n---\n\n".join(sections)
