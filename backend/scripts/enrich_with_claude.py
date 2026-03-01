#!/usr/bin/env python3
from __future__ import annotations

"""
Analyze Qdrant knowledge points with Claude and enrich with @applies_when tags.

Reads the full Qdrant export (qdrant_export_all.json), sends points to Claude
for analysis, and produces an enriched output ready for injection into the
knowledge markdown files.

Usage (on EC2):
    cd /opt/perchspot
    # Step 1: Extract all points
    python3 backend/scripts/extract_qdrant_tags.py --all

    # Step 2: Enrich with Claude (3-4 API calls)
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
BATCH_SIZE = 500  # ~4 API calls for 1831 points
API_URL = "https://api.anthropic.com/v1/messages"


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


def build_system_prompt(knowledge_sections: dict[str, list[str]]) -> tuple[str, list[str]]:
    """Build the system prompt with numbered file list to prevent hallucination.
    Returns (prompt_text, ordered_file_names) so caller can map numbers back.
    """
    file_names = sorted(knowledge_sections.keys())
    file_list = ""
    for i, fname in enumerate(file_names):
        headings = knowledge_sections[fname]
        heading_str = ", ".join(headings[:10])
        file_list += f"  {i}: {fname} (sections: {heading_str})\n"

    prompt = f"""You analyze home-buying knowledge points for a property analysis tool.

For each point, decide:
1. Is it USEFUL? Skip generic/obvious advice. Keep specific, actionable knowledge with concrete details (costs, timelines, conditions, thresholds).
2. Which file number (0-{len(file_names)-1}) should it go in? You MUST use a number from the list below.
3. What @applies_when conditions apply? Only add when text clearly references specific property characteristics.

@applies_when attributes and operators (<, >, <=, >=, =, contains):
  year_built (int), has_hoa (bool), hoa_fee (num), property_type (str),
  lot_size_sqft (num), living_area_sqft (num), bedrooms (num), bathrooms (num),
  stories (num), has_pool (bool), has_garage (bool)

Priority: high (safety/structural/major $), medium (important), low (minor)

FILE LIST — use the number, NOT the filename:
{file_list}
RULES:
- Only output USEFUL entries. Skip the rest entirely.
- The "f" field MUST be an integer from 0-{len(file_names)-1}. Do NOT invent filenames.
- Many points won't need @applies_when — only add when text specifically mentions property characteristics.

Output format — JSON array, one object per useful point:
[{{"idx":0,"f":3,"aw":["year_built<1970"],"p":"high"}},{{"idx":5,"f":7,"aw":[],"p":"medium"}}]

Keys: idx (point index), f (file number as integer), aw (applies_when strings), p (priority).
Return ONLY the JSON array."""

    return prompt, file_names


def call_claude(system: str, user_msg: str, max_tokens: int = 8192) -> str | None:
    """Call Claude API and return the text response."""
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user_msg}],
    }

    for attempt in range(3):
        try:
            resp = requests.post(API_URL, json=body, headers=headers, timeout=120)
            if resp.status_code == 200:
                result = resp.json()
                text = result["content"][0]["text"]
                usage = result.get("usage", {})
                print(f"    Tokens: {usage.get('input_tokens', '?')} in, "
                      f"{usage.get('output_tokens', '?')} out")
                return text
            if resp.status_code == 429:
                wait = 15 * (attempt + 1)
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
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        print(f"    Failed to parse response: {text[:300]}")
        return []


def format_points(points: list[dict], start_idx: int) -> str:
    """Format points for Claude, compact format."""
    lines = []
    for i, pt in enumerate(points):
        idx = start_idx + i
        text = pt.get("full_text", pt.get("text", ""))
        category = pt.get("category", "")
        source = pt.get("source_file", "?")
        lines.append(f"[{idx}] <{source}> [{category}]\n{text}")
    return "\n\n".join(lines)


def enrich_points(export_path: str) -> dict:
    """Main enrichment: read export, send to Claude in a few large batches."""
    with open(export_path) as f:
        export = json.load(f)

    # Flatten all points
    all_points = []
    for source_file, entries in export["by_source_file"].items():
        for entry in entries:
            entry["source_file"] = source_file
            all_points.append(entry)

    print(f"Total points to analyze: {len(all_points)}")

    knowledge_sections = load_knowledge_sections()
    system_prompt, file_names = build_system_prompt(knowledge_sections)
    total_batches = (len(all_points) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Sending in {total_batches} batch(es) of ~{BATCH_SIZE} points\n")

    all_results = []

    for batch_start in range(0, len(all_points), BATCH_SIZE):
        batch = all_points[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches} "
              f"(points {batch_start}-{batch_start + len(batch) - 1})...")

        user_msg = format_points(batch, batch_start)
        response = call_claude(system_prompt, user_msg)
        if not response:
            print(f"    FAILED - skipping batch")
            continue

        results = parse_claude_response(response)
        print(f"    -> {len(results)} useful points returned")
        all_results.extend(results)

        if batch_num < total_batches:
            time.sleep(2)

    # Map results back to source points and build enriched output
    enriched = []
    skipped_bad_file = 0
    for result in all_results:
        idx = result.get("idx", -1)
        if idx < 0 or idx >= len(all_points):
            continue
        pt = all_points[idx]

        # Map file number back to filename
        file_num = result.get("f", -1)
        if not isinstance(file_num, int) or file_num < 0 or file_num >= len(file_names):
            skipped_bad_file += 1
            continue
        target_file = file_names[file_num]

        enriched.append({
            "text": pt.get("full_text", pt.get("text", "")),
            "category": pt.get("category", ""),
            "source_file": pt.get("source_file", ""),
            "target_file": target_file,
            "applies_when": result.get("aw", []),
            "priority": result.get("p", "medium"),
        })

    if skipped_bad_file:
        print(f"  Skipped {skipped_bad_file} results with invalid file numbers")

    with_tags = sum(1 for e in enriched if e["applies_when"])

    output = {
        "enriched_at": datetime.now(timezone.utc).isoformat(),
        "source_export": export_path,
        "total_analyzed": len(all_points),
        "total_useful": len(enriched),
        "total_with_applies_when": with_tags,
        "points": enriched,
    }

    with open(ENRICHED_OUTPUT, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nEnrichment summary:")
    print(f"  Analyzed: {len(all_points)}")
    print(f"  Useful: {len(enriched)}")
    print(f"  With @applies_when: {with_tags}")
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

    # Group by target file, only those with applies_when
    by_target: dict[str, list[dict]] = {}
    for pt in points:
        target = pt.get("target_file", "")
        if target and pt.get("applies_when"):
            by_target.setdefault(target, []).append(pt)

    total_injected = 0
    files_modified = 0

    for target_file, pts in sorted(by_target.items()):
        md_path = find_md_file(target_file)
        if not md_path:
            print(f"  SKIP {target_file}: not found")
            continue

        with open(md_path) as f:
            lines = f.readlines()

        injections = []
        for pt in pts:
            text = pt["text"]
            category = pt["category"]
            aw_tags = pt["applies_when"]
            priority = pt.get("priority", "medium")

            # Find matching section: first try text match, then category heading
            heading_line = None

            # Try to find the text content in the file
            text_start = text[:60].strip().lower()
            if text_start:
                for i, line in enumerate(lines):
                    if text_start in line.strip().lower():
                        # Walk back to heading
                        for j in range(i - 1, max(i - 15, -1), -1):
                            if re.match(r'^#{2,3}\s+', lines[j].strip()):
                                heading_line = j
                                break
                        break

            # Fallback: find by category heading
            if heading_line is None:
                for i, line in enumerate(lines):
                    m = re.match(r'^#{2,3}\s+(.+)$', line.strip())
                    if m and m.group(1).strip().lower() == category.lower():
                        heading_line = i
                        break

            if heading_line is None:
                continue

            # Check if heading already has @applies_when tags
            has_tags = False
            for j in range(heading_line + 1, min(heading_line + 10, len(lines))):
                s = lines[j].strip()
                if s.startswith("@applies_when:"):
                    has_tags = True
                    break
                if s and not s.startswith("@") and s != "":
                    break

            if has_tags:
                continue

            # Build tag lines
            tag_lines = []
            for aw in aw_tags:
                if isinstance(aw, str):
                    tag_lines.append(f"@applies_when: {aw}")
                elif isinstance(aw, dict):
                    tag_lines.append(
                        f"@applies_when: {aw['attribute']}{aw['operator']}{aw['value']}"
                    )
            if priority != "medium":
                tag_lines.append(f"@priority: {priority}")

            if tag_lines:
                injections.append({
                    "line": heading_line + 1,
                    "tags": tag_lines,
                    "category": category,
                    "text_preview": text[:80],
                })

        # Deduplicate by line number
        seen_lines = set()
        unique_inj = []
        for inj in injections:
            if inj["line"] not in seen_lines:
                seen_lines.add(inj["line"])
                unique_inj.append(inj)
        injections = unique_inj

        if not injections:
            continue

        files_modified += 1
        total_injected += len(injections)
        print(f"  {target_file}: injecting {len(injections)} tag blocks")
        for inj in injections:
            for t in inj["tags"]:
                print(f"    L{inj['line']+1} [{inj['category']}]: {t}")

        if not dry_run:
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
        help="Apply enriched tags to markdown files (run enrichment first)"
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
