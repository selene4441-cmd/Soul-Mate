from celery import Celery

from app.config import get_settings

settings = get_settings()
celery_app = Celery("tongpin", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Shanghai",
)


@celery_app.task(name="outcomes.send_due_surveys")
def send_due_surveys() -> dict[str, int]:
    return {"queued": 0}
