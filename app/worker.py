import asyncio
import logging
from celery import Celery
from celery.signals import worker_ready, task_failure, worker_process_init

from app.core.config import settings
from app.api.whatsapp import _process_payload

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery("whatsapp_worker")

# Configure Celery
celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Use solo pool everywhere — prefork causes ValueError crash in
    # fast_trace_task on Railway (fork + re-import race condition).
    # Since we use --concurrency=1, solo is simpler and more reliable.
    worker_pool="solo",
    # Retry config — worker retries 3 times before giving up
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)


@worker_process_init.connect
def on_worker_process_init(**kwargs):
    from app.db.base import engine
    engine.sync_engine.dispose()
    logger.info("[OK] Reinitialized SQLAlchemy engine for the worker process")


@worker_ready.connect
def on_worker_ready(**kwargs):
    print("✅ Celery worker is ready and listening for WhatsApp tasks!")


@task_failure.connect
def on_task_failure(task_id, exception, traceback, **kwargs):
    print(f"❌ Task {task_id} failed: {exception}")


@celery_app.task(
    name="process_whatsapp_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def process_whatsapp_webhook(self, payload: dict):
    """
    Synchronous Celery task that wraps the async _process_payload function.
    Retries up to 3 times on failure.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process_payload(payload))
    except Exception as exc:
        logger.error(f"Task failed, retrying: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        loop.close()
