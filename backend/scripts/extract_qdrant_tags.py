#!/usr/bin/env python3
"""
Extract enriched tags from Qdrant knowledge collection.

Scrolls all points from the Qdrant REST API and exports those with
@applies_when tags or non-default @priority to a JSON file for merging
back into the markdown source files.

Usage (on EC2):
    cd /opt/perchspot
    python backend/scripts/extract_qdrant_tags.py

Output: backend/scripts/qdrant_export.json
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION = "knowledge"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "qdrant_export.json")
SCROLL_LIMIT = 100  # points per scroll request


def scroll_all_points() -> list[dict]:
    """Scroll through all points in the knowledge collection."""
    url = f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll"
    all_points = []
    offset = None

    while True:
        body = {
            "limit": SCROLL_LIMIT,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            body["offset"] = offset

        resp = requests.post(url, json=body, timeout=30)
        if resp.status_code != 200:
            print(f"Error: Qdrant returned {resp.status_code}: {resp.text}")
            sys.exit(1)

        data = resp.json().get("result", {})
        points = data.get("points", [])
        all_points.extend(points)

        next_offset = data.get("next_page_offset")
        if next_offset is None or not points:
            break
        offset = next_offset

        print(f"  Scrolled {len(all_points)} points so far...")

    return all_points


def format_condition(cond: dict) -> str:
    """Format an applies_when condition for display."""
    return f"{cond.get('attribute', '?')}{cond.get('operator', '?')}{cond.get('value', '?')}"


def main():
    # Check collection exists
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    try:
        info_resp = requests.get(
            f"{QDRANT_URL}/collections/{COLLECTION}", timeout=10
        )
        if info_resp.status_code != 200:
            print(f"Collection '{COLLECTION}' not found (status {info_resp.status_code})")
            sys.exit(1)
        count = info_resp.json().get("result", {}).get("points_count", "?")
        print(f"Collection '{COLLECTION}' has {count} points")
    except requests.ConnectionError:
        print(f"Cannot connect to Qdrant at {QDRANT_URL}")
        sys.exit(1)

    # Scroll all points
    print("Scrolling all points...")
    points = scroll_all_points()
    print(f"Total points retrieved: {len(points)}")

    # Group by source file and filter for those with tags
    by_source: dict[str, list[dict]] = {}
    points_with_tags = 0

    for pt in points:
        payload = pt.get("payload", {})
        source_file = payload.get("source_file", "unknown")
        applies_when = payload.get("applies_when", [])
        priority = payload.get("priority", "medium")

        has_enrichment = bool(applies_when) or priority != "medium"

        if has_enrichment:
            points_with_tags += 1
            entry = {
                "text": payload.get("text", "")[:150],
                "full_text": payload.get("text", ""),
                "category": payload.get("category", ""),
                "heading": payload.get("heading", ""),
                "applies_when": applies_when,
                "priority": priority,
                "point_index": payload.get("point_index", -1),
            }
            by_source.setdefault(source_file, []).append(entry)

    # Sort entries within each file by point_index
    for source_file in by_source:
        by_source[source_file].sort(key=lambda e: e.get("point_index", 0))

    # Build export
    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "qdrant_url": QDRANT_URL,
        "total_points": len(points),
        "points_with_tags": points_with_tags,
        "source_files_count": len(by_source),
        "by_source_file": by_source,
    }

    # Write JSON
    with open(OUTPUT_PATH, "w") as f:
        json.dump(export, f, indent=2, default=str)

    print(f"\nExport summary:")
    print(f"  Total points: {len(points)}")
    print(f"  Points with tags: {points_with_tags}")
    print(f"  Source files: {len(by_source)}")
    for src, entries in sorted(by_source.items()):
        print(f"    {src}: {len(entries)} tagged points")
    print(f"\nWritten to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
