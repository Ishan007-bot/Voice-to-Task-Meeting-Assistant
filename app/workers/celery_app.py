"""
Celery Application Configuration
Background task processing for audio transcription and task extraction.
"""

from celery import Celery

from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "voice_to_task",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task result settings
    result_expires=3600,  # 1 hour
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # 50 minutes soft limit
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time for heavy processing
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (memory management)
    
    # Retry settings
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    
    # Queue settings
    task_default_queue="default",
    task_queues={
        "default": {},
        "transcription": {"x-max-priority": 10},
        "extraction": {"x-max-priority": 5},
        "sync": {"x-max-priority": 3},
    },
    
    # Rate limiting (prevent overwhelming external APIs)
    task_annotations={
        "app.workers.tasks.sync_task_to_external": {
            "rate_limit": "10/m",  # 10 per minute
        },
    },
)

# Optional: Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    # Retry failed syncs every 15 minutes
    "retry-failed-syncs": {
        "task": "app.workers.tasks.retry_failed_syncs",
        "schedule": 900.0,  # 15 minutes
    },
    # Cleanup old audio files daily
    "cleanup-old-files": {
        "task": "app.workers.tasks.cleanup_old_files",
        "schedule": 86400.0,  # 24 hours
    },
}
