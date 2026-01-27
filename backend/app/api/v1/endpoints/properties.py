"""
Properties endpoints - main analysis API
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
import logging
import uuid

from app.database.connection import get_db
from app.models.schemas import (
    PropertyAnalysisRequest,
    PropertyAnalysisResponse,
    AnalysisStatusResponse,
    AnalysisStatus
)
from app.tasks.analysis_tasks import analyze_property_task
from celery.result import AsyncResult

logger = logging.getLogger(__name__)

router = APIRouter()

# Store for analysis results (in production, use database)
analysis_store = {}


@router.post("/analyze", response_model=PropertyAnalysisResponse)
async def analyze_property(
    request: PropertyAnalysisRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze a property by address

    This endpoint:
    1. Validates the address
    2. Creates an analysis job
    3. Triggers background Celery task
    4. Returns job ID for status polling

    The actual analysis runs asynchronously.
    """
    try:
        logger.info(f"Received analysis request for: {request.address}")

        # Generate analysis ID
        analysis_id = str(uuid.uuid4())

        # Trigger Celery task
        task = analyze_property_task.delay(analysis_id, request.address)

        logger.info(f"Started analysis task {task.id} for analysis {analysis_id}")

        return PropertyAnalysisResponse(
            analysis_id=task.id,  # Use Celery task ID for tracking
            status=AnalysisStatus.PENDING,
            message="Analysis started. Poll /analysis/{id}/status for updates."
        )

    except Exception as e:
        logger.error(f"Error starting analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{analysis_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the status of an analysis job

    Poll this endpoint to check analysis progress.
    """
    try:
        # Get Celery task result
        task_result = AsyncResult(analysis_id)

        # Map Celery states to our AnalysisStatus
        status_map = {
            'PENDING': AnalysisStatus.PENDING,
            'STARTED': AnalysisStatus.PROCESSING,
            'PROGRESS': AnalysisStatus.PROCESSING,
            'SUCCESS': AnalysisStatus.COMPLETED,
            'FAILURE': AnalysisStatus.FAILED
        }

        status = status_map.get(task_result.state, AnalysisStatus.PENDING)

        # Get progress info if available
        progress = 0
        current_step = "Waiting to start"
        error_message = None

        if task_result.state == 'PROGRESS':
            info = task_result.info or {}
            progress = info.get('current', 0)
            current_step = info.get('status', 'Processing...')
        elif task_result.state == 'SUCCESS':
            progress = 100
            current_step = "Complete"
        elif task_result.state == 'FAILURE':
            error_message = str(task_result.info)
            current_step = "Failed"

        return AnalysisStatusResponse(
            analysis_id=analysis_id,
            status=status,
            progress=progress,
            current_step=current_step,
            error_message=error_message
        )

    except Exception as e:
        logger.error(f"Error fetching analysis status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{analysis_id}/report")
async def get_analysis_report(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the complete analysis report (JSON format)

    Returns detailed analysis with all scores and insights.
    """
    try:
        # Get Celery task result
        task_result = AsyncResult(analysis_id)

        if task_result.state != 'SUCCESS':
            raise HTTPException(
                status_code=404,
                detail=f"Analysis not complete. Status: {task_result.state}"
            )

        # Get result
        result = task_result.get()
        analysis_data = result.get('result', {})

        logger.info(f"Returning analysis report for {analysis_id}")

        return analysis_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching analysis report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analysis/{analysis_id}/report/pdf")
async def download_pdf_report(
    analysis_id: str,
    db: Session = Depends(get_db)
):
    """
    Download analysis report as PDF

    Returns a PDF file with the complete property analysis.
    """
    try:
        # Get Celery task result
        task_result = AsyncResult(analysis_id)

        if task_result.state != 'SUCCESS':
            raise HTTPException(
                status_code=404,
                detail=f"Analysis not complete. Status: {task_result.state}"
            )

        # Get result
        result = task_result.get()
        analysis_data = result.get('result', {})

        # Generate PDF
        from app.services.reporting.pdf_generator import PDFReportGenerator
        pdf_generator = PDFReportGenerator()
        pdf_bytes = pdf_generator.generate_report(analysis_data)

        # Return PDF
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=property_report_{analysis_id[:8]}.pdf"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
