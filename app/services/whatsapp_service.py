"""
WhatsApp Service — Handles all communication with the Meta WhatsApp Cloud API.
Sending messages, downloading media attachments, etc.
"""
import httpx
import structlog
from typing import Optional
from app.core.config import settings

logger = structlog.get_logger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


async def send_text_message(to_number: str, message: str, phone_number_id: Optional[str] = None) -> dict:
    """
    Send a plain text WhatsApp message to a phone number via Meta Cloud API.
    """
    resolved_phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    if not resolved_phone_number_id:
        raise ValueError("WHATSAPP_PHONE_NUMBER_ID is not configured")

    url = f"{GRAPH_API_BASE}/{resolved_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"preview_url": False, "body": message},
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.is_success:
        logger.info(f"✅ WhatsApp message sent to {to_number}")
    else:
        logger.error(f"❌ Failed to send WhatsApp message: {response.status_code} - {response.text}")

    try:
        return response.json()
    except Exception:
        return {"status_code": response.status_code, "body": response.text}


async def download_media(media_id: str) -> bytes:
    """
    Download a media file (image, document, audio) from Meta's servers.
    Step 1: Get the download URL from the media_id.
    Step 2: Download the actual binary content.
    """
    headers = {"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}

    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Get media URL
        meta_response = await client.get(f"{GRAPH_API_BASE}/{media_id}", headers=headers)
        meta_response.raise_for_status()
        media_url = meta_response.json().get("url")

        if not media_url:
            raise ValueError(f"Could not resolve media URL for media_id: {media_id}")

        # Step 2: Download actual file bytes
        file_response = await client.get(media_url, headers=headers)
        file_response.raise_for_status()
        return file_response.content


async def mark_as_read(message_id: str, phone_number_id: Optional[str] = None) -> None:
    """Mark a message as 'read' (blue ticks) on WhatsApp."""
    resolved_phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
    if not resolved_phone_number_id or not message_id:
        return

    url = f"{GRAPH_API_BASE}/{resolved_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, headers=headers, json=payload)
        if not response.is_success:
            logger.warning("Failed to mark WhatsApp message as read", status_code=response.status_code, response=response.text)
