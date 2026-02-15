"""
Celery application configuration
"""
from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Create Celery app
celery_app = Celery(
    "housing_analysis",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.analysis_tasks",
        "app.tasks.data_collection_tasks",
        "app.tasks.email_tasks",
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # 50 minutes soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks
)

# Periodic tasks schedule (Celery Beat)
celery_app.conf.beat_schedule = {
    'cleanup-old-notes-monthly': {
        'task': 'cleanup_old_notes_files',
        'schedule': crontab(day_of_month='1', hour='2', minute='0'),  # 1st of each month at 2:00 AM
        'args': (30,),  # Delete files older than 30 days
        'options': {
            'expires': 3600,  # Task expires if not run within 1 hour
        }
    },
    'send-weekly-digest-sunday': {
        'task': 'send_weekly_digest_emails',
        'schedule': crontab(day_of_week='sunday', hour='9', minute='0'),  # Every Sunday at 9:00 AM UTC
        'options': {
            'expires': 7200,  # Task expires if not run within 2 hours
        }
    },
}

if __name__ == "__main__":
    celery_app.start()
