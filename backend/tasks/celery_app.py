"""Celery application for async task processing.

Handles AI voxel generation (L4) and long-running export tasks.
"""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "car2lego",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tasks.generation", "tasks.customization"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
