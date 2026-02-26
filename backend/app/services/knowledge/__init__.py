"""
Knowledge Store — File-based knowledge retrieval

Loads markdown knowledge files directly from disk, cached in memory.
Provides attribute matching via @applies_when tags parsed from files.
"""
from app.services.knowledge.skill_knowledge_service import (
    load_files,
    preload_all_files,
    get_attribute_knowledge,
    get_attribute_knowledge_with_details,
    get_market_file_key,
)

__all__ = [
    "load_files",
    "preload_all_files",
    "get_attribute_knowledge",
    "get_attribute_knowledge_with_details",
    "get_market_file_key",
]
