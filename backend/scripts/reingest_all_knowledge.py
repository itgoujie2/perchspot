#!/usr/bin/env python3
"""
Re-ingest all knowledge markdown files into Qdrant.

With the delete-before-upsert fix in ingestion_service.py, this script
purges all stale/orphan data and leaves only current knowledge points.

Usage:
    docker compose exec backend python scripts/reingest_all_knowledge.py
"""
import os
import sys
import glob
import logging

# Add the backend root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.knowledge.ingestion_service import get_ingestion_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")


def main():
    ingestion = get_ingestion_service()

    md_files = sorted(glob.glob(os.path.join(KNOWLEDGE_DIR, "**", "*.md"), recursive=True))
    if not md_files:
        logger.warning(f"No .md files found in {KNOWLEDGE_DIR}")
        return

    logger.info(f"Found {len(md_files)} markdown files to re-ingest")

    total_points = 0
    for filepath in md_files:
        rel = os.path.relpath(filepath, KNOWLEDGE_DIR)
        source_id = os.path.basename(filepath)
        logger.info(f"Ingesting: {rel} (source_id={source_id})")

        try:
            result = ingestion.ingest_markdown(filepath, source_id=source_id)
            count = result.get("points_ingested", 0)
            total_points += count
            logger.info(f"  -> {count} points ingested")
        except Exception as e:
            logger.error(f"  -> FAILED: {e}")

    logger.info(f"Done. Total points ingested: {total_points}")


if __name__ == "__main__":
    main()
