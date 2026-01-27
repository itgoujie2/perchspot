"""
Celery tasks for property analysis
"""
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from celery import Task
from app.tasks.celery_app import celery_app
from app.services.agent.analysis_orchestrator import AnalysisOrchestrator
from app.services.reporting.pdf_generator import PDFReportGenerator
from app.services.agent.tools.notes_manager import get_notes_manager
from app.config import settings

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """
    Base task with callbacks for progress tracking
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails"""
        logger.error(f"Task {task_id} failed: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds"""
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(base=CallbackTask, bind=True, name="analyze_property")
def analyze_property_task(self, analysis_id: str, address: str):
    """
    Main task for property analysis

    This task orchestrates the entire analysis pipeline:
    1. Collect data from multiple sources
    2. Download and process images
    3. Run LLM analyses
    4. Calculate scores
    5. Generate report

    Args:
        self: Task instance (bound)
        analysis_id: Analysis job ID
        address: Property address

    Returns:
        Analysis result dictionary
    """
    logger.info(f"Starting analysis {analysis_id} for: {address}")

    try:
        # Update job status to 'processing'
        self.update_state(
            state='PROGRESS',
            meta={'current': 10, 'total': 100, 'status': 'Initializing analysis...'}
        )

        # Create orchestrator
        orchestrator = AnalysisOrchestrator()

        # Run async analysis in sync context
        async def run_analysis():
            return await orchestrator.analyze_property(address)

        # Execute async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            analysis_result = loop.run_until_complete(run_analysis())
        finally:
            loop.close()

        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 90, 'total': 100, 'status': 'Generating PDF report...'}
        )

        # Generate PDF report
        pdf_generator = PDFReportGenerator()
        pdf_bytes = pdf_generator.generate_report(analysis_result)

        # Store PDF (TODO: save to S3/MinIO)
        analysis_result['pdf_size'] = len(pdf_bytes)

        self.update_state(
            state='PROGRESS',
            meta={'current': 100, 'total': 100, 'status': 'Complete!'}
        )

        logger.info(
            f"Analysis complete: {analysis_id}, "
            f"score={analysis_result.get('overall_score')}, "
            f"cost=${analysis_result.get('total_llm_cost')}"
        )

        return {
            'status': 'completed',
            'analysis_id': analysis_id,
            'result': analysis_result,
            'pdf_generated': True
        }

    except Exception as e:
        logger.error(f"Error analyzing property {analysis_id}: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={'status': 'Failed', 'error': str(e)}
        )
        raise


@celery_app.task(name="cleanup_old_notes_files")
def cleanup_old_notes_files(age_days: int = 30):
    """
    Periodic task to clean up old analysis notes files.

    This task runs monthly to remove notes files older than the specified age.
    In production, notes are uploaded to S3 immediately after analysis, so local
    files are kept as backup. This task cleans up old backups to save disk space.

    Args:
        age_days: Delete files older than this many days (default: 30)

    Returns:
        Dictionary with cleanup statistics
    """
    logger.info(f"Starting cleanup of notes files older than {age_days} days")

    try:
        # Get notes manager
        notes_manager = get_notes_manager()
        notes_dir = notes_manager.notes_dir

        if not notes_dir.exists():
            logger.warning(f"Notes directory does not exist: {notes_dir}")
            return {'status': 'skipped', 'reason': 'directory_not_found'}

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=age_days)
        logger.info(f"Cutoff date: {cutoff_date.isoformat()}")

        # Find old files
        deleted_count = 0
        total_size_freed = 0
        errors = []

        for notes_file in notes_dir.glob("*.md"):
            try:
                # Get file modification time
                file_mtime = datetime.fromtimestamp(notes_file.stat().st_mtime)

                # Check if file is older than cutoff
                if file_mtime < cutoff_date:
                    file_size = notes_file.stat().st_size
                    logger.info(f"Deleting old notes file: {notes_file.name} (modified: {file_mtime.isoformat()})")

                    # Delete file
                    notes_file.unlink()

                    deleted_count += 1
                    total_size_freed += file_size

            except Exception as e:
                error_msg = f"Error deleting {notes_file.name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        # Log summary
        logger.info(
            f"Cleanup complete: deleted {deleted_count} files, "
            f"freed {total_size_freed / 1024 / 1024:.2f} MB"
        )

        return {
            'status': 'completed',
            'deleted_count': deleted_count,
            'total_size_freed_mb': round(total_size_freed / 1024 / 1024, 2),
            'cutoff_date': cutoff_date.isoformat(),
            'errors': errors
        }

    except Exception as e:
        logger.error(f"Error during notes cleanup: {e}", exc_info=True)
        return {
            'status': 'failed',
            'error': str(e)
        }
