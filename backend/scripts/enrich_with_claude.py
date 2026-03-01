#!/usr/bin/env python3
from __future__ import annotations

"""
Analyze Qdrant knowledge points with Claude and enrich with @applies_when tags.

Reads the full Qdrant export (qdrant_export_all.json), sends points to Claude
in batches for analysis, and produces an enriched output ready for injection
into the knowledge markdown files.

Usage (on EC2):
    cd /opt/perchspot
    # Step 1: Extract all points
    python3 backend/scripts/extract_qdrant_tags.py --all

    # Step 2: Enrich with Claude
    python3 backend/scripts/enrich_with_claude.py

    # Step 3: Review then apply
    python3 backend/scripts/enrich_with_claude.py --apply --dry-run
    python3 backend/scripts/enrich_with_claude.py --apply

Requires ANTHROPIC_API_KEY environment variable.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(SCRIPT_DIR, "..", "knowledge")
DEFAULT_EXPORT = os.path.join(SCRIPT_DIR, "qdrant_export_all.json")
ENRICHED_OUTPUT = os.path.join(SCRIPT_DIR, "enriched_points.json")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 40  # points per Claude call
API_URL = "https://api.anthropic.com/v1/messages"

# Supported attributes from skill_knowledge_service.py
SUPPORTED_ATTRIBUTES = [
    "year_built", "has_hoa", "hoa_fee", "property_type",
    "lot_size_sqft", "living_area_sqft", "bedrooms", "bathrooms",
    "stories", "has_pool", "has_garage",
]

CONDITION_PATTERN = re.compile(
    r'^(\w+)\s*(<=|>=|<|>|=|contains)\s*(.+)$',
    re.IGNORECASE,
)


def load_knowledge_sections() -> dict[str, list[str]]:
    """Load all knowledge files and extract their section headings."""
    sections = {}
    for root, _dirs, files in os.walk(KNOWLEDGE_DIR):
        for fname in sorted(files):
            if not fname.endswith(".md"):
                continue
            path = os.path.join(root, fname)
            with open(path) as f:
                content = f.read()
            headings = []
            for line in content.split("\n"):
                stripped = line.strip()
                m = re.match(r'^#{2,3}\s+(.+)$', stripped)
                if m:
                    headings.append(m.group(1).strip())
            if headings:
                sections[fname] = headings
    return sections


def build_system_prompt(knowledge_sections: dict[str, list[str]]) -> str:
    """Build the system prompt with available knowledge files."""
    file_list = ""
    for fname, headings in sorted(knowledge_sections.items()):
        file_list += f"\n{fname}:\n"
        for h in headings[:15]:  # limit to keep prompt short
            file_list += f"  - {h}\n"

    return f"""You analyze home-buying knowledge points and decide which are useful for a property analysis tool.

For each point, you must decide:
1. Is it USEFUL? Skip generic advice anyone would know (e.g., "get a home inspection"). Keep specific, actionable knowledge with concrete details (costs, timelines, conditions, thresholds).
2. Which knowledge file should it go in? Pick the best-fit file from the list below.
3. What @applies_when conditions apply? These filter when the point is shown to a buyer based on property attributes. Only add conditions when the text clearly references specific property characteristics.

Available attributes for @applies_when:
- year_built: integer (e.g., year_built<1970, year_built>=2000)
- has_hoa: boolean (has_hoa=true, has_hoa=false)
- hoa_fee: number (hoa_fee>500)
- property_type: string (property_type=condo, property_type=townhouse, property_type contains single)
- lot_size_sqft: number (lot_size_sqft>10000)
- living_area_sqft: number (living_area_sqft<1000)
- bedrooms: number (bedrooms>=4)
- bathrooms: number (bathrooms>=3)
- stories: number (stories>=2)
- has_pool: boolean (has_pool=true)
- has_garage: boolean (has_garage=true)

Operators: <, >, <=, >=, =, contains

Priority levels:
- high: critical safety, structural, or major financial impact
- medium: important but not critical
- low: nice-to-know, minor consideration

Available knowledge files:{file_list}

IMPORTANT: Many points won't need @applies_when at all — they are general advice that applies to all properties. Only add conditions when the text SPECIFICALLY mentions property characteristics (age, type, size, HOA, etc.).

Respond with a JSON array. For each point, output:
{{"idx": 0, "useful": true, "target_file": "01_Foundation_Structure.md", "applies_when": ["year_built<1970"], "priority": "high"}}

If not useful: {{"idx": 0, "useful": false}}
If useful but no conditions apply: {{"idx": 0, "useful": true, "target_file": "...", "applies_when": [], "priority": "medium"}}

Return ONLY the JSON array, no other text."""


def call_claude(system: str, user_msg: str) -> str | None:
    """Call Claude API and return the text response."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 4096,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}],
    }

    for attempt in range(3):
        try:
            resp = requests.post(API_URL, json=body, headers=headers, timeout=60)
            if resp.status_code == 200:
                return resp.json()["content"][0]["text"]
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"    API error {resp.status_code}: {resp.text[:200]}")
            return None
        except Exception as e:
            print(f"    Request error: {e}")
            if attempt < 2:
                time.sleep(5)
    return None


def parse_claude_response(text: str) -> list[dict]:
    """Parse Claude's JSON response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code block if present
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        print(f"    Failed to parse response: {text[:200]}")
        return []


def format_batch(points: list[dict], start_idx: int) -> str:
    """Format a batch of points for Claude."""
    lines = []
    for i, pt in enumerate(points):
        idx = start_idx + i
        text = pt.get("full_text", pt.get("text", ""))
        category = pt.get("category", "")
        source = pt.get("source_file", "?")
        existing_aw = pt.get("applies_when", [])
        aw_str = ""
        if existing_aw:
            aw_str = f" [existing tags: {json.dumps(existing_aw)}]"
        lines.append(f"[{idx}] ({source} / {category}){aw_str}\n{text}\n")
    return "\n".join(lines)


def enrich_points(export_path: str) -> dict:
    """Main enrichment pipeline: read export, send to Claude, collect results."""
    with open(export_path) as f:
        export = json.load(f)

    # Flatten all points with their source file
    all_points = []
    for source_file, entries in export["by_source_file"].items():
        for entry in entries:
            entry["source_file"] = source_file
            all_points.append(entry)

    print(f"Total points to analyze: {len(all_points)}")

    knowledge_sections = load_knowledge_sections()
    system_prompt = build_system_prompt(knowledge_sections)

    enriched = []
    total_useful = 0
    total_with_tags = 0

    for batch_start in range(0, len(all_points), BATCH_SIZE):
        batch = all_points[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(all_points) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches} "
              f"(points {batch_start}-{batch_start + len(batch) - 1})...")

        user_msg = format_batch(batch, batch_start)
        response = call_claude(system_prompt, user_msg)
        if not response:
            print(f"    FAILED - skipping batch")
            continue

        results = parse_claude_response(response)
        if not results:
            print(f"    No valid results from batch")
            continue

        # Map results back to points
        for result in results:
            idx = result.get("idx", -1)
            if idx < batch_start or idx >= batch_start + len(batch):
                continue
            pt = batch[idx - batch_start]
            if not result.get("useful", False):
                continue

            total_useful += 1
            aw_tags = result.get("applies_when", [])
            if aw_tags:
                total_with_tags += 1

            enriched.append({
                "text": pt.get("full_text", pt.get("text", "")),
                "category": pt.get("category", ""),
                "source_file": pt.get("source_file", ""),
                "target_file": result.get("target_file", ""),
                "applies_when": aw_tags,
                "priority": result.get("priority", "medium"),
                "original_applies_when": pt.get("applies_when", []),
            })

        print(f"    -> {sum(1 for r in results if r.get('useful'))} useful, "
              f"{sum(1 for r in results if r.get('applies_when'))} with tags")

        # Small delay between batches
        time.sleep(1)

    output = {
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "source_export": export_path,
        "total_analyzed": len(all_points),
        "total_useful": total_useful,
        "total_with_applies_when": total_with_tags,
        "points": enriched,
    }

    with open(ENRICHED_OUTPUT, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nEnrichment summary:")
    print(f"  Analyzed: {len(all_points)}")
    print(f"  Useful: {total_useful}")
    print(f"  With @applies_when: {total_with_tags}")
    print(f"  Written to: {ENRICHED_OUTPUT}")

    return output


def find_md_file(filename: str) -> str | None:
    """Find full path to a knowledge markdown file."""
    for root, _dirs, files in os.walk(KNOWLEDGE_DIR):
        for f in files:
            if f == filename:
                return os.path.join(root, f)
    return None


def apply_enriched(dry_run: bool = True):
    """Apply enriched points to knowledge markdown files."""
    if not os.path.exists(ENRICHED_OUTPUT):
        print(f"No enriched output found at {ENRICHED_OUTPUT}")
        print("Run without --apply first to generate enrichment.")
        sys.exit(1)

    with open(ENRICHED_OUTPUT) as f:
        data = json.load(f)

    points = data["points"]
    print(f"Enriched points: {len(points)}")

    # Group by target file
    by_target: dict[str, list[dict]] = {}
    for pt in points:
        target = pt.get("target_file", "")
        if target:
            by_target.setdefault(target, []).append(pt)

    total_injected = 0
    files_modified = 0

    for target_file, pts in sorted(by_target.items()):
        md_path = find_md_file(target_file)
        if not md_path:
            print(f"  SKIP {target_file}: not found")
            continue

        # Filter to only points with applies_when tags
        tagged_pts = [p for p in pts if p.get("applies_when")]
        if not tagged_pts:
            print(f"  {target_file}: {len(pts)} points, 0 with tags to inject")
            continue

        with open(md_path) as f:
            lines = f.readlines()

        injections = []
        for pt in tagged_pts:
            text = pt["text"]
            category = pt["category"]
            aw_tags = pt["applies_when"]
            priority = pt.get("priority", "medium")

            # Find matching section by searching for the text or category
            best_line = None
            best_score = 0

            for i, line in enumerate(lines):
                stripped = line.strip()
                # Check if this line contains the start of the point's text
                text_start = text[:60].strip()
                if text_start and text_start.lower() in stripped.lower():
                    best_line = i
                    best_score = 1.0
                    break

            # If no text match, find by category heading
            if best_line is None:
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    m = re.match(r'^#{2,3}\s+(.+)$', stripped)
                    if m and m.group(1).strip().lower() == category.lower():
                        best_line = i
                        best_score = 0.8
                        break

            if best_line is not None:
                # Check if tags already exist after this heading
                # Walk backward to find the heading for this content
                heading_line = best_line
                if best_score == 1.0:
                    # Found text, walk back to find heading
                    for j in range(best_line - 1, max(best_line - 15, -1), -1):
                        s = lines[j].strip()
                        if re.match(r'^#{2,3}\s+', s):
                            heading_line = j
                            break

                # Check if heading already has these tags
                has_tags = False
                for j in range(heading_line + 1, min(heading_line + 10, len(lines))):
                    if lines[j].strip().startswith("@applies_when:"):
                        has_tags = True
                        break
                    if lines[j].strip() and not lines[j].strip().startswith("@"):
                        break

                tag_lines = []
                for aw in aw_tags:
                    # Parse "year_built<1970" format
                    if isinstance(aw, str):
                        tag_lines.append(f"@applies_when: {aw}")
                    elif isinstance(aw, dict):
                        attr = aw.get("attribute", "")
                        op = aw.get("operator", "")
                        val = aw.get("value", "")
                        tag_lines.append(f"@applies_when: {attr}{op}{val}")
                    else:
                        tag_lines.append(f"@applies_when: {aw}")

                if priority != "medium":
                    tag_lines.append(f"@priority: {priority}")

                if tag_lines and not has_tags:
                    injections.append({
                        "line": heading_line + 1,
                        "tags": tag_lines,
                        "category": category,
                        "text_preview": text[:80],
                    })

        if not injections:
            print(f"  {target_file}: {len(tagged_pts)} tagged, 0 injectable (already tagged or no match)")
            continue

        # Deduplicate by line number (keep first)
        seen_lines = set()
        unique_inj = []
        for inj in injections:
            if inj["line"] not in seen_lines:
                seen_lines.add(inj["line"])
                unique_inj.append(inj)
        injections = unique_inj

        files_modified += 1
        total_injected += len(injections)
        print(f"  {target_file}: injecting {len(injections)} tag blocks")
        for inj in injections:
            for t in inj["tags"]:
                print(f"    L{inj['line']+1} [{inj['category']}]: {t}")

        if not dry_run:
            # Apply in reverse order
            result = list(lines)
            for inj in sorted(injections, key=lambda x: x["line"], reverse=True):
                insert_at = inj["line"]
                for k, tag in enumerate(inj["tags"]):
                    result.insert(insert_at + k, tag + "\n")

            with open(md_path, "w") as f:
                f.writelines(result)
            print(f"    -> Written")

    print(f"\n{'DRY RUN ' if dry_run else ''}Summary:")
    print(f"  Files modified: {files_modified}")
    print(f"  Tag blocks injected: {total_injected}")
    if dry_run:
        print("\nRe-run with --apply (without --dry-run) to write files.")


def main():
    parser = argparse.ArgumentParser(
        description="Enrich Qdrant knowledge points with Claude"
    )
    parser.add_argument(
        "--export", default=DEFAULT_EXPORT,
        help=f"Path to qdrant export JSON (default: {DEFAULT_EXPORT})"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply enriched tags to markdown files (run enrichment first without this)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview --apply changes without writing"
    )
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY and not args.apply:
        print("Error: ANTHROPIC_API_KEY environment variable required")
        sys.exit(1)

    if args.apply:
        apply_enriched(dry_run=args.dry_run)
    else:
        if not os.path.exists(args.export):
            print(f"Export not found: {args.export}")
            print("Run: python3 backend/scripts/extract_qdrant_tags.py --all")
            sys.exit(1)
        enrich_points(args.export)


if __name__ == "__main__":
    main()
