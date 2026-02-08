"""
Document Upload API endpoints - Upload and analyze inspection reports and HOA documents
"""
import logging
import uuid
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.documents.pdf_processor import get_pdf_processor
from app.services.documents.document_classifier import get_document_classifier, DocumentType
from app.services.agent.skills.inspection_skill import InspectionSkill
from app.services.agent.skills.hoa_skill import HOASkill
from app.services.agent.tools.notes_manager import get_notes_manager
from app.api.v1.deps import get_optional_user
from app.database.connection import get_db
from app.models.user import User
from app.services.auth.credit_service import deduct_credits, check_balance
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage (in production, use Redis or database)
document_jobs: Dict[str, Dict[str, Any]] = {}

# Temp directory for uploaded files
UPLOAD_DIR = Path("/tmp/housing_analysis_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document"""
    status: Literal["accepted", "error"]
    job_id: str
    document_type: DocumentType
    address: str
    message: Optional[str] = None
    credit_balance: Optional[float] = None


class DocumentStatusResponse(BaseModel):
    """Response for job status check"""
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    document_type: DocumentType
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    credit_balance: Optional[float] = None


class PropertyDocument(BaseModel):
    """A document associated with a property"""
    id: str
    document_type: DocumentType
    filename: str
    uploaded_at: str
    summary: Optional[str] = None
    score: Optional[int] = None


class PropertyDocumentsResponse(BaseModel):
    """Response listing all documents for a property"""
    address: str
    documents: list[PropertyDocument]


async def process_document(
    job_id: str,
    pdf_path: Path,
    address: str,
    document_type: DocumentType,
    filename: str,
):
    """
    Background task to process uploaded document.
    """
    try:
        document_jobs[job_id]["status"] = "running"
        logger.info(f"Processing document {job_id}: {filename} as {document_type}")

        # Extract text from PDF
        pdf_processor = get_pdf_processor()
        document_text = pdf_processor.extract_text(pdf_path)

        if len(document_text) < 100:
            raise ValueError("Could not extract sufficient text from PDF. It may be a scanned document.")

        # Run appropriate skill
        if document_type == "inspection":
            skill = InspectionSkill()
            analysis = await skill.analyze(
                address=address,
                document_text=document_text,
                filename=filename
            )
        elif document_type == "hoa":
            skill = HOASkill()
            analysis = await skill.analyze(
                address=address,
                document_text=document_text,
                filename=filename
            )
        else:
            raise ValueError(f"Unknown document type: {document_type}")

        # Append to property notes
        notes_manager = get_notes_manager()
        notes_manager.append_document_analysis(
            address=address,
            document_type=document_type,
            analysis=analysis,
            filename=filename
        )

        # Store result
        document_jobs[job_id]["status"] = "completed"
        document_jobs[job_id]["result"] = analysis
        document_jobs[job_id]["completed_at"] = datetime.now().isoformat()

        logger.info(f"Document {job_id} processed successfully. Score: {analysis.get('score')}")

    except Exception as e:
        logger.error(f"Document processing failed for {job_id}: {e}", exc_info=True)
        document_jobs[job_id]["status"] = "failed"
        document_jobs[job_id]["error"] = str(e)

    finally:
        # Clean up temp file
        try:
            if pdf_path.exists():
                pdf_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to clean up temp file {pdf_path}: {e}")


@router.post("/upload/{address:path}", response_model=DocumentUploadResponse)
async def upload_document(
    address: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    document_type: Optional[str] = Form("auto"),
    user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Upload a document (inspection report or HOA doc) for analysis.

    - **address**: Property address this document belongs to
    - **file**: PDF file to upload
    - **document_type**: "inspection", "hoa", or "auto" (auto-detect)
    """
    # Validate file type
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Check file size (max 20MB)
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 20MB")

    # Save to temp file
    job_id = str(uuid.uuid4())
    pdf_path = UPLOAD_DIR / f"{job_id}.pdf"

    try:
        with open(pdf_path, 'wb') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    # Auto-detect document type if needed
    detected_type: DocumentType = "unknown"
    if document_type == "auto" or document_type not in ("inspection", "hoa"):
        try:
            pdf_processor = get_pdf_processor()
            text_preview = pdf_processor.extract_first_n_chars(pdf_path, 2000)
            classifier = get_document_classifier()
            detected_type, confidence = classifier.classify(file.filename, text_preview)
            logger.info(f"Auto-detected document type: {detected_type} (confidence: {confidence})")
        except Exception as e:
            logger.warning(f"Auto-detection failed: {e}")
            detected_type = "unknown"
    else:
        detected_type = document_type  # type: ignore

    if detected_type == "unknown":
        # Clean up and return error
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="Could not determine document type. Please specify 'inspection' or 'hoa'."
        )

    # Estimate cost and check credits
    # Document analysis costs roughly $0.02-0.05
    estimated_cost = 0.05
    user_cost = estimated_cost / (1.0 - settings.PRICING_MARGIN) if settings.PRICING_MARGIN < 1.0 else estimated_cost

    if user:
        balance = float(check_balance(db, user.id))
        if balance < user_cost:
            pdf_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "Insufficient credits for document analysis",
                    "balance": balance,
                    "cost": user_cost,
                }
            )
        # Deduct credits upfront
        deducted = deduct_credits(
            db, user.id, user_cost, "document_analysis", job_id,
            description=f"Document analysis: {file.filename}"
        )
        if not deducted:
            pdf_path.unlink(missing_ok=True)
            raise HTTPException(status_code=402, detail="Failed to deduct credits")

    # Get updated balance after deduction
    current_balance: Optional[float] = None
    user_id: Optional[int] = None
    if user:
        current_balance = float(check_balance(db, user.id))
        user_id = user.id

    # Create job entry
    document_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "document_type": detected_type,
        "address": address,
        "filename": file.filename,
        "uploaded_at": datetime.now().isoformat(),
        "result": None,
        "error": None,
        "user_id": user_id,  # Store user_id for balance lookup in status
    }

    # Start background processing
    background_tasks.add_task(
        process_document,
        job_id=job_id,
        pdf_path=pdf_path,
        address=address,
        document_type=detected_type,
        filename=file.filename,
    )

    return DocumentUploadResponse(
        status="accepted",
        job_id=job_id,
        document_type=detected_type,
        address=address,
        message=f"Document accepted for {detected_type} analysis",
        credit_balance=current_balance,
    )


@router.get("/status/{job_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Check the status of a document analysis job.
    """
    if job_id not in document_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = document_jobs[job_id]

    # Get current credit balance if user_id is stored
    current_balance: Optional[float] = None
    if job.get("user_id"):
        current_balance = float(check_balance(db, job["user_id"]))

    return DocumentStatusResponse(
        job_id=job_id,
        status=job["status"],
        document_type=job["document_type"],
        result=job.get("result"),
        error=job.get("error"),
        credit_balance=current_balance,
    )


@router.get("/{address:path}", response_model=PropertyDocumentsResponse)
async def get_property_documents(address: str):
    """
    Get all documents associated with a property address.
    """
    # Find all jobs for this address that completed successfully
    documents = []
    for job_id, job in document_jobs.items():
        if job["address"] == address and job["status"] == "completed":
            result = job.get("result", {})
            documents.append(PropertyDocument(
                id=job_id,
                document_type=job["document_type"],
                filename=job["filename"],
                uploaded_at=job["uploaded_at"],
                summary=result.get("reasoning"),
                score=result.get("score"),
            ))

    return PropertyDocumentsResponse(
        address=address,
        documents=documents
    )
