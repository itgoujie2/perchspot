"""
Knowledge Store API Endpoints

Browse, search, ingest, and manage knowledge points for the admin portal.
All endpoints require admin authentication via X-Admin-Password header.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.config import settings
from app.services.knowledge.skill_knowledge_service import (
    KNOWLEDGE_DIR,
    KNOWLEDGE_FILE_MAP,
    _file_cache,
    _parsed_cache,
    _load_file,
    _get_parsed_points,
    _parse_markdown_to_points,
)

logger = logging.getLogger(__name__)
router = APIRouter()

DELETED_POINTS_FILE = KNOWLEDGE_DIR / ".deleted_points.json"
CUSTOM_KNOWLEDGE_DIR = KNOWLEDGE_DIR / "custom"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def verify_admin(x_admin_password: Optional[str] = Header(None)):
    if not x_admin_password:
        raise HTTPException(status_code=401, detail="Admin password required")
    if x_admin_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")


# ---------------------------------------------------------------------------
# Deleted-points tombstone (avoids modifying markdown files directly)
# ---------------------------------------------------------------------------

def _get_deleted_ids() -> set:
    try:
        if DELETED_POINTS_FILE.exists():
            return set(json.loads(DELETED_POINTS_FILE.read_text()))
    except Exception:
        pass
    return set()


def _save_deleted_ids(deleted: set):
    try:
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        DELETED_POINTS_FILE.write_text(json.dumps(sorted(deleted)))
    except Exception as e:
        logger.error(f"Failed to save deleted points: {e}")


# ---------------------------------------------------------------------------
# Helper: all points with stable IDs across all files
# ---------------------------------------------------------------------------

def _all_file_keys() -> List[str]:
    """Return all file keys: hardcoded + custom uploaded."""
    keys = list(KNOWLEDGE_FILE_MAP.keys())
    if CUSTOM_KNOWLEDGE_DIR.exists():
        for md_file in sorted(CUSTOM_KNOWLEDGE_DIR.glob("*.md")):
            key = f"custom_{md_file.stem}"
            if key not in KNOWLEDGE_FILE_MAP and key not in keys:
                keys.append(key)
    return keys


def _load_custom_file(key: str) -> Optional[str]:
    """Load a custom (non-hardcoded) knowledge file."""
    if key in _file_cache:
        return _file_cache[key]
    if not key.startswith("custom_"):
        return None
    stem = key[len("custom_"):]
    path = CUSTOM_KNOWLEDGE_DIR / f"{stem}.md"
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        _file_cache[key] = content
        return content
    except Exception as e:
        logger.error(f"Failed to read custom knowledge file {path}: {e}")
        return None


def _get_points_for_key(key: str):
    """Get parsed KnowledgePoint list for any file key (hardcoded or custom)."""
    if key in KNOWLEDGE_FILE_MAP:
        return _get_parsed_points(key)
    # Custom file
    if key in _parsed_cache:
        return _parsed_cache[key]
    content = _load_custom_file(key)
    if not content:
        return []
    stem = key[len("custom_"):] if key.startswith("custom_") else key
    points = _parse_markdown_to_points(content, f"{stem}.md")
    _parsed_cache[key] = points
    return points


def _get_all_points(deleted_ids: Optional[set] = None):
    """Return list of dicts with id/text/category/source_file, excluding deleted."""
    if deleted_ids is None:
        deleted_ids = _get_deleted_ids()
    result = []
    for file_key in _all_file_keys():
        points = _get_points_for_key(file_key)
        for i, pt in enumerate(points):
            point_id = f"{file_key}:{i}"
            if point_id not in deleted_ids:
                result.append({
                    "id": point_id,
                    "text": pt.text,
                    "category": pt.category,
                    "source_file": pt.source_file,
                })
    return result


# ---------------------------------------------------------------------------
# Response models (legacy — for /files endpoints)
# ---------------------------------------------------------------------------

class FileInfo(BaseModel):
    key: str
    path: str
    size_bytes: int
    points_count: int


class FilesResponse(BaseModel):
    files: List[FileInfo]
    total_files: int
    total_bytes: int
    total_points: int


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@router.get("/status", dependencies=[Depends(verify_admin)])
async def knowledge_status():
    """Get knowledge store status. Returns point_count for admin portal."""
    deleted_ids = _get_deleted_ids()
    total_points = 0
    total_bytes = 0
    total_files = 0
    missing_files = []

    for key in _all_file_keys():
        if key in KNOWLEDGE_FILE_MAP:
            content = _load_file(key)
            rel_path = KNOWLEDGE_FILE_MAP[key]
        else:
            content = _load_custom_file(key)
            rel_path = f"custom/{key[len('custom_'):]}.md"

        if content:
            total_files += 1
            total_bytes += len(content)
            pts = _get_points_for_key(key)
            active = sum(1 for i in range(len(pts)) if f"{key}:{i}" not in deleted_ids)
            total_points += active
        else:
            missing_files.append(rel_path)

    return {
        "status": "ok" if not missing_files else "degraded",
        "collection": "knowledge",
        "point_count": total_points,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "missing_files": missing_files,
    }


# ---------------------------------------------------------------------------
# Files (legacy endpoints — still used by other parts of admin portal)
# ---------------------------------------------------------------------------

@router.get("/files", response_model=FilesResponse, dependencies=[Depends(verify_admin)])
async def list_knowledge_files():
    """List all knowledge files with their sizes and point counts."""
    files = []
    total_bytes = 0
    total_points = 0

    for key, rel_path in sorted(KNOWLEDGE_FILE_MAP.items()):
        content = _load_file(key)
        size = len(content) if content else 0
        points = _get_parsed_points(key)
        points_count = len(points)

        files.append(FileInfo(key=key, path=rel_path, size_bytes=size, points_count=points_count))
        total_bytes += size
        total_points += points_count

    return FilesResponse(
        files=files,
        total_files=len(files),
        total_bytes=total_bytes,
        total_points=total_points,
    )


@router.get("/files/{file_key}", dependencies=[Depends(verify_admin)])
async def get_knowledge_file(file_key: str):
    """Get the content of a specific knowledge file."""
    if file_key not in KNOWLEDGE_FILE_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown file key: {file_key}")
    content = _load_file(file_key)
    if content is None:
        raise HTTPException(status_code=404, detail=f"File not found on disk: {file_key}")
    points = _get_parsed_points(file_key)
    return {
        "key": file_key,
        "path": KNOWLEDGE_FILE_MAP[file_key],
        "content": content,
        "size_bytes": len(content),
        "points_count": len(points),
    }


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

@router.get("/filters", dependencies=[Depends(verify_admin)])
async def get_filters():
    """Return distinct source files and categories across all knowledge points."""
    deleted_ids = _get_deleted_ids()
    sources: set = set()
    categories: set = set()

    for file_key in _all_file_keys():
        points = _get_points_for_key(file_key)
        for i, pt in enumerate(points):
            if f"{file_key}:{i}" not in deleted_ids:
                if pt.source_file:
                    sources.add(pt.source_file)
                if pt.category:
                    categories.add(pt.category)

    return {
        "sources": sorted(sources),
        "categories": sorted(categories),
    }


# ---------------------------------------------------------------------------
# List (browse with pagination + filtering)
# ---------------------------------------------------------------------------

class ListRequest(BaseModel):
    limit: int = 50
    offset: int = 0
    source_filter: Optional[str] = None
    category_filter: Optional[str] = None


@router.post("/list", dependencies=[Depends(verify_admin)])
async def list_points(req: ListRequest):
    """Browse all knowledge points with optional source/category filtering."""
    deleted_ids = _get_deleted_ids()
    all_pts = _get_all_points(deleted_ids)

    if req.source_filter:
        all_pts = [p for p in all_pts if p["source_file"] == req.source_filter]
    if req.category_filter:
        all_pts = [p for p in all_pts if p["category"] == req.category_filter]

    total = len(all_pts)
    page = all_pts[req.offset: req.offset + req.limit]
    return {
        "points": page,
        "total": total,
        "has_more": (req.offset + req.limit) < total,
    }


# ---------------------------------------------------------------------------
# Search (keyword-based, no vector similarity)
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    limit: int = 20


@router.post("/search", dependencies=[Depends(verify_admin)])
async def search_points(req: SearchRequest):
    """Keyword search across all knowledge points."""
    deleted_ids = _get_deleted_ids()
    all_pts = _get_all_points(deleted_ids)

    terms = req.query.lower().split()
    scored = []
    for pt in all_pts:
        text_lower = pt["text"].lower()
        cat_lower = pt["category"].lower()
        hits = sum(1 for t in terms if t in text_lower or t in cat_lower)
        if hits > 0:
            scored.append((hits, pt))

    scored.sort(key=lambda x: -x[0])
    results = [
        {**pt, "score": round(hits / len(terms), 2)}
        for hits, pt in scored[: req.limit]
    ]
    return {"results": results}


# ---------------------------------------------------------------------------
# Ingest (upload a .md file — saved to custom/ directory)
# ---------------------------------------------------------------------------

@router.post("/ingest", dependencies=[Depends(verify_admin)])
async def ingest_file(file: UploadFile = File(...)):
    """
    Upload a markdown file to the custom knowledge directory.
    Returns synchronous result (no async job needed for file-based system).
    """
    if not file.filename or not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are accepted")

    try:
        content = (await file.read()).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read file as UTF-8 text")

    if not content.strip():
        raise HTTPException(status_code=400, detail="File is empty")

    # Save to custom dir
    CUSTOM_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-.]", "_", file.filename)
    dest = CUSTOM_KNOWLEDGE_DIR / safe_name

    dest.write_text(content, encoding="utf-8")

    # Parse and cache
    stem = safe_name[:-3]  # remove .md
    key = f"custom_{stem}"
    _file_cache[key] = content
    if key in _parsed_cache:
        del _parsed_cache[key]  # invalidate cache so it re-parses
    points = _get_points_for_key(key)

    logger.info(f"Ingested custom knowledge file: {safe_name} ({len(points)} points)")

    return {
        "status": "completed",
        "result": {
            "points_ingested": len(points),
            "source_file": safe_name,
        },
    }


@router.get("/ingest/status/{job_id}", dependencies=[Depends(verify_admin)])
async def ingest_status(job_id: str):
    """
    Ingest job status — always completed since ingest is synchronous.
    Kept for frontend compatibility.
    """
    return {"status": "completed", "result": None}


# ---------------------------------------------------------------------------
# Delete single point
# ---------------------------------------------------------------------------

@router.delete("/point/{point_id:path}", dependencies=[Depends(verify_admin)])
async def delete_point(point_id: str):
    """Mark a knowledge point as deleted (tombstone — does not modify .md files)."""
    # Validate the ID looks reasonable
    if ":" not in point_id:
        raise HTTPException(status_code=400, detail="Invalid point ID format")

    deleted = _get_deleted_ids()
    deleted.add(point_id)
    _save_deleted_ids(deleted)

    return {"deleted": point_id}


# ---------------------------------------------------------------------------
# Bulk delete
# ---------------------------------------------------------------------------

class BulkDeleteRequest(BaseModel):
    point_ids: List[str]


@router.post("/points/delete", dependencies=[Depends(verify_admin)])
async def bulk_delete_points(req: BulkDeleteRequest):
    """Bulk mark knowledge points as deleted."""
    if not req.point_ids:
        raise HTTPException(status_code=400, detail="No point IDs provided")

    deleted = _get_deleted_ids()
    deleted.update(req.point_ids)
    _save_deleted_ids(deleted)

    return {"deleted_count": len(req.point_ids)}
