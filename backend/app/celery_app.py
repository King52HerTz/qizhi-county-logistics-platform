from celery import Celery

from app.config import get_settings


settings = get_settings()
celery_app = Celery("qizhi", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    timezone="Asia/Shanghai",
)
celery_app.autodiscover_tasks(["app"])
