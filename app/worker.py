import asyncio
import os
from celery import Celery
from app.core.config import settings
from app.api.whatsapp import _process_payload

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
    # Fix for Windows running Celery
    task_pool="solo" if os.name == "nt" else "prefork"
)

@celery_app.task(name="process_whatsapp_webhook")
def process_whatsapp_webhook(payload: dict):
    """
    Synchronous Celery task that wraps the async _process_payload function.
    """
    # Create an event loop and run the async payload processor
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_process_payload(payload))
    finally:
        loop.close()
