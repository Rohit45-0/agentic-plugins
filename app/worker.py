import asyncio
import logging
from celery import Celery
from celery.signals import worker_ready, task_failure, worker_process_init
from kombu import Queue

from app.core.config import settings

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
    broker_connection_retry_on_startup=True,
    task_queues=(
        Queue("webhook_ingest"),
        Queue("llm_reply"),
        Queue("media"),
    ),
    task_routes={
        "process_whatsapp_webhook": {"queue": "webhook_ingest"},
        "process_whatsapp_message": {"queue": "llm_reply"},
    },
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
    Fan out a webhook batch into specialized message queues.
    """
    try:
        from app.api.whatsapp import _iter_payload_message_events, _select_processing_queue

        dispatch_count = 0
        for event in _iter_payload_message_events(payload):
            msg = event.get("msg") or {}
            queue_name = _select_processing_queue(msg)
            process_whatsapp_message.apply_async(kwargs={"event": event}, queue=queue_name)
            dispatch_count += 1
        return {"status": "dispatched", "count": dispatch_count}
    except Exception as exc:
        logger.error(f"Task failed, retrying: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="process_whatsapp_message",
    bind=True,
    max_retries=3,
    default_retry_delay=2,
)
def process_whatsapp_message(self, event: dict):
    """
    Process one inbound WhatsApp message event.
    This runs on queue-specialized workers (llm/media).
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        from app.api.whatsapp import _process_message_event

        loop.run_until_complete(_process_message_event(event))
        return {"status": "processed"}
    except Exception as exc:
        logger.error(f"Message task failed, retrying: {exc}", exc_info=True)
        raise self.retry(exc=exc)
    finally:
        loop.close()
