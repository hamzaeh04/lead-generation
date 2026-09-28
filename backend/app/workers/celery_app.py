from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "lead_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.example_task", "app.tasks.campaign_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "process-due-campaign-sends": {
        "task": "app.tasks.process_due_campaign_sends",
        "schedule": 60.0,  # every minute — supports 5-minute paced campaigns
    },
}
