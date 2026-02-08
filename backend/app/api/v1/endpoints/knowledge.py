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
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Header, BackgroundTasks
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory ingestion job tracking
_ingestion_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


def verify_admin(x_admin_password: str = Header(...)):
    """Verify admin password from request header."""
    if x_admin_password != settings.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin password")


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    categories: Optional[List[str]] = None


class SearchResultItem(BaseModel):
    text: str
    category: str
    score: float
    source_file: str


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
