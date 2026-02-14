"""
Knowledge Store API Endpoints

Provides ingestion, search, and management of the knowledge store.
All endpoints require admin authentication via X-Admin-Password header.
"""
import logging
import os
import tempfile
import threading
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory ingestion job tracking
_ingestion_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def verify_admin(x_admin_password: Optional[str] = Header(None)):
    """Verify admin password from request header."""
    if not x_admin_password:
        raise HTTPException(status_code=401, detail="Admin password required")
    if x_admin_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    categories: Optional[List[str]] = None


class AppliesWhenCondition(BaseModel):
    attribute: str
    operator: str
    value: Any


class SearchResultItem(BaseModel):
    text: str
    category: str
    score: float
    source_file: str
    priority: Optional[str] = "medium"
    applies_when: Optional[List[AppliesWhenCondition]] = None


class SearchResponse(BaseModel):
    results: List[SearchResultItem]


def _run_ingestion(job_id: str, tmp_path: str, source_id: str):
    """Background task to run ingestion."""
    try:
        from app.services.knowledge.ingestion_service import get_ingestion_service

        with _jobs_lock:
            _ingestion_jobs[job_id]["status"] = "running"

        service = get_ingestion_service()
        result = service.ingest_markdown(tmp_path, source_id=source_id)

        with _jobs_lock:
            _ingestion_jobs[job_id]["status"] = "completed"
            _ingestion_jobs[job_id]["result"] = result
            _ingestion_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

    except Exception as e:
        logger.error(f"Ingestion error for job {job_id}: {e}", exc_info=True)
        with _jobs_lock:
            _ingestion_jobs[job_id]["status"] = "failed"
            _ingestion_jobs[job_id]["error"] = str(e)
            _ingestion_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@router.post("/ingest", dependencies=[Depends(verify_admin)])
async def ingest_markdown(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """Upload and ingest a .md knowledge file (runs in background)."""
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are supported")

    try:
        content = await file.read()

        # Save to temp file
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".md", delete=False,
            prefix=f"knowledge_{file.filename}_"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Create job
        job_id = str(uuid.uuid4())[:8]
        with _jobs_lock:
            _ingestion_jobs[job_id] = {
                "job_id": job_id,
                "source_file": file.filename,
                "status": "queued",
                "started_at": datetime.utcnow().isoformat(),
                "result": None,
                "error": None,
            }

        # Run in background thread (BackgroundTasks runs after response, but we want immediate start)
        thread = threading.Thread(target=_run_ingestion, args=(job_id, tmp_path, file.filename))
        thread.daemon = True
        thread.start()

        return {
            "status": "accepted",
            "job_id": job_id,
            "source_file": file.filename,
            "message": "Ingestion started in background. Check /api/v1/knowledge/ingest/status/{job_id} for progress."
        }

    except Exception as e:
        logger.error(f"Ingestion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ingest/status/{job_id}", dependencies=[Depends(verify_admin)])
async def get_ingestion_status(job_id: str):
    """Get status of a background ingestion job."""
    with _jobs_lock:
        if job_id not in _ingestion_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return _ingestion_jobs[job_id]


@router.get("/ingest/jobs", dependencies=[Depends(verify_admin)])
async def list_ingestion_jobs():
    """List all ingestion jobs."""
    with _jobs_lock:
        return {"jobs": list(_ingestion_jobs.values())}


@router.post("/search", response_model=SearchResponse,
             dependencies=[Depends(verify_admin)])
async def search_knowledge(request: SearchRequest):
    """Hybrid search over the knowledge store."""
    try:
        from app.services.knowledge.search_service import get_search_service

        service = get_search_service()
        results = service.search(
            query=request.query,
            limit=request.limit,
            categories=request.categories,
        )
        return SearchResponse(
            results=[
                SearchResultItem(
                    text=r.text,
                    category=r.category,
                    score=r.score,
                    source_file=r.source_file,
                    priority=r.priority,
                    applies_when=[
                        AppliesWhenCondition(**cond) for cond in (r.applies_when or [])
                    ] if r.applies_when else None,
                )
                for r in results
            ]
        )
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", dependencies=[Depends(verify_admin)])
async def knowledge_status():
    """Get knowledge collection status."""
    try:
        from app.services.knowledge.storage_service import get_storage_service

        service = get_storage_service()
        return service.collection_info()
    except Exception as e:
        logger.error(f"Status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/source/{source_id}",
               dependencies=[Depends(verify_admin)])
async def delete_source(source_id: str):
    """Delete all knowledge points from a source file."""
    try:
        from app.services.knowledge.storage_service import get_storage_service

        service = get_storage_service()
        service.delete_by_source(source_id)
        return {"status": "ok", "deleted_source": source_id}
    except Exception as e:
        logger.error(f"Delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ListPointsRequest(BaseModel):
    limit: int = 100
    offset: int = 0
    source_filter: Optional[str] = None
    category_filter: Optional[str] = None


class KnowledgePoint(BaseModel):
    id: str
    text: str
    category: str
    source_file: str
    applies_when: Optional[List[AppliesWhenCondition]] = None
    priority: Optional[str] = "medium"


class ListPointsResponse(BaseModel):
    points: List[KnowledgePoint]
    count: int
    has_more: bool = False


@router.post("/list", response_model=ListPointsResponse,
             dependencies=[Depends(verify_admin)])
async def list_knowledge_points(request: ListPointsRequest):
    """List all knowledge points with optional filtering."""
    try:
        from app.services.knowledge.storage_service import get_storage_service

        service = get_storage_service()
        result = service.list_points(
            limit=request.limit,
            offset=request.offset,
            source_filter=request.source_filter,
            category_filter=request.category_filter,
        )

        return ListPointsResponse(
            points=[
                KnowledgePoint(
                    id=p["id"],
                    text=p["text"],
                    category=p["category"],
                    source_file=p["source_file"],
                    applies_when=[
                        AppliesWhenCondition(**cond) for cond in (p.get("applies_when") or [])
                    ] if p.get("applies_when") else None,
                    priority=p.get("priority", "medium"),
                )
                for p in result["points"]
            ],
            count=result["count"],
            has_more=result["next_offset"] is not None,
        )
    except Exception as e:
        logger.error(f"List points error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class FilterOptionsResponse(BaseModel):
    sources: List[str]
    categories: List[str]


@router.get("/filters", response_model=FilterOptionsResponse,
            dependencies=[Depends(verify_admin)])
async def get_filter_options():
    """Get available source files and categories for filtering."""
    try:
        from app.services.knowledge.storage_service import get_storage_service

        service = get_storage_service()
        result = service.get_unique_values()

        return FilterOptionsResponse(
            sources=result["sources"],
            categories=result["categories"],
        )
    except Exception as e:
        logger.error(f"Get filters error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/point/{point_id}",
               dependencies=[Depends(verify_admin)])
async def delete_point(point_id: str):
    """Delete a single knowledge point by ID."""
    try:
        from app.services.knowledge.storage_service import get_storage_service

        service = get_storage_service()
        service.delete_point(point_id)
        return {"status": "ok", "deleted_point": point_id}
    except Exception as e:
        logger.error(f"Delete point error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class BulkDeleteRequest(BaseModel):
    point_ids: List[str]


@router.post("/points/delete",
             dependencies=[Depends(verify_admin)])
async def delete_points_bulk(request: BulkDeleteRequest):
    """Delete multiple knowledge points by IDs."""
    try:
        from app.services.knowledge.storage_service import get_storage_service

        service = get_storage_service()
        deleted_count = 0
        for point_id in request.point_ids:
            try:
                service.delete_point(point_id)
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete point {point_id}: {e}")

        return {"status": "ok", "deleted_count": deleted_count, "requested_count": len(request.point_ids)}
    except Exception as e:
        logger.error(f"Bulk delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Auto-tagging endpoints
_auto_tag_jobs: Dict[str, Dict[str, Any]] = {}
_auto_tag_lock = threading.Lock()


class AutoTagRequest(BaseModel):
    dry_run: bool = True  # Default to dry run for safety
    only_untagged: bool = True  # Only process points without existing tags
    source_filter: Optional[str] = None  # Optional: only process specific source


def _run_auto_tagging(job_id: str, dry_run: bool, only_untagged: bool, source_filter: Optional[str]):
    """Background task to run auto-tagging."""
    try:
        from app.services.knowledge.auto_tagging_service import get_auto_tagging_service

        with _auto_tag_lock:
            _auto_tag_jobs[job_id]["status"] = "running"

        service = get_auto_tagging_service()

        def progress_callback(current: int, total: int, result):
            with _auto_tag_lock:
                _auto_tag_jobs[job_id]["progress"] = {
                    "current": current,
                    "total": total,
                    "last_point": result.text_preview if result else None,
                }

        result = service.auto_tag_all(
            dry_run=dry_run,
            only_untagged=only_untagged,
            source_filter=source_filter,
            progress_callback=progress_callback,
        )

        with _auto_tag_lock:
            _auto_tag_jobs[job_id]["status"] = "completed"
            _auto_tag_jobs[job_id]["result"] = result
            _auto_tag_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()

    except Exception as e:
        logger.error(f"Auto-tagging error for job {job_id}: {e}", exc_info=True)
        with _auto_tag_lock:
            _auto_tag_jobs[job_id]["status"] = "failed"
            _auto_tag_jobs[job_id]["error"] = str(e)
            _auto_tag_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()


@router.post("/auto-tag", dependencies=[Depends(verify_admin)])
async def start_auto_tagging(request: AutoTagRequest):
    """
    Start auto-tagging of knowledge points using LLM.

    This analyzes each knowledge point's content and suggests @applies_when tags
    based on the content. Tags determine when knowledge surfaces during property analysis.

    Args:
        dry_run: If True (default), don't actually update points, just return suggestions
        only_untagged: If True (default), only process points without existing tags
        source_filter: Optional source file to filter by

    Returns:
        Job ID to track progress
    """
    job_id = str(uuid.uuid4())[:8]

    with _auto_tag_lock:
        _auto_tag_jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "dry_run": request.dry_run,
            "only_untagged": request.only_untagged,
            "source_filter": request.source_filter,
            "started_at": datetime.utcnow().isoformat(),
            "progress": {"current": 0, "total": 0},
            "result": None,
            "error": None,
        }

    # Run in background thread
    thread = threading.Thread(
        target=_run_auto_tagging,
        args=(job_id, request.dry_run, request.only_untagged, request.source_filter)
    )
    thread.daemon = True
    thread.start()

    return {
        "status": "accepted",
        "job_id": job_id,
        "dry_run": request.dry_run,
        "message": f"Auto-tagging started. Check /api/v1/knowledge/auto-tag/status/{job_id} for progress."
    }


@router.get("/auto-tag/status/{job_id}", dependencies=[Depends(verify_admin)])
async def get_auto_tag_status(job_id: str):
    """Get status of an auto-tagging job."""
    with _auto_tag_lock:
        if job_id not in _auto_tag_jobs:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return _auto_tag_jobs[job_id]


@router.get("/auto-tag/jobs", dependencies=[Depends(verify_admin)])
async def list_auto_tag_jobs():
    """List all auto-tagging jobs."""
    with _auto_tag_lock:
        # Return jobs without full results to keep response small
        jobs_summary = []
        for job in _auto_tag_jobs.values():
            summary = {k: v for k, v in job.items() if k != "result"}
            if job.get("result"):
                summary["result_summary"] = {
                    "total_processed": job["result"].get("total_processed", 0),
                    "total_tagged": job["result"].get("total_tagged", 0),
                    "total_skipped": job["result"].get("total_skipped", 0),
                    "total_errors": job["result"].get("total_errors", 0),
                }
            jobs_summary.append(summary)
        return {"jobs": jobs_summary}


class UpdateTagsRequest(BaseModel):
    applies_when: List[AppliesWhenCondition]
    priority: str = "medium"


@router.put("/point/{point_id}/tags", dependencies=[Depends(verify_admin)])
async def update_point_tags(point_id: str, request: UpdateTagsRequest):
    """
    Manually update tags for a single knowledge point.

    This allows manual editing of @applies_when tags without re-ingesting.
    """
    try:
        from app.services.knowledge.storage_service import get_storage_service

        service = get_storage_service()

        # Convert to dict format for storage
        applies_when_data = [
            {
                "attribute": cond.attribute,
                "operator": cond.operator,
                "value": cond.value,
            }
            for cond in request.applies_when
        ]

        service.update_point_payload(
            point_id=point_id,
            payload_updates={
                "applies_when": applies_when_data,
                "priority": request.priority,
            }
        )

        return {
            "status": "ok",
            "point_id": point_id,
            "applies_when": applies_when_data,
            "priority": request.priority,
        }
    except Exception as e:
        logger.error(f"Update tags error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
