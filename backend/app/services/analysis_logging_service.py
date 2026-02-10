"""
Analysis Logging Service

Provides methods for tracking analysis jobs and their individual steps.
Used to monitor success rates, latency, costs, and user-property mapping.
"""
import logging
import uuid
import re
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.database import AnalysisJob
from app.models.analysis_log import AnalysisStepLog, ANALYSIS_STEPS
from app.config import settings

logger = logging.getLogger(__name__)


def _normalize_address(address: str) -> str:
    """Normalize address for deduplication."""
    if not address:
        return ""
    # Lowercase, strip whitespace, normalize spaces
    normalized = address.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    # Remove common variations
    normalized = normalized.replace(',', '')
    normalized = normalized.replace('.', '')
    return normalized


def _apply_margin(cost: float) -> float:
    """Apply pricing margin to convert internal cost to user-facing price."""
    if settings.PRICING_MARGIN >= 1.0:
        return cost
    return cost / (1.0 - settings.PRICING_MARGIN)


class AnalysisLoggingService:
    """Service for logging analysis jobs and steps."""

    def __init__(self, db: Session):
        self.db = db

    def create_analysis_job(
        self,
        address: str,
        user_id: Optional[str] = None,
        client_ip: Optional[str] = None,
        property_id: Optional[str] = None,
    ) -> AnalysisJob:
        """
        Create a new analysis job record.

        Args:
            address: Property address being analyzed
            user_id: User ID if authenticated
            client_ip: Client IP for anonymous users
            property_id: Optional property ID if already known

        Returns:
            The created AnalysisJob
        """
        request_id = str(uuid.uuid4())

        job = AnalysisJob(
            request_id=request_id,
            address=address,
            address_normalized=_normalize_address(address),
            user_id=user_id,
            client_ip=client_ip,
            property_id=property_id,
            status='in_progress',
            started_at=datetime.utcnow(),
        )

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        logger.info(f"Created analysis job {job.id} for address: {address}")
        return job

    def start_step(
        self,
        job_id: str,
        step_number: int,
        step_name: str,
        step_type: str,
    ) -> AnalysisStepLog:
        """
        Start tracking a step in the analysis.

        Args:
            job_id: The analysis job ID
            step_number: Step number (1-10)
            step_name: Human-readable step name
            step_type: 'system', 'extraction', or 'analysis'

        Returns:
            The created AnalysisStepLog
        """
        step_log = AnalysisStepLog(
            analysis_job_id=job_id,
            step_number=step_number,
            step_name=step_name,
            step_type=step_type,
            status='in_progress',
            started_at=datetime.utcnow(),
        )

        self.db.add(step_log)
        self.db.commit()
        self.db.refresh(step_log)

        # Update job's current step
        job = self.db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.current_step = step_name
            job.progress = int((step_number / 10) * 100)
            self.db.commit()

        logger.debug(f"Started step {step_number} ({step_name}) for job {job_id}")
        return step_log

    def complete_step(
        self,
        step_log_id: str,
        cost: float = 0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark a step as completed.

        Args:
            step_log_id: The step log ID
            cost: LLM cost for this step
            input_tokens: Input token count
            output_tokens: Output token count
            model: LLM model used
            metadata: Additional metadata
        """
        step_log = self.db.query(AnalysisStepLog).filter(
            AnalysisStepLog.id == step_log_id
        ).first()

        if not step_log:
            logger.warning(f"Step log {step_log_id} not found")
            return

        now = datetime.utcnow()
        step_log.status = 'completed'
        step_log.completed_at = now
        step_log.cost = Decimal(str(cost))
        step_log.input_tokens = input_tokens
        step_log.output_tokens = output_tokens
        step_log.model = model
        step_log.step_metadata = metadata

        if step_log.started_at:
            step_log.duration_ms = int((now - step_log.started_at).total_seconds() * 1000)

        self.db.commit()
        logger.debug(f"Completed step {step_log.step_name} (cost: ${cost:.6f})")

    def skip_step(self, step_log_id: str, reason: Optional[str] = None) -> None:
        """Mark a step as skipped."""
        step_log = self.db.query(AnalysisStepLog).filter(
            AnalysisStepLog.id == step_log_id
        ).first()

        if not step_log:
            return

        step_log.status = 'skipped'
        step_log.completed_at = datetime.utcnow()
        if step_log.started_at:
            step_log.duration_ms = int(
                (step_log.completed_at - step_log.started_at).total_seconds() * 1000
            )
        if reason:
            step_log.step_metadata = {"skip_reason": reason}

        self.db.commit()

    def fail_step(
        self,
        step_log_id: str,
        error_message: str,
    ) -> None:
        """
        Mark a step as failed.

        Args:
            step_log_id: The step log ID
            error_message: Error message
        """
        step_log = self.db.query(AnalysisStepLog).filter(
            AnalysisStepLog.id == step_log_id
        ).first()

        if not step_log:
            logger.warning(f"Step log {step_log_id} not found")
            return

        now = datetime.utcnow()
        step_log.status = 'failed'
        step_log.completed_at = now
        step_log.error_message = error_message

        if step_log.started_at:
            step_log.duration_ms = int((now - step_log.started_at).total_seconds() * 1000)

        self.db.commit()
        logger.warning(f"Step {step_log.step_name} failed: {error_message}")

    def complete_job(
        self,
        job_id: str,
        is_cached: bool = False,
    ) -> None:
        """
        Mark an analysis job as completed.

        Calculates total cost and duration from step logs.

        Args:
            job_id: The analysis job ID
            is_cached: Whether the result was served from cache
        """
        job = self.db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found")
            return

        now = datetime.utcnow()
        job.status = 'completed'
        job.completed_at = now
        job.is_cached = is_cached
        job.progress = 100

        # Calculate totals from step logs
        step_logs = self.db.query(AnalysisStepLog).filter(
            AnalysisStepLog.analysis_job_id == job_id
        ).all()

        total_cost = sum(float(s.cost or 0) for s in step_logs)
        job.total_cost = Decimal(str(total_cost))
        job.total_cost_user = Decimal(str(_apply_margin(total_cost)))

        if job.started_at:
            job.total_duration_ms = int((now - job.started_at).total_seconds() * 1000)

        self.db.commit()
        logger.info(
            f"Completed job {job_id}: cached={is_cached}, "
            f"cost=${total_cost:.4f}, duration={job.total_duration_ms}ms"
        )

    def fail_job(
        self,
        job_id: str,
        error_message: str,
        error_step: Optional[str] = None,
    ) -> None:
        """
        Mark an analysis job as failed.

        Args:
            job_id: The analysis job ID
            error_message: Error message
            error_step: Which step failed
        """
        job = self.db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            logger.warning(f"Job {job_id} not found")
            return

        now = datetime.utcnow()
        job.status = 'failed'
        job.completed_at = now
        job.error_message = error_message
        job.error_step = error_step

        if job.started_at:
            job.total_duration_ms = int((now - job.started_at).total_seconds() * 1000)

        # Calculate costs up to failure
        step_logs = self.db.query(AnalysisStepLog).filter(
            AnalysisStepLog.analysis_job_id == job_id
        ).all()

        total_cost = sum(float(s.cost or 0) for s in step_logs)
        job.total_cost = Decimal(str(total_cost))
        job.total_cost_user = Decimal(str(_apply_margin(total_cost)))

        self.db.commit()
        logger.error(f"Failed job {job_id} at step {error_step}: {error_message}")

    def get_step_definition(self, step_number: int) -> Optional[Dict[str, Any]]:
        """Get step definition by number."""
        for step in ANALYSIS_STEPS:
            if step["number"] == step_number:
                return step
        return None


# Convenience function for creating service
def get_analysis_logging_service(db: Session) -> AnalysisLoggingService:
    """Create an AnalysisLoggingService instance."""
    return AnalysisLoggingService(db)
