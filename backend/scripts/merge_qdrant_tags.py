#!/usr/bin/env python3
"""
Merge enriched Qdrant tags back into markdown knowledge files.

Reads the export from extract_qdrant_tags.py and injects @applies_when
and @priority tags into the corresponding markdown source files.

Usage:
    python backend/scripts/merge_qdrant_tags.py
    python backend/scripts/merge_qdrant_tags.py --dry-run   # preview only
    python backend/scripts/merge_qdrant_tags.py --export path/to/qdrant_export.json

Output: Modified markdown files in backend/knowledge/
"""

import argparse
import json
import os
import re
import sys
from difflib import SequenceMatcher

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_EXPORT = os.path.join(SCRIPT_DIR, "qdrant_export.json")
KNOWLEDGE_DIR = os.path.join(SCRIPT_DIR, "..", "knowledge")

# Same pattern used in skill_knowledge_service.py
CONDITION_PATTERN = re.compile(
    r'^(\w+)\s*(<=|>=|<|>|=|contains)\s*(.+)$',
    re.IGNORECASE,
)


def find_md_file(source_file: str) -> str | None:
    """Find the full path to a markdown file by its filename."""
    for root, _dirs, files in os.walk(KNOWLEDGE_DIR):
        for f in files:
            if f == source_file:
                return os.path.join(root, f)
    return None


def similarity(a: str, b: str) -> float:
    """Compute text similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def normalize_text(text: str) -> str:
    """Normalize text for comparison — collapse whitespace, lowercase."""
    return re.sub(r'\s+', ' ', text.lower().strip())


def format_applies_when(cond: dict) -> str:
    """Format a single applies_when condition as a tag line."""
    attr = cond.get("attribute", "")
    op = cond.get("operator", "")
    val = cond.get("value", "")
    # Convert Python booleans/numbers back to string
    if isinstance(val, bool):
        val = str(val).lower()
    else:
        val = str(val)
    return f"@applies_when: {attr}{op}{val}"


def parse_existing_tags(lines: list[str], start_idx: int) -> tuple[list[dict], str, int]:
    """
    Parse existing @applies_when and @priority tags starting at start_idx.
    Returns (applies_when_list, priority, next_content_line_idx).
    """
    applies_when = []
    priority = "medium"
    j = start_idx
    while j < len(lines):
        stripped = lines[j].strip()
        if stripped.startswith("@applies_when:"):
            cond_str = stripped.replace("@applies_when:", "").strip()
            match = CONDITION_PATTERN.match(cond_str)
            if match:
                applies_when.append({
                    "attribute": match.group(1).lower(),
                    "operator": match.group(2).lower(),
                    "value": match.group(3).strip(),
                })
            j += 1
        elif stripped.startswith("@priority:"):
            p = stripped.replace("@priority:", "").strip().lower()
            if p in ("high", "medium", "low"):
                priority = p
            j += 1
        elif not stripped:
            j += 1
        else:
            break
    return applies_when, priority, j


def condition_key(cond: dict) -> str:
    """Unique key for a condition to detect duplicates."""
    return f"{cond.get('attribute', '').lower()}|{cond.get('operator', '').lower()}|{str(cond.get('value', '')).lower()}"


def match_points_to_sections(lines: list[str], qdrant_entries: list[dict]) -> list[dict]:
    """
    Match Qdrant export entries to sections in the markdown file.
    Returns a list of injection instructions.
    """
    injections = []

    # Build a map of sections: heading line index -> section info
    sections = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match ## heading or ### heading
        heading_match = (
            re.match(r'^#{2,3}\s+(?:\d+\.\s+)?(.+)$', stripped) or
            re.match(r'^\d+\.\s+(.+)$', stripped)
        )
        if heading_match:
            category = heading_match.group(1).strip()
            # Collect text content after heading (skip tags and blanks)
            existing_aw, existing_priority, content_start = parse_existing_tags(
                lines, i + 1
            )
            # Gather content text for matching
            content_lines = []
            for k in range(content_start, min(content_start + 10, len(lines))):
                s = lines[k].strip()
                if s == "---" or s.startswith("##"):
                    break
                if s and not s.startswith("@"):
                    content_lines.append(s)
            content_text = " ".join(content_lines)

            sections.append({
                "line_idx": i,
                "category": category,
                "existing_applies_when": existing_aw,
                "existing_priority": existing_priority,
                "tag_insert_line": i + 1,  # line after heading where tags go
                "content_text": content_text,
            })

    # Match each Qdrant entry to a section
    used_sections = set()
    for entry in qdrant_entries:
        qdrant_text = entry.get("full_text", entry.get("text", ""))
        qdrant_category = entry.get("category", "")
        qdrant_aw = entry.get("applies_when", [])
        qdrant_priority = entry.get("priority", "medium")

        if not qdrant_aw and qdrant_priority == "medium":
            continue  # nothing to inject

        best_match = None
        best_score = 0.0

        for idx, sec in enumerate(sections):
            if idx in used_sections:
                continue

            # Score by category match + content similarity
            cat_score = similarity(qdrant_category, sec["category"])

            # Compare full text to section content
            text_score = similarity(
                normalize_text(qdrant_text)[:200],
                normalize_text(sec["content_text"])[:200],
            )

            # Also try matching the first 80 chars
            short_score = similarity(
                normalize_text(qdrant_text)[:80],
                normalize_text(sec["content_text"])[:80],
            )

            combined = cat_score * 0.4 + max(text_score, short_score) * 0.6

            if combined > best_score:
                best_score = combined
                best_match = idx

        if best_match is not None and best_score >= 0.4:
            sec = sections[best_match]
            used_sections.add(best_match)

            # Determine new tags to add
            existing_keys = {condition_key(c) for c in sec["existing_applies_when"]}
            new_conditions = [
                c for c in qdrant_aw
                if condition_key(c) not in existing_keys
            ]

            # Only upgrade priority if existing is default and Qdrant has explicit
            new_priority = None
            if (
                qdrant_priority != "medium"
                and sec["existing_priority"] == "medium"
                and not sec["existing_applies_when"]
            ):
                new_priority = qdrant_priority

            if new_conditions or new_priority:
                injections.append({
                    "section_line": sec["line_idx"],
                    "category": sec["category"],
                    "insert_at": sec["tag_insert_line"],
                    "has_existing_tags": bool(sec["existing_applies_when"]),
                    "new_conditions": new_conditions,
                    "new_priority": new_priority,
                    "match_score": round(best_score, 3),
                    "qdrant_text_preview": qdrant_text[:80],
                })

    return injections


def apply_injections(lines: list[str], injections: list[dict]) -> list[str]:
    """
    Apply tag injections to the markdown lines.
    Process in reverse line order so insertions don't shift subsequent indices.
    """
    sorted_inj = sorted(injections, key=lambda x: x["insert_at"], reverse=True)
    result = list(lines)

    for inj in sorted_inj:
        insert_at = inj["insert_at"]
        tag_lines = []

        for cond in inj["new_conditions"]:
            tag_lines.append(format_applies_when(cond))

        if inj["new_priority"]:
            tag_lines.append(f"@priority: {inj['new_priority']}")

        if not tag_lines:
            continue

        # If section already has tags, find the last tag line and append after it
        if inj["has_existing_tags"]:
            j = insert_at
            while j < len(result):
                stripped = result[j].strip()
                if stripped.startswith("@"):
                    j += 1
                elif not stripped:
                    j += 1
                else:
                    break
            # Insert before the content, after existing tags
            for k, tag in enumerate(tag_lines):
                result.insert(j + k, tag + "\n")
        else:
            # No existing tags — insert right after the heading line
            new_block = [t + "\n" for t in tag_lines]
            for k, tag_line in enumerate(new_block):
                result.insert(insert_at + k, tag_line)

    return result


def main():
    parser = argparse.ArgumentParser(description="Merge Qdrant tags into markdown files")
    parser.add_argument(
        "--export", default=DEFAULT_EXPORT,
        help=f"Path to qdrant_export.json (default: {DEFAULT_EXPORT})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing files"
    )
    args = parser.parse_args()

    if not os.path.exists(args.export):
        print(f"Export file not found: {args.export}")
        print("Run extract_qdrant_tags.py first.")
        sys.exit(1)

    with open(args.export) as f:
        export = json.load(f)

    print(f"Export from: {export.get('exported_at', '?')}")
    print(f"Total points: {export.get('total_points', '?')}")
    print(f"Points with tags: {export.get('points_with_tags', '?')}")
    print(f"Source files: {export.get('source_files_count', '?')}")
    print()

    by_source = export.get("by_source_file", {})
    total_tags_added = 0
    total_files_modified = 0
    total_matched = 0
    total_unmatched = 0

    for source_file, entries in sorted(by_source.items()):
        md_path = find_md_file(source_file)
        if not md_path:
            print(f"SKIP {source_file}: file not found in {KNOWLEDGE_DIR}")
            total_unmatched += len(entries)
            continue

        with open(md_path) as f:
            lines = f.readlines()

        injections = match_points_to_sections(lines, entries)
        matched = len(injections)
        unmatched = len(entries) - matched
        total_matched += matched
        total_unmatched += unmatched

        if not injections:
            print(f"  {source_file}: {len(entries)} entries, 0 new tags to add")
            continue

        tags_count = sum(
            len(inj["new_conditions"]) + (1 if inj["new_priority"] else 0)
            for inj in injections
        )
        total_tags_added += tags_count
        total_files_modified += 1

        print(f"  {source_file}: {matched} sections matched, {tags_count} new tags")
        for inj in injections:
            conds_str = ", ".join(format_applies_when(c) for c in inj["new_conditions"])
            prio_str = f", priority={inj['new_priority']}" if inj["new_priority"] else ""
            print(f"    L{inj['section_line']+1} [{inj['category']}] "
                  f"(score={inj['match_score']}): {conds_str}{prio_str}")

        if not args.dry_run:
            updated_lines = apply_injections(lines, injections)
            with open(md_path, "w") as f:
                f.writelines(updated_lines)
            print(f"    -> Written to {md_path}")

    print(f"\n{'DRY RUN ' if args.dry_run else ''}Summary:")
    print(f"  Files modified: {total_files_modified}")
    print(f"  Sections matched: {total_matched}")
    print(f"  Entries unmatched: {total_unmatched}")
    print(f"  Tags added: {total_tags_added}")

    if args.dry_run:
        print("\nRe-run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
