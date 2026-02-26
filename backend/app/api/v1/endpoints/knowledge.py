"""
Knowledge Store API Endpoints — Read-only file-based

Lists available knowledge files and their content.
All endpoints require admin authentication via X-Admin-Password header.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel

from app.config import settings
from app.services.knowledge.skill_knowledge_service import (
    KNOWLEDGE_FILE_MAP,
    _load_file,
    _get_parsed_points,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def verify_admin(x_admin_password: Optional[str] = Header(None)):
    """Verify admin password from request header."""
    if not x_admin_password:
        raise HTTPException(status_code=401, detail="Admin password required")
    if x_admin_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")


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

        files.append(FileInfo(
            key=key,
            path=rel_path,
            size_bytes=size,
            points_count=points_count,
        ))
        total_bytes += size
        total_points += points_count

    return FilesResponse(
        files=files,
        total_files=len(files),
        total_bytes=total_bytes,
        total_points=total_points,
    )


class FileContentResponse(BaseModel):
    key: str
    path: str
    content: str
    size_bytes: int
    points_count: int


@router.get("/files/{file_key}", response_model=FileContentResponse, dependencies=[Depends(verify_admin)])
async def get_knowledge_file(file_key: str):
    """Get the content of a specific knowledge file."""
    if file_key not in KNOWLEDGE_FILE_MAP:
        raise HTTPException(status_code=404, detail=f"Unknown file key: {file_key}")

    content = _load_file(file_key)
    if content is None:
        raise HTTPException(status_code=404, detail=f"File not found on disk: {file_key}")

    points = _get_parsed_points(file_key)

    return FileContentResponse(
        key=file_key,
        path=KNOWLEDGE_FILE_MAP[file_key],
        content=content,
        size_bytes=len(content),
        points_count=len(points),
    )


@router.get("/status", dependencies=[Depends(verify_admin)])
async def knowledge_status():
    """Get knowledge store status."""
    total_files = 0
    total_bytes = 0
    total_points = 0
    missing_files = []

    for key, rel_path in KNOWLEDGE_FILE_MAP.items():
        content = _load_file(key)
        if content:
            total_files += 1
            total_bytes += len(content)
            total_points += len(_get_parsed_points(key))
        else:
            missing_files.append(rel_path)

    return {
        "status": "ok" if not missing_files else "degraded",
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_points": total_points,
        "missing_files": missing_files,
    }
