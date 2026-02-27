from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("hb_bot", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = settings.timezone
celery_app.conf.enable_utc = True
celery_app.conf.beat_schedule = {
    "process-periodic-workflow": {
        "task": "app.jobs.tasks.process_periodic_workflow",
        "schedule": 60.0,
    }
}

celery_app.autodiscover_tasks(["app.jobs"])
