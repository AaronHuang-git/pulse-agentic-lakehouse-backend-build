"""Celery application for the ingest service."""
from __future__ import annotations

from celery import Celery

from shared.config import get_settings

settings = get_settings()

# Both broker and result backend point at the shared Redis. We won't rely on
# the result backend for our own status tracking (Postgres `jobs` is the
# source of truth) but Celery requires one to be configured.
celery_app = Celery(
    "pulse_ingest",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=["services.ingest.app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,             # ack only after task finishes (safer on crash)
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=200,  # recycle worker process after N tasks
    result_expires=3600,             # results auto-expire from Redis after 1h
    timezone="UTC",
    enable_utc=True,
)
