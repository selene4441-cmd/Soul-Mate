from celery import Celery

from app.config import get_settings
from app.database import SessionLocal
from app.modules.connections import expire_connection_requests
from app.modules.outbox import dispatch_pending_outbox

settings = get_settings()
celery_app = Celery("tongpin", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Shanghai",
    beat_schedule={
        "dispatch-outbox-every-5-seconds": {
            "task": "conversation.dispatch_outbox",
            "schedule": 5.0,
        },
        "expire-connection-requests-every-minute": {
            "task": "conversation.expire_connection_requests",
            "schedule": 60.0,
        },
    },
)


@celery_app.task(name="outcomes.send_due_surveys")
def send_due_surveys() -> dict[str, int]:
    return {"queued": 0}


@celery_app.task(name="conversation.dispatch_outbox")
def dispatch_outbox() -> dict[str, int]:
    with SessionLocal() as db:
        return {"processed": dispatch_pending_outbox(db, limit=200)}


@celery_app.task(name="conversation.expire_connection_requests")
def expire_requests() -> dict[str, int]:
    with SessionLocal() as db:
        return {"expired": expire_connection_requests(db, limit=200)}
