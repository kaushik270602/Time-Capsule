"""
Celery application configuration for TimeLock.

Configures Celery with Redis broker, periodic task scheduling, and retry policies.
"""

from celery import Celery
from celery.schedules import crontab
from app.config import settings

# Create Celery app
celery_app = Celery(
    "timelock",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.unlock_scheduler"]
)

# Celery configuration
celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Retry policy defaults
    task_acks_late=True,  # Acknowledge tasks after execution
    task_reject_on_worker_lost=True,  # Requeue tasks if worker dies
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Fetch one task at a time for fairness
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks
    
    # Periodic task schedule
    beat_schedule={
        "check-and-unlock-capsules": {
            "task": "app.tasks.unlock_scheduler.check_and_unlock_capsules",
            "schedule": 60.0,  # Run every 60 seconds (1 minute)
            "options": {
                "expires": 55,  # Task expires after 55 seconds to avoid overlap
            }
        },
    },
    
    # Task routing
    task_routes={
        "app.tasks.unlock_scheduler.*": {"queue": "unlock"},
        "app.tasks.notifications.*": {"queue": "notifications"},
        "app.tasks.ai_analysis.*": {"queue": "ai"},
    },
    
    # Retry policy for tasks
    task_default_retry_delay=60,  # Wait 60 seconds before retry
    task_max_retries=3,  # Maximum 3 retry attempts
)

# Task annotations for specific retry policies
celery_app.conf.task_annotations = {
    "app.tasks.unlock_scheduler.unlock_capsule": {
        "rate_limit": "10/s",  # Max 10 unlocks per second
        "time_limit": 300,  # 5 minute hard time limit
        "soft_time_limit": 240,  # 4 minute soft time limit
    },
    "app.tasks.notifications.send_unlock_notification": {
        "rate_limit": "50/s",
        "time_limit": 60,
        "soft_time_limit": 50,
    },
    "app.tasks.ai_analysis.analyze_capsule_task": {
        "rate_limit": "5/s",  # AI API rate limiting
        "time_limit": 600,  # 10 minute hard time limit
        "soft_time_limit": 540,  # 9 minute soft time limit
    },
}
