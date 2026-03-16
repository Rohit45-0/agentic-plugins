"""
WhatsApp Webhook + Inbox APIs.

Implements:
1) Meta webhook verification and inbound processing
2) Conversation/message persistence for dashboard inbox
3) Escalation management APIs (A+B model)
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import redis.asyncio as redis
import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.base import AsyncSessionLocal, get_db
from app.db.models import (
    User,
    WhatsAppBotConfig,
    WhatsAppConversation,
    WhatsAppEscalation,
    WhatsAppMessage,
    WhatsAppProcessedMessage,
)
from app.api.deps import get_current_user
from app.services import rag_service, whatsapp_service

logger = structlog.get_logger(__name__)
router = APIRouter()

# Lazy LLM client
_llm_client: Optional[AsyncOpenAI] = None
_rate_limit_redis_client: Optional[redis.Redis] = None


def _get_rate_limit_redis_client() -> redis.Redis:
    global _rate_limit_redis_client
    if _rate_limit_redis_client is None:
        redis_url = settings.REDIS_URL
        if redis_url.startswith("rediss://") and "ssl_cert_reqs" not in redis_url:
            separator = "&" if "?" in redis_url else "?"
            redis_url = f"{redis_url}{separator}ssl_cert_reqs=none"
        _rate_limit_redis_client = redis.from_url(redis_url, decode_responses=True)
    return _rate_limit_redis_client


async def _is_rate_limited(identifier: str) -> bool:
    try:
        client = _get_rate_limit_redis_client()
        key = f"rate:whatsapp:{identifier}"
        current_count = await client.incr(key)
        if current_count == 1:
            await client.expire(key, settings.RATE_LIMIT_WINDOW_SECONDS)
        return current_count > settings.RATE_LIMIT_MAX_MESSAGES
    except Exception as exc:
        logger.warning("Redis rate-limit check failed; allowing request", error=str(exc))
        return False


class ManualModeUpdate(BaseModel):
    manual_mode: bool


class EscalationResolveRequest(BaseModel):
    notes: Optional[str] = None


class ManualReplyRequest(BaseModel):
    message: str


class BotConfigUpsertRequest(BaseModel):
    user_id: UUID
    phone_number_id: str
    owner_phone_number: Optional[str] = None
    whatsapp_phone_number: Optional[str] = None
    business_display_name: Optional[str] = None
    google_sheet_id: Optional[str] = None
    use_case_type: str = "restaurant"
    is_active: bool = True


class SystemAlertRequest(BaseModel):
    user_id: str
    phone_number: str
    phone_number_id: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    message: Optional[str] = None


class ToolPreferencesRequest(BaseModel):
    """Payload from the Settings UI to save tool toggle preferences."""
    enabled_tools: dict  # {"get_menu": true, "check_weather_and_suggest": false, ...}


def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
        )
    return _llm_client


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _verify_meta_signature(raw_body: bytes, signature_header: Optional[str]) -> None:
    """Verify X-Hub-Signature-256 when app secret is configured."""
    if not settings.WHATSAPP_APP_SECRET:
        return

    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Missing or invalid webhook signature")

    expected = "sha256=" + hmac.new(
        settings.WHATSAPP_APP_SECRET.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=403, detail="Webhook signature mismatch")


def _verify_internal_webhook_secret(secret_header: Optional[str]) -> None:
    if not settings.INTERNAL_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Internal webhook secret is not configured")
    if not secret_header:
        raise HTTPException(status_code=403, detail="Missing internal webhook secret")
    if not hmac.compare_digest(settings.INTERNAL_WEBHOOK_SECRET, secret_header):
        raise HTTPException(status_code=403, detail="Invalid internal webhook secret")


def _iter_payload_message_events(payload: dict):
    """Yield normalized message events from a Meta webhook payload."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            metadata = value.get("metadata", {})
            phone_number_id = metadata.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID
            for msg in value.get("messages", []) or []:
                yield {
                    "phone_number_id": phone_number_id,
                    "msg": msg,
                }


def _select_processing_queue(msg: dict) -> str:
    """Route message handling to specialized queues by message type."""
    msg_type = (msg or {}).get("type", "")
    if msg_type in {"document", "image", "audio", "video", "sticker"}:
        return "media"
    if msg_type in {"text", "interactive", "button"}:
        return "llm_reply"
    return "webhook_ingest"


async def _process_message_event(event: dict) -> None:
    """Process exactly one inbound WhatsApp message event."""
    phone_number_id = event.get("phone_number_id")
    msg = event.get("msg") or {}

    if not isinstance(msg, dict):
        logger.warning("Skipping malformed message event payload")
        return

    async with AsyncSessionLocal() as db:
        from_number = msg.get("from", "")
        owner, config, owner_phone_number = await _resolve_owner_context(
            db, phone_number_id, from_number=from_number
        )
        if owner is None:
            logger.warning("No owner found for incoming message", from_number=from_number)
            return

        await _process_single_message(
            db=db,
            owner=owner,
            config=config,
            msg=msg,
            owner_phone_number=owner_phone_number,
            phone_number_id=phone_number_id,
        )


def _extract_text_from_message(msg: dict) -> str:
    msg_type = msg.get("type", "")
    if msg_type == "text":
        return msg.get("text", {}).get("body", "").strip()
    if msg_type == "document":
        return msg.get("document", {}).get("filename", "[document]")
    if msg_type == "image":
        return "[image]"
    if msg_type == "audio":
        return "[audio]"
    return ""


def _normalize_phone(phone: Optional[str]) -> str:
    """Strip leading + and country code 91 to get the bare 10-digit number for comparison."""
    if not phone:
        return ""
    p = phone.strip().replace("+", "").replace(" ", "").replace("-", "")
    # If it starts with 91 and is 12 digits, strip the country code
    if p.startswith("91") and len(p) == 12:
        return p[2:]
    return p


def _is_owner_message(from_number: str, owner_phone_number: Optional[str]) -> bool:
    if not owner_phone_number or not from_number:
        return False
    return _normalize_phone(from_number) == _normalize_phone(owner_phone_number)


def _escalation_keywords() -> set[str]:
    return {
        token.strip().lower()
        for token in settings.ESCALATION_KEYWORDS.split(",")
        if token and token.strip()
    }


def _should_escalate(question: str, rag_chunks_found: int, bot_reply: str) -> tuple[bool, Optional[str], str]:
    normalized = question.lower()

    for keyword in _escalation_keywords():
        if keyword in normalized:
            return True, "customer_requested_human", "high"

    if rag_chunks_found == 0:
        return True, "low_confidence_no_context", "medium"

    if "don't have that information" in bot_reply.lower() or "do not have that information" in bot_reply.lower():
        return True, "low_confidence_fallback", "medium"

    return False, None, "low"


async def _resolve_owner_context(
    db: AsyncSession, phone_number_id: Optional[str], from_number: Optional[str] = None
) -> tuple[Optional[User], Optional[WhatsAppBotConfig], Optional[str]]:
    """Resolve the owner, config, and owner phone number for a webhook message.
    
    When multiple configs share the same phone_number_id (shared Meta number model),
    we match by checking if from_number is the owner of any of those configs.
    If no owner match, we pick the first active config (default).
    """
    config = None
    owner = None
    configs = []

    if phone_number_id:
        stmt = (
            select(WhatsAppBotConfig)
            .filter(
                WhatsAppBotConfig.phone_number_id == phone_number_id,
                WhatsAppBotConfig.is_active.is_(True),
            )
        )
        res = await db.execute(stmt)
        configs = res.scalars().all()

    # If we have multiple configs sharing the same phone_number_id,
    # try to match the from_number to a specific owner's phone number
    if from_number and len(configs) > 1:
        for c in configs:
            if c.owner_phone_number and _normalize_phone(from_number) == _normalize_phone(c.owner_phone_number):
                config = c
                break
    
    # If no specific match found, pick the first config (or the only one)
    if config is None and configs:
        config = configs[0]

    if config:
        res_owner = await db.execute(select(User).filter(User.id == config.user_id))
        owner = res_owner.scalar_one_or_none()

    if owner is None:
        res_first = await db.execute(select(User).limit(1))
        owner = res_first.scalar_one_or_none()

    owner_phone_number = None
    if config and config.owner_phone_number:
        owner_phone_number = config.owner_phone_number
    elif settings.OWNER_PHONE_NUMBER:
        owner_phone_number = settings.OWNER_PHONE_NUMBER

    return owner, config, owner_phone_number


async def _get_or_create_conversation(
    db: AsyncSession,
    user_id: UUID,
    customer_phone: str,
    phone_number_id: Optional[str],
) -> WhatsAppConversation:
    stmt = (
        select(WhatsAppConversation)
        .filter(
            WhatsAppConversation.user_id == user_id,
            WhatsAppConversation.customer_phone == customer_phone,
        )
    )
    res = await db.execute(stmt)
    conversation = res.scalar_one_or_none()

    if conversation:
        if phone_number_id and conversation.phone_number_id != phone_number_id:
            conversation.phone_number_id = phone_number_id
            conversation.updated_at = _utcnow()
            await db.commit()
            await db.refresh(conversation)
        return conversation

    conversation = WhatsAppConversation(
        user_id=user_id,
        phone_number_id=phone_number_id,
        customer_phone=customer_phone,
        last_message_at=_utcnow(),
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def _persist_message(
    db: AsyncSession,
    conversation: WhatsAppConversation,
    user_id: UUID,
    direction: str,
    message_type: str,
    content: str,
    status: str,
    wa_message_id: Optional[str] = None,
    is_ai_generated: bool = False,
    raw_payload: Optional[dict] = None,
) -> WhatsAppMessage:
    try:
        record = WhatsAppMessage(
            conversation_id=conversation.id,
            user_id=user_id,
            wa_message_id=wa_message_id,
            direction=direction,
            message_type=message_type,
            content=content,
            status=status,
            is_ai_generated=is_ai_generated,
            raw_payload=raw_payload,
        )
        db.add(record)

        conversation.last_message_preview = (content or "")[:300]
        conversation.last_message_at = _utcnow()
        conversation.updated_at = _utcnow()

        await db.commit()
        await db.refresh(record)
        await db.refresh(conversation)
        return record
    except IntegrityError:
        await db.rollback()
        if wa_message_id:
            stmt = select(WhatsAppMessage).filter(WhatsAppMessage.wa_message_id == wa_message_id)
            res = await db.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing
        raise


async def _create_escalation(
    db: AsyncSession,
    conversation: WhatsAppConversation,
    user_id: UUID,
    reason: str,
    severity: str = "medium",
    notes: Optional[str] = None,
    trigger_message_id: Optional[UUID] = None,
) -> WhatsAppEscalation:
    stmt = (
        select(WhatsAppEscalation)
        .filter(
            WhatsAppEscalation.conversation_id == conversation.id,
            WhatsAppEscalation.status == "open",
            WhatsAppEscalation.reason == reason,
        )
    )
    res = await db.execute(stmt)
    open_existing = res.scalar_one_or_none()
    if open_existing:
        return open_existing

    escalation = WhatsAppEscalation(
        conversation_id=conversation.id,
        user_id=user_id,
        trigger_message_id=trigger_message_id,
        reason=reason,
        severity=severity,
        status="open",
        notes=notes,
    )
    db.add(escalation)
    await db.commit()
    await db.refresh(escalation)
    return escalation


async def _is_duplicate_message(db: AsyncSession, wa_message_id: str) -> bool:
    if not wa_message_id:
        return False
        
    res = await db.execute(select(WhatsAppProcessedMessage).filter(WhatsAppProcessedMessage.wa_message_id == wa_message_id))
    return res.scalar_one_or_none() is not None


async def _mark_processed(db: AsyncSession, wa_message_id: str, user_id: Optional[UUID]) -> None:
    if not wa_message_id:
        return
    try:
        rec = WhatsAppProcessedMessage(wa_message_id=wa_message_id, user_id=user_id)
        db.add(rec)
        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning("Processed message marker already exists or failed", wa_message_id=wa_message_id)


async def _send_and_persist(
    db: AsyncSession,
    conversation: WhatsAppConversation,
    user_id: UUID,
    to_number: str,
    text: str,
    phone_number_id: Optional[str],
    is_ai_generated: bool,
) -> dict:
    response = await whatsapp_service.send_text_message(
        to_number=to_number,
        message=text,
        phone_number_id=phone_number_id,
    )
    outbound_wa_id = (
        (response.get("messages") or [{}])[0].get("id")
        if isinstance(response, dict)
        else None
    )
    await _persist_message(
        db=db,
        conversation=conversation,
        user_id=user_id,
        direction="outbound",
        message_type="text",
        content=text,
        status="sent",
        wa_message_id=outbound_wa_id,
        is_ai_generated=is_ai_generated,
        raw_payload=response if isinstance(response, dict) else None,
    )
    return response


# ─── Webhook Verification (Meta handshake) ───────────────────────────────────


@router.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Meta sends a GET here once to verify we own the webhook URL."""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("[OK] Meta WhatsApp Webhook verified!")
        return int(hub_challenge)

    logger.warning("[FAIL] Webhook verification failed: token mismatch")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/webhook")
async def handle_incoming(request: Request):
    """Main listener. Meta POSTs here every time someone messages the bot."""
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    _verify_meta_signature(raw_body, signature)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if settings.WEBHOOK_USE_CELERY:
        try:
            from app.worker import process_whatsapp_webhook
            process_whatsapp_webhook.apply_async(kwargs={"payload": payload}, queue="webhook_ingest")
        except Exception as exc:
            logger.error("Failed to enqueue WhatsApp payload in Celery", error=str(exc), exc_info=True)
            raise HTTPException(status_code=503, detail="Webhook queue unavailable")
        return {"status": "queued"}

    await _process_payload(payload)
    return {"status": "ok"}


async def _process_payload(payload: dict):
    """Parse Meta webhook payload and process all message events in-process."""
    try:
        for event in _iter_payload_message_events(payload):
            await _process_message_event(event)
    except Exception as e:
        logger.error(f"Error processing WhatsApp payload: {e}", exc_info=True)


async def _process_single_message(
    db: AsyncSession,
    owner: User,
    config: Optional[WhatsAppBotConfig],
    msg: dict,
    owner_phone_number: Optional[str],
    phone_number_id: Optional[str],
):
    from_number = msg.get("from", "")
    msg_type = msg.get("type", "")
    msg_id = msg.get("id", "")
    preview = _extract_text_from_message(msg)

    if not from_number or not msg_id:
        return

    # 1. Check Rate Limits (Protect OpenAI costs and DB spam)
    if await _is_rate_limited(f"customer:{from_number}"):
        logger.warning(f"Rate limit exceeded for customer phone: {from_number}")
        return

    if await _is_duplicate_message(db, msg_id):
        logger.info("Skipping duplicate webhook message", wa_message_id=msg_id)
        return

    await whatsapp_service.mark_as_read(msg_id, phone_number_id=phone_number_id)

    conversation = await _get_or_create_conversation(
        db=db,
        user_id=owner.id,
        customer_phone=from_number,
        phone_number_id=phone_number_id,
    )

    inbound_record = await _persist_message(
        db=db,
        conversation=conversation,
        user_id=owner.id,
        direction="inbound",
        message_type=msg_type or "unknown",
        content=preview,
        status="received",
        wa_message_id=msg_id,
        raw_payload=msg,
    )

    processed_successfully = False
    try:
        if _is_owner_message(from_number, owner_phone_number):
            await _handle_owner_message(db, owner, config, conversation, msg, msg_type, from_number, phone_number_id)
        else:
            if conversation.manual_mode:
                await _send_and_persist(
                    db=db,
                    conversation=conversation,
                    user_id=owner.id,
                    to_number=from_number,
                    text="Thanks for your message. A human teammate will reply shortly 🙏",
                    phone_number_id=phone_number_id,
                    is_ai_generated=False,
                )
                await _create_escalation(
                    db=db,
                    conversation=conversation,
                    user_id=owner.id,
                    reason="manual_mode_active",
                    severity="high",
                    trigger_message_id=inbound_record.id,
                    notes="Conversation is in manual mode; bot auto-reply skipped.",
                )
            else:
                await _handle_customer_message(
                    db,
                    owner,
                    config,
                    conversation,
                    inbound_record,
                    msg,
                    msg_type,
                    from_number,
                    phone_number_id,
                    owner_phone_number,
                )
        processed_successfully = True
    finally:
        if processed_successfully:
            await _mark_processed(db, msg_id, owner.id)


async def _handle_owner_message(
    db: AsyncSession,
    owner: User,
    config: Optional[WhatsAppBotConfig],
    conversation: WhatsAppConversation,
    msg: dict,
    msg_type: str,
    from_number: str,
    phone_number_id: Optional[str],
):
    """
    Owner texts bot to train it.
    - Text messages → ingest as knowledge.
    - Documents → download, extract text, ingest.
    """
    if msg_type == "text":
        text_body = msg.get("text", {}).get("body", "").strip()
        if not text_body:
            return

        use_case = config.use_case_type if config else "general"
        
        # Example intents based on use case
        if use_case == "salon":
            ex_add = "'add hair spa 500 rs' → ADD|Hair Spa - ₹500"
            ex_rm = "'remove facial' → REMOVE|Facial"
            ex_query = "'when does rohit work?' → QUERY|when does rohit work"
            ex_save = "'we are open from 9am to 8pm' → SAVE|Business layout: open 9 AM to 8 PM"
        elif use_case == "tiffin":
            ex_add = "'add veg thali 100 rs' → ADD|Veg Thali - ₹100"
            ex_rm = "'remove chapati' → REMOVE|Chapati"
            ex_query = "'who skipped tiffin today?' → QUERY|who skipped tiffin today"
            ex_save = "'no delivery on sunday' → SAVE|We do not deliver on Sunday"
        else: # general / restaurant
            ex_add = "'add paneer tikka 250 rs to menu' → ADD|Paneer Tikka - ₹250"
            ex_rm = "'remove dosa from menu' → REMOVE|Dosa"
            ex_query = "'what items do we have?' → QUERY|what items do we have"
            ex_save = "'we are open 9am to 10pm' → SAVE|Business hours: 9 AM to 10 PM"
            
        ex_cancel = "'cancel booking for 9876543210 on 2026-03-02' → CANCEL|<phone_number>|<YYYY-MM-DD>"
        ex_cancel_all = "'cancel all bookings for today' → CANCEL|ALL|<YYYY-MM-DD>"
        ex_gen = "'create a video for paneer tikka' → GENERATE|<type>|<prompt>"

        # Use AI to understand owner intent
        client = _get_llm_client()
        today_str = datetime.today().strftime('%Y-%m-%d')
        
        try:
            intent_resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{
                    "role": "system",
                    "content": (
                        "You classify business owner messages into intents. "
                        "Reply with ONLY one of these formats:\n"
                        f"ADD|<clean item/info to add> - when owner wants to add something (e.g. {ex_add})\n"
                        f"REMOVE|<item to remove> - when owner wants to remove/delete something (e.g. {ex_rm})\n"
                        f"QUERY|<question> - when owner is asking a question (e.g. {ex_query})\n"
                        f"SAVE|<info> - when owner shares business info/facts to remember (e.g. {ex_save})\n"
                        f"CANCEL|<phone_number>|<date> - when owner wants to completely cancel a specific customer's booking. (e.g. {ex_cancel})\n"
                        f"CANCEL|ALL|<date> - when owner wants to cancel ALL schedule/appointments for a day. (e.g. {ex_cancel_all})\n"
                        f"GENERATE|<type>|<prompt> - when owner wants to create marketing content like video, poster, or blog. <type> must be exactly: video, poster, or blog. (e.g. {ex_gen})\n"
                        f"GREET|hello - ONLY if the owner just says hi or hello and NOTHING else.\n"
                        "Always clean up and format the content nicely. Support Hindi/Marathi/Hinglish.\n"
                        f"CRITICAL: The current date is {today_str}. If the user refers to 'today', 'tomorrow', or implies a date, map it to the actual YYYY-MM-DD date based on the current date: {today_str}."
                    )
                }, {
                    "role": "user",
                    "content": text_body
                }],
                max_tokens=200,
                temperature=0.1,
            )
            intent_raw = (intent_resp.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            intent_raw = f"SAVE|{text_body}"

        # Parse intent
        intent_type = "SAVE"
        intent_content = text_body
        extra_content = ""
        
        if "|" in intent_raw:
            parts = intent_raw.split("|")
            intent_type = parts[0].strip().upper()
            
            if intent_type in ("CANCEL", "GENERATE") and len(parts) >= 3:
                # Format: CANCEL|<phone>|<date> or GENERATE|<type>|<prompt>
                intent_content = parts[1].strip()
                extra_content = parts[2].strip()
            elif len(parts) >= 2:
                # Format: TYPE|<content>
                intent_content = parts[1].strip()
            else:
                intent_content = intent_raw
        else:
            intent_content = intent_raw

        # Hardcoded overrides to forcefully bypass AI if it hallucinated or got confused by a greeting
        text_lower = text_body.lower()
        if "make a poster" in text_lower or "create a poster" in text_lower or "poster for" in text_lower:
            intent_type = "GENERATE"
            intent_content = "poster"
            extra_content = text_body
        elif "make a video" in text_lower or "create a video" in text_lower or "video for" in text_lower:
            intent_type = "GENERATE"
            intent_content = "video"
            extra_content = text_body
        elif "write a blog" in text_lower or "create a blog" in text_lower or "blog post for" in text_lower:
            intent_type = "GENERATE"
            intent_content = "blog"
            extra_content = text_body
        elif "research" in text_lower or "market research" in text_lower or "analyze market" in text_lower:
            intent_type = "RESEARCH"
            # Extract product name heuristically
            p_name = text_lower.replace("do market research for", "").replace("market research for", "").replace("market research", "").replace("research", "").replace("analyze market for", "").strip()
            if not p_name:
                p_name = config.use_case_type if config else text_body
            intent_content = p_name
            extra_content = text_body


        # Handle each intent
        if intent_type == "GREET":
            msg_reply = f"👋 Hello Boss! I'm your active {use_case} AI assistant.\n\nJust text me your prices, rules, or menu items right here and I'll memorize them for your customers! Try saying:\n'Haircut is 250 Rs'"
            if use_case == "restaurant" or use_case == "tiffin":
                msg_reply = f"👋 Hello Boss! I'm your active {use_case} AI assistant.\n\nJust text me your menu items or rules right here and I'll memorize them for your customers! Try saying:\n'Veg Thali is 100 Rs'"

        elif intent_type == "ADD":
            count, err = await rag_service.ingest_text(db, intent_content, owner.id)
            if count > 0:
                msg_reply = f"✅ Added to knowledge base:\n\n📝 \"{intent_content}\"\n\nCustomers can now ask about this!"
            else:
                msg_reply = f"❌ Couldn't add. {err or 'Unknown error'}"

        elif intent_type == "REMOVE":
            # Search for matching chunks and delete them
            from app.db.models import KnowledgeChunk
            search_term = intent_content.lower()
            stmt = select(KnowledgeChunk).filter(
                KnowledgeChunk.user_id == owner.id,
                KnowledgeChunk.content.ilike(f"%{search_term}%"),
            )
            res = await db.execute(stmt)
            matching = res.scalars().all()
            if matching:
                for chunk in matching:
                    await db.delete(chunk)
                await db.commit()
                msg_reply = f"🗑️ Removed {len(matching)} item(s) matching \"{intent_content}\" from knowledge base."
            else:
                msg_reply = f"⚠️ Couldn't find anything matching \"{intent_content}\" in the knowledge base."

        elif intent_type == "QUERY":
            chunks = await rag_service.search_knowledge(db, intent_content, owner.id, limit=5)
            context = "\n".join([f"- {c.content}" for c in chunks]) if chunks else "No info found."
            try:
                answer_resp = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": f"You are a business assistant. Answer the owner's question using this knowledge:\n{context}"},
                        {"role": "user", "content": intent_content},
                    ],
                    max_tokens=500,
                    temperature=0.3,
                )
                msg_reply = (answer_resp.choices[0].message.content or "").strip()
            except Exception as e:
                msg_reply = f"❌ Error answering: {e}"

        elif intent_type == "CANCEL":
            customer_phone_provided = intent_content
            target_date_str = extra_content
            
            from app.services.slot_engine import cancel_calendar_events
            try:
                if not config or not hasattr(config, "id") or not config.id:
                    msg_reply = "❌ You must configure and connect your Google Calendar to cancel bookings."
                else:
                    cancelled_count = await cancel_calendar_events(
                        db=db, 
                        bot_config_id=str(config.id), 
                        customer_phone=customer_phone_provided, 
                        target_date_str=target_date_str
                    )
                    if cancelled_count > 0:
                        if customer_phone_provided == "ALL":
                            msg_reply = f"✅ Successfully cancelled {cancelled_count} booking(s) for EVERYONE on {target_date_str} in Google Calendar."
                        else:
                            msg_reply = f"✅ Successfully cancelled {cancelled_count} booking(s) for customer {customer_phone_provided} on {target_date_str} in Google Calendar."
                            # Notify the specific customer automatically
                            try:
                                await _send_and_persist(
                                    db=db,
                                    conversation=conversation, # Note: this conversation is the owner's. 
                                    user_id=owner.id,
                                    to_number=customer_phone_provided,
                                    text=f"⚠️ Your appointment on {target_date_str} has been cancelled by the business. Please reach out or book a new slot if needed.",
                                    phone_number_id=phone_number_id,
                                    is_ai_generated=False,
                                )
                                msg_reply += "\nThe customer has been notified via WhatsApp automatically."
                            except Exception as ne:
                                logger.error(f"Failed to notify customer of manual cancellation: {ne}")
                                msg_reply += "\n⚠️ But failed to notify the customer automatically. Please let them know."
                    else:
                        if customer_phone_provided == "ALL":
                            msg_reply = f"❌ No bookings found to cancel on '{target_date_str}'."
                        else:
                            msg_reply = f"❌ No bookings found matching customer phone '{customer_phone_provided}' on '{target_date_str}'."
            except Exception as e:
                logger.error(f"Error cancelling bookings from owner message: {e}")
                msg_reply = f"❌ Error cancelling bookings: {e}"
        elif intent_type == "GENERATE":
            gen_type = intent_content.lower() # video, poster, blog
            prompt_text = extra_content
            
            import asyncio
            import httpx
            core_url = "https://thick-dancers-scream.loca.lt/api/v1/campaigns/generate-via-bot"
            payload = {
                "user_id": str(owner.id),
                "type": gen_type,
                "prompt": prompt_text,
                "phone_number": from_number,
                "phone_number_id": phone_number_id
            }
            
            async def trigger_core():
                try:
                    headers = {"Bypass-Tunnel-Reminder": "true"}
                    async with httpx.AsyncClient(timeout=10.0) as core_client:
                        await core_client.post(core_url, json=payload, headers=headers)
                except Exception as ex:
                    logger.error(f"Core API generation trigger failed: {ex}")
                    
            asyncio.create_task(trigger_core())
            msg_reply = f"🎬 Preparing to generate your `{gen_type}` via Catalyst Nexus Core for '{prompt_text}'.\n\nThis usually takes 1-3 minutes. I'll ping you here as soon as it's ready! 🚀"

        elif intent_type == "RESEARCH":
            import asyncio
            import httpx
            core_url = "https://thick-dancers-scream.loca.lt/api/v1/market-scout/research-via-bot"
            payload = {
                "user_id": str(owner.id),
                "product_name": intent_content,
                "category": config.use_case_type if config else "general",
                "phone_number": from_number,
                "phone_number_id": phone_number_id
            }
            
            async def trigger_core_research():
                try:
                    headers = {"Bypass-Tunnel-Reminder": "true"}
                    async with httpx.AsyncClient(timeout=10.0) as core_client:
                        await core_client.post(core_url, json=payload, headers=headers)
                except Exception as ex:
                    logger.error(f"Core API research trigger failed: {ex}")
                    
            asyncio.create_task(trigger_core_research())
            msg_reply = f"🔍 Launching Catalyst Nexus AI Market Research for '{intent_content}'.\n\nI am scraping the web for competitors, trends, and content gaps right now. I'll ping you here with the final strategic report shortly! 🚀"

        else:  # SAVE
            count, err = await rag_service.ingest_text(db, intent_content, owner.id)
            if count > 0:
                msg_reply = f"✅ Got it, Boss! I saved this:\n\n📝 \"{intent_content}\"\n\nI'll use this to answer customer questions."
            elif err:
                msg_reply = f"❌ Couldn't save. Error: {err}"
            else:
                msg_reply = "⚠️ Message was too short to save. Try sending more details."

        await _send_and_persist(
            db=db,
            conversation=conversation,
            user_id=owner.id,
            to_number=from_number,
            text=msg_reply,
            phone_number_id=phone_number_id,
            is_ai_generated=False,
        )

    elif msg_type == "document":
        doc = msg.get("document", {})
        media_id = doc.get("id")
        filename = doc.get("filename", "unknown.txt")

        try:
            file_bytes = await whatsapp_service.download_media(media_id)

            # Extract text based on file type
            if filename.lower().endswith(".pdf"):
                import fitz  # PyMuPDF
                import base64

                await _send_and_persist(
                    db=db,
                    conversation=conversation,
                    user_id=owner.id,
                    to_number=from_number,
                    text=f"📄 Reading '{filename}'... This may take a minute for large documents.",
                    phone_number_id=phone_number_id,
                    is_ai_generated=False,
                )

                pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
                total_pages = len(pdf_doc)
                all_text_parts = []
                vision_pages = 0

                for i, page in enumerate(pdf_doc):
                    if i >= 30:  # Max 30 pages
                        break

                    # First try: extract text directly (fast, works for text-based pages)
                    page_text = page.get_text().strip()

                    if len(page_text) > 30:
                        # Good text extraction - use it
                        all_text_parts.append(f"--- Page {i+1} ---\n{page_text}")
                    else:
                        # Image-based page - use GPT-4o vision (slower but reads images)
                        try:
                            pix = page.get_pixmap(dpi=150)
                            img_bytes = pix.tobytes("png")
                            b64_img = base64.b64encode(img_bytes).decode("utf-8")

                            client = _get_llm_client()
                            vision_resp = await client.chat.completions.create(
                                model="gpt-4o-mini",
                                messages=[{
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": "Extract ALL text from this image exactly as shown. Include every item name, price, quantity, and description. Output as plain text only - no explanations or commentary."},
                                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
                                    ]
                                }],
                                max_tokens=2000,
                            )
                            extracted = vision_resp.choices[0].message.content
                            if extracted and len(extracted.strip()) > 10:
                                all_text_parts.append(f"--- Page {i+1} ---\n{extracted}")
                                vision_pages += 1
                        except Exception as ve:
                            logger.warning(f"Vision extraction failed for page {i+1}: {ve}")

                pdf_doc.close()
                text_content = "\n\n".join(all_text_parts).strip()
                logger.info(f"PDF processed: {total_pages} total pages, {len(all_text_parts)} extracted, {vision_pages} via vision")
            else:
                # Plain text files (.txt, .csv, etc.)
                text_content = file_bytes.decode("utf-8", errors="ignore")

            count, err = await rag_service.ingest_text(
                db,
                text_content,
                owner.id,
                source_type="whatsapp_document",
            )

            if count > 0:
                preview = text_content[:150].replace("\n", " ") + ("..." if len(text_content) > 150 else "")
                msg_reply = f"📄 Read '{filename}' — saved {count} knowledge chunk(s)!\n\nPreview: \"{preview}\"\n\nI'll use this to answer customer questions."
            elif err:
                msg_reply = f"❌ Couldn't learn from '{filename}'. Error: {err}"
            else:
                msg_reply = f"⚠️ '{filename}' didn't contain enough text to learn from."

            await _send_and_persist(
                db=db,
                conversation=conversation,
                user_id=owner.id,
                to_number=from_number,
                text=msg_reply,
                phone_number_id=phone_number_id,
                is_ai_generated=False,
            )
        except Exception as e:
            logger.error(f"Failed to process owner document: {e}")
            await _send_and_persist(
                db=db,
                conversation=conversation,
                user_id=owner.id,
                to_number=from_number,
                text=f"⚠️ I couldn't read '{filename}'. Error: {str(e)[:200]}",
                phone_number_id=phone_number_id,
                is_ai_generated=False,
            )
    else:
        await _send_and_persist(
            db=db,
            conversation=conversation,
            user_id=owner.id,
            to_number=from_number,
            text="👋 I can learn from text and documents (.txt/.csv). Send menu, prices, or FAQs.",
            phone_number_id=phone_number_id,
            is_ai_generated=False,
        )


async def _handle_customer_message(
    db: AsyncSession,
    owner: User,
    config: Optional[WhatsAppBotConfig],
    conversation: WhatsAppConversation,
    inbound_record: WhatsAppMessage,
    msg: dict,
    msg_type: str,
    from_number: str,
    phone_number_id: Optional[str],
    owner_phone_number: Optional[str],
):
    """Customer message flow: retrieve context -> LLM answer -> reply + escalation checks."""
    if msg_type != "text":
        await _send_and_persist(
            db=db,
            conversation=conversation,
            user_id=owner.id,
            to_number=from_number,
            text="Hi! I can read text messages right now. Please type your question 😊",
            phone_number_id=phone_number_id,
            is_ai_generated=False,
        )
        return

    question = msg.get("text", {}).get("body", "").strip()
    if not question:
        return

    rag_context_units = 0
    retrieval_action = "legacy"
    context = "No specific business context found."
    chunks = []

    try:
        if settings.CRAG_ENABLED:
            semantic_scored = await rag_service.search_knowledge_scored(
                db=db,
                query=question,
                user_id=owner.id,
                limit=settings.CRAG_MAX_INTERNAL_CHUNKS,
            )
            retrieval_eval = rag_service.evaluate_retrieval_action(
                scored_chunks=semantic_scored,
                high_threshold=settings.CRAG_HIGH_CONFIDENCE_THRESHOLD,
                low_threshold=settings.CRAG_LOW_CONFIDENCE_THRESHOLD,
            )
            retrieval_action = retrieval_eval["action"]

            chunks = [item["chunk"] for item in semantic_scored]
            internal_refined = await rag_service.refine_chunks_for_query(
                query=question,
                chunks=chunks,
                max_strips=settings.CRAG_MAX_REFINED_STRIPS,
                min_similarity=settings.CRAG_MIN_STRIP_SIMILARITY,
            )
            final_strips = internal_refined

            if retrieval_action in {"ambiguous", "incorrect"}:
                rewritten = rag_service.rewrite_query_keywords(question)
                lexical_chunks = await rag_service.search_knowledge_lexical(
                    db=db,
                    query=rewritten,
                    user_id=owner.id,
                    limit=settings.CRAG_MAX_EXTERNAL_CHUNKS,
                )
                external_refined = await rag_service.refine_chunks_for_query(
                    query=question,
                    chunks=lexical_chunks,
                    max_strips=settings.CRAG_MAX_REFINED_STRIPS,
                    min_similarity=settings.CRAG_MIN_STRIP_SIMILARITY,
                )
                final_strips = rag_service.merge_unique_strips(
                    internal_refined,
                    external_refined,
                    max_items=settings.CRAG_MAX_REFINED_STRIPS,
                )

            rag_context_units = len(final_strips)
            if final_strips:
                context = "\n".join([f"- {strip}" for strip in final_strips])
        else:
            chunks = await rag_service.search_knowledge(db, question, owner.id, limit=5)
            rag_context_units = len(chunks)
            if chunks:
                context = "\n".join([f"- {c.content}" for c in chunks])
    except Exception as retrieval_err:
        logger.warning("CRAG retrieval failed, using semantic fallback", error=str(retrieval_err))
        chunks = await rag_service.search_knowledge(db, question, owner.id, limit=5)
        rag_context_units = len(chunks)
        retrieval_action = "fallback_semantic"
        if chunks:
            context = "\n".join([f"- {c.content}" for c in chunks])

    logger.info(
        "RAG retrieval decision",
        user_id=str(owner.id),
        action=retrieval_action,
        context_units=rag_context_units,
    )

    use_case = config.use_case_type if config else "general"
    
    # Dynamic personas based on business type
    personas = {
        "restaurant": "restaurant or mess",
        "salon": "salon or parlour",
        "tiffin": "daily tiffin or meal subscription service",
        "kirana": "kirana or grocery store",
        "coaching": "coaching class or tuition center",
        "clinic": "doctor's clinic or medical practice",
        "gym": "gym, fitness center, or yoga studio",
        "general": "local business"
    }
    
    persona_desc = personas.get(use_case, "local business")

    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    day_of_week = datetime.now().strftime('%A')
    business_name = config.business_display_name if config else "our business"

    # Vertical-specific tool instructions
    vertical_instructions = {
        "restaurant": (
            "7. MENU & ORDERS: You can show the menu, check item availability, create orders, and show order history using tools.\n"
            "8. WEATHER: You can check weather to suggest rain-day/cold-day promos.\n"
            "9. DELIVERY: You can check delivery distance and estimate charges.\n"
        ),
        "tiffin": (
            "7. MENU: You can show today's tiffin menu using the get_todays_menu tool.\n"
            "8. SUBSCRIPTIONS: You can create, pause, and resume tiffin subscriptions for customers.\n"
            "9. DELIVERY: You can check delivery distance using the check_delivery_distance tool.\n"
        ),
        "salon": (
            "7. APPOINTMENTS: You can check salon slot availability and book appointments using salon-specific tools.\n"
            "8. LOYALTY: You can check customer loyalty tier and next reward milestone.\n"
        ),
        "clinic": (
            "7. QUEUE: You can generate a queue token for patients and show estimated wait times.\n"
            "8. QUEUE STATUS: You can check how many patients are waiting and current token number.\n"
        ),
        "kirana": (
            "7. CATALOG: You can search the store inventory for products using the search_catalog tool.\n"
            "8. CREDIT (UDHAR): You can check customer's udhar/khata balance using get_udhar_balance.\n"
            "9. DELIVERY: You can check delivery distance for home delivery orders.\n"
        ),
        "coaching": (
            "7. ATTENDANCE: You can show a student's attendance report for any month.\n"
            "8. FEES: You can check if the student has any pending fee invoices.\n"
        ),
        "gym": (
            "7. MEMBERSHIP: You can check membership status, days remaining, and streak using check_membership.\n"
            "8. CLASSES: You can show the class schedule and book spots in classes.\n"
        ),
    }
    extra_rules = vertical_instructions.get(use_case, "")

    client = _get_llm_client()
    system_prompt = (
        f"You are a friendly WhatsApp AI assistant for '{business_name}', a {persona_desc}. "
        f"Today is {day_of_week}, {today_str}. "
        "You help customers with appointments, pricing questions, and general inquiries.\n\n"
        
        "CRITICAL RULES:\n"
        "1. APPOINTMENTS & BOOKING: When a customer wants to book, check availability, reschedule, or cancel an appointment — "
        "you MUST use the provided tool functions (check_available_slots, book_slot, cancel_bookings, check_customer_bookings). "
        "NEVER say 'I cannot book' or 'I don't have access to scheduling'. You DO have full booking access via tools.\n"
        "2. BUSINESS INFORMATION: All information in the BUSINESS KNOWLEDGE section below is PUBLIC business information "
        "(phone numbers, addresses, prices, doctor names, etc.). You MUST share this freely when asked. "
        "These are NOT private or personal — they are the business's public contact details and service menu.\n"
        "3. NEVER say 'I cannot provide customer phone numbers' or 'I cannot share personal information'. "
        "Everything in the knowledge base is meant to be shared with customers.\n"
        "4. Keep answers concise, warm, and helpful. Use emojis sparingly. Hinglish is fine if the customer uses Hindi.\n"
        "5. If the customer says 'tomorrow', calculate the actual date from today's date.\n"
        "6. When booking, ALWAYS call check_available_slots first to show real availability, then book_slot after the customer confirms a time.\n"
        f"{extra_rules}"
        "\n"
        f"=== BUSINESS KNOWLEDGE ===\n{context}\n=== END ==="
    )

    # Fetch enabled tool names from config
    enabled_tool_names = None
    if config and config.enabled_tools and isinstance(config.enabled_tools, dict):
        enabled_tool_names = [k for k, v in config.enabled_tools.items() if v]

    from app.tools.registry import get_tools_for_vertical
    
    # 1. Fetch Core tools (filtered)
    tools = get_tools_for_vertical("core", enabled_tools=enabled_tool_names)
    
    # 2. Fetch Vertical tools (filtered)
    vertical_tool_schemas = get_tools_for_vertical(use_case, enabled_tools=enabled_tool_names)
    tools.extend(vertical_tool_schemas)

    # Fetch last 10 messages for context
    from app.db.models import WhatsAppMessage
    stmt_hist = (
        select(WhatsAppMessage)
        .filter(
            WhatsAppMessage.conversation_id == conversation.id,
            WhatsAppMessage.id != inbound_record.id  # Exclude the current message we just saved
        )
        .order_by(WhatsAppMessage.created_at.desc())
        .limit(10)
    )
    res_hist = await db.execute(stmt_hist)
    history_records = res_hist.scalars().all()

    messages = [{"role": "system", "content": system_prompt}]
    
    # Add history in chronological order
    for rec in reversed(history_records):
        role = "assistant" if rec.direction == "outbound" else "user"
        content = rec.content or ""
        if content:
            messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    try:
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=tools,
            tool_choice="auto",
            max_tokens=500,
            temperature=0.3,
        )
        
        response_message = completion.choices[0].message
        
        # Check if the AI wants to call a tool
        if response_message.tool_calls:
            messages.append(response_message)
            import json
            from app.services.slot_engine import get_final_available_slots, acquire_slot_lock, release_slot_lock, create_calendar_event, cancel_calendar_events, check_customer_bookings as slot_check_customer_bookings
            from app.services.whatsapp_service import send_text_message
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                if function_name == "check_available_slots":
                    target_date_str = function_args.get("target_date")
                    try:
                        target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
                        slots = await get_final_available_slots(db, str(config.id), target_dt)
                        if slots:
                            formatted_slots = [s["start"].split(" ")[1] for s in slots]
                            tool_result = f"Available slots for {target_date_str}: {', '.join(formatted_slots)}"
                        else:
                            tool_result = f"No slots available for {target_date_str}."
                    except Exception as e:
                        tool_result = f"Error checking slots: {e}"
                        
                elif function_name == "book_slot":
                    dt_str = function_args.get("date_time")
                    locked = await acquire_slot_lock(str(config.id), dt_str, from_number)
                    if locked:
                        success = await create_calendar_event(db, str(config.id), from_number, dt_str)
                        if success:
                            tool_result = f"Successfully booked {dt_str}. Let the customer know."
                            # Send notification to owner
                            if owner_phone_number:
                                try:
                                    await send_text_message(
                                        to_number=owner_phone_number,
                                        message=f"📅 New booking alert!\nCustomer {from_number} just booked an appointment for {dt_str}.",
                                        phone_number_id=phone_number_id,
                                    )
                                except Exception as notify_err:
                                    logger.error(f"Failed to notify owner about booking: {notify_err}")
                        else:
                            # Calendar failed, free the lock
                            await release_slot_lock(str(config.id), dt_str, from_number)
                            tool_result = f"Failed to book {dt_str} due to calendar error. Ask them to try again later."
                    else:
                        tool_result = f"Failed to book {dt_str}. The slot is locked by someone else or no longer available. Ask them to pick another time."

                elif function_name == "cancel_bookings":
                    target_date_str = function_args.get("target_date")
                    try:
                        cancelled_count = await cancel_calendar_events(db, str(config.id), from_number, target_date_str)
                        if cancelled_count > 0:
                            tool_result = f"Successfully cancelled {cancelled_count} booking(s) for {target_date_str}."
                            # Notify owner about cancellation
                            if owner_phone_number:
                                try:
                                    await send_text_message(
                                        to_number=owner_phone_number,
                                        message=f"❌ Booking cancelled!\nCustomer {from_number} cancelled {cancelled_count} booking(s) for {target_date_str}.",
                                        phone_number_id=phone_number_id,
                                    )
                                except Exception as notify_err:
                                    logger.error(f"Failed to notify owner about cancellation: {notify_err}")
                        else:
                            tool_result = f"No bookings found for {target_date_str} to cancel."
                    except Exception as e:
                        tool_result = f"Error cancelling bookings: {e}"

                elif function_name == "check_customer_bookings":
                    target_date_str = function_args.get("target_date")
                    existing_bookings = await slot_check_customer_bookings(db, str(config.id), from_number, target_date_str)
                    if existing_bookings != "None":
                        tool_result = f"The customer currently has appointments at: {existing_bookings}."
                    else:
                        tool_result = f"The customer has NO appointments for {target_date_str}."

                else:
                    # Route to vertical tool executor (Phase 5)
                    from app.tools.registry import execute_vertical_tool
                    sheet_id = None
                    if config:
                        # Use dedicated sheet field first. Fall back to legacy google_doc_id
                        # to avoid breaking existing installs that stored Sheet ID there.
                        sheet_id = getattr(config, "google_sheet_id", None) or getattr(config, "google_doc_id", None)
                    tool_result = await execute_vertical_tool(
                        use_case_type=use_case,
                        function_name=function_name,
                        function_args=function_args,
                        customer_phone=from_number,
                        customer_name=from_number,  # We use phone as name fallback
                        spreadsheet_id=sheet_id,
                        business_name=business_name,
                    )
                    
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": tool_result
                })
                
            # Second call to AI with the tool results
            second_response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=500,
                temperature=0.3,
            )
            reply = (second_response.choices[0].message.content or "").strip()
        else:
            reply = (response_message.content or "").strip()
            
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        reply = "Sorry, I'm having trouble right now. A human teammate can help shortly. 🙏"

    await _send_and_persist(
        db=db,
        conversation=conversation,
        user_id=owner.id,
        to_number=from_number,
        text=reply,
        phone_number_id=phone_number_id,
        is_ai_generated=True,
    )

    should_escalate, reason, severity = _should_escalate(question, rag_context_units, reply)
    if should_escalate and reason:
        await _create_escalation(
            db=db,
            conversation=conversation,
            user_id=owner.id,
            reason=reason,
            severity=severity,
            trigger_message_id=inbound_record.id,
            notes=f"Auto escalation for question: {question[:120]}",
        )

    logger.info(
        "Customer replied",
        from_number=from_number,
        conversation_id=str(conversation.id),
        escalated=should_escalate,
    )


# ─── Inbox & escalation APIs (Dashboard use) ─────────────────────────────────


@router.get("/inbox/conversations")
async def list_conversations(
    user_id: Optional[UUID] = Query(None),
    escalated_only: bool = Query(False),
    manual_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(WhatsAppConversation).filter(WhatsAppConversation.user_id == current_user.id)
    if manual_only:
        q = q.filter(WhatsAppConversation.manual_mode.is_(True))

    q = q.order_by(WhatsAppConversation.last_message_at.desc()).offset(offset).limit(limit)
    res = await db.execute(q)
    conversations = res.scalars().all()

    open_escalation_map: dict[UUID, dict] = {}
    if conversations:
        conv_ids = [c.id for c in conversations]
        stmt_esc = (
            select(WhatsAppEscalation)
            .filter(
                WhatsAppEscalation.conversation_id.in_(conv_ids),
                WhatsAppEscalation.status == "open",
            )
        )
        res_esc = await db.execute(stmt_esc)
        open_escalations = res_esc.scalars().all()
        for esc in open_escalations:
            open_escalation_map[esc.conversation_id] = {
                "id": str(esc.id),
                "reason": esc.reason,
                "severity": esc.severity,
                "created_at": esc.created_at,
            }

    result = []
    for c in conversations:
        open_esc = open_escalation_map.get(c.id)
        if escalated_only and not open_esc:
            continue

        result.append(
            {
                "id": str(c.id),
                "user_id": str(c.user_id),
                "customer_phone": c.customer_phone,
                "phone_number_id": c.phone_number_id,
                "last_message_preview": c.last_message_preview,
                "last_message_at": c.last_message_at,
                "manual_mode": c.manual_mode,
                "is_blocked": c.is_blocked,
                "open_escalation": open_esc,
            }
        )

    return {"items": result, "count": len(result), "offset": offset, "limit": limit}


@router.get("/inbox/conversations/{conversation_id}/messages")
async def list_conversation_messages(
    conversation_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res_conv = await db.execute(select(WhatsAppConversation).filter(
        WhatsAppConversation.id == conversation_id,
        WhatsAppConversation.user_id == current_user.id
    ))
    conversation = res_conv.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    stmt = (
        select(WhatsAppMessage)
        .filter(WhatsAppMessage.conversation_id == conversation_id)
        .order_by(WhatsAppMessage.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    res_msg = await db.execute(stmt)
    items = res_msg.scalars().all()
    return {
        "conversation_id": str(conversation_id),
        "items": [
            {
                "id": str(m.id),
                "wa_message_id": m.wa_message_id,
                "direction": m.direction,
                "message_type": m.message_type,
                "content": m.content,
                "status": m.status,
                "is_ai_generated": m.is_ai_generated,
                "created_at": m.created_at,
            }
            for m in items
        ],
        "count": len(items),
    }


@router.patch("/inbox/conversations/{conversation_id}/manual-mode")
async def update_manual_mode(
    conversation_id: UUID,
    payload: ManualModeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res_conv = await db.execute(select(WhatsAppConversation).filter(
        WhatsAppConversation.id == conversation_id,
        WhatsAppConversation.user_id == current_user.id
    ))
    conversation = res_conv.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.manual_mode = payload.manual_mode
    conversation.updated_at = _utcnow()
    await db.commit()
    await db.refresh(conversation)

    return {
        "conversation_id": str(conversation.id),
        "manual_mode": conversation.manual_mode,
    }


@router.post("/inbox/conversations/{conversation_id}/reply")
async def send_manual_reply(
    conversation_id: UUID,
    payload: ManualReplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res_conv = await db.execute(select(WhatsAppConversation).filter(
        WhatsAppConversation.id == conversation_id,
        WhatsAppConversation.user_id == current_user.id
    ))
    conversation = res_conv.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    response = await _send_and_persist(
        db=db,
        conversation=conversation,
        user_id=conversation.user_id,
        to_number=conversation.customer_phone,
        text=message,
        phone_number_id=conversation.phone_number_id,
        is_ai_generated=False,
    )

    return {
        "conversation_id": str(conversation.id),
        "status": "sent",
        "provider_response": response,
    }


@router.get("/inbox/escalations")
async def list_escalations(
    user_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query("open"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(WhatsAppEscalation).filter(WhatsAppEscalation.user_id == current_user.id)
    if status:
        q = q.filter(WhatsAppEscalation.status == status)

    q = q.order_by(WhatsAppEscalation.created_at.desc()).offset(offset).limit(limit)
    res = await db.execute(q)
    items = res.scalars().all()
    return {
        "items": [
            {
                "id": str(e.id),
                "conversation_id": str(e.conversation_id),
                "user_id": str(e.user_id),
                "reason": e.reason,
                "severity": e.severity,
                "status": e.status,
                "notes": e.notes,
                "created_at": e.created_at,
                "resolved_at": e.resolved_at,
            }
            for e in items
        ],
        "count": len(items),
    }


@router.patch("/inbox/escalations/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: UUID,
    payload: EscalationResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res_esc = await db.execute(select(WhatsAppEscalation).filter(
        WhatsAppEscalation.id == escalation_id,
        WhatsAppEscalation.user_id == current_user.id
    ))
    escalation = res_esc.scalar_one_or_none()
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    escalation.status = "resolved"
    escalation.resolved_at = _utcnow()
    if payload.notes:
        escalation.notes = payload.notes

    await db.commit()
    await db.refresh(escalation)

    return {
        "id": str(escalation.id),
        "status": escalation.status,
        "resolved_at": escalation.resolved_at,
    }


@router.post("/bot-config")
async def upsert_bot_config(
    payload: BotConfigUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Ensure they can only update their own bot config unless they are a superuser
    if payload.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot assign bot config to another user")

    # Auto-assign default phone number if "auto" is passed (simplified onboarding)
    phone_id = payload.phone_number_id
    if phone_id == "auto":
        phone_id = settings.WHATSAPP_PHONE_NUMBER_ID or "0000000000000000"

    # Look up existing config by user_id first (shared number model)
    stmt = select(WhatsAppBotConfig).filter(WhatsAppBotConfig.user_id == payload.user_id)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.user_id = payload.user_id
        existing.owner_phone_number = payload.owner_phone_number
        existing.whatsapp_phone_number = payload.whatsapp_phone_number
        existing.business_display_name = payload.business_display_name
        existing.google_sheet_id = payload.google_sheet_id
        existing.use_case_type = payload.use_case_type
        existing.is_active = payload.is_active
        existing.updated_at = _utcnow()
        await db.commit()
        await db.refresh(existing)
        cfg = existing
    else:
        cfg = WhatsAppBotConfig(
            user_id=payload.user_id,
            phone_number_id=phone_id,
            owner_phone_number=payload.owner_phone_number,
            whatsapp_phone_number=payload.whatsapp_phone_number,
            business_display_name=payload.business_display_name,
            google_sheet_id=payload.google_sheet_id,
            use_case_type=payload.use_case_type,
            is_active=payload.is_active,
        )
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)

    return {
        "data": {
            "id": str(cfg.id),
            "user_id": str(cfg.user_id),
            "phone_number_id": cfg.phone_number_id,
            "owner_phone_number": cfg.owner_phone_number,
            "whatsapp_phone_number": cfg.whatsapp_phone_number,
            "business_display_name": cfg.business_display_name,
            "google_sheet_id": cfg.google_sheet_id,
            "use_case_type": cfg.use_case_type,
            "is_active": cfg.is_active,
        }
    }


@router.get("/bot-config")
async def get_bot_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get bot config for the currently logged in user."""
    stmt = (
        select(WhatsAppBotConfig)
        .filter(WhatsAppBotConfig.user_id == current_user.id, WhatsAppBotConfig.is_active.is_(True))
    )
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()
    
    if not config:
        return {"data": None}

    return {
        "data": {
            "id": str(config.id),
            "user_id": str(config.user_id),
            "phone_number_id": config.phone_number_id,
            "owner_phone_number": config.owner_phone_number,
            "whatsapp_phone_number": config.whatsapp_phone_number,
            "business_display_name": config.business_display_name,
            "use_case_type": config.use_case_type,
            "is_active": config.is_active,
            "google_doc_id": config.google_doc_id,
            "google_sheet_id": config.google_sheet_id,
            "has_calendar": config.google_calendar_token is not None,
        }
    }


@router.get("/bot-config/users")
async def list_available_users(
    limit: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Utility endpoint for frontend setup screens to pick a valid user_id."""
    # Note: Using AsyncSession logic
    res = await db.execute(select(User).filter(User.id == current_user.id).limit(limit))
    users = res.scalars().all()
    return {
        "items": [
            {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "username": u.username,
            }
            for u in users
        ],
        "count": len(users),
    }


@router.get("/tool-preferences")
async def get_tool_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's tool toggle preferences."""
    stmt = (
        select(WhatsAppBotConfig)
        .filter(WhatsAppBotConfig.user_id == current_user.id, WhatsAppBotConfig.is_active.is_(True))
    )
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()

    if not config:
        return {"data": {"enabled_tools": {}, "use_case_type": "general"}}

    return {
        "data": {
            "enabled_tools": config.enabled_tools or {},
            "use_case_type": config.use_case_type or "general",
        }
    }


@router.put("/tool-preferences")
async def update_tool_preferences(
    payload: ToolPreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save tool toggle preferences from the Settings UI."""
    stmt = (
        select(WhatsAppBotConfig)
        .filter(WhatsAppBotConfig.user_id == current_user.id, WhatsAppBotConfig.is_active.is_(True))
    )
    res = await db.execute(stmt)
    config = res.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="No active bot config found. Please set up your bot first.")

    config.enabled_tools = payload.enabled_tools
    config.updated_at = _utcnow()
    await db.commit()
    await db.refresh(config)

    enabled_count = sum(1 for v in payload.enabled_tools.values() if v)
    total_count = len(payload.enabled_tools)

    return {
        "status": "saved",
        "enabled_count": enabled_count,
        "total_count": total_count,
    }


@router.post("/system-alert")
async def receive_system_alert(
    payload: SystemAlertRequest,
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
    db: AsyncSession = Depends(get_db)
):
    """Internal webhook for core system to push generated content back to WhatsApp owner."""
    from app.services.whatsapp_service import send_text_message, send_media_message
    _verify_internal_webhook_secret(x_internal_secret)

    try:
        owner_id = UUID(payload.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    res_cfg = await db.execute(
        select(WhatsAppBotConfig).filter(
            WhatsAppBotConfig.user_id == owner_id,
            WhatsAppBotConfig.is_active.is_(True),
        )
    )
    bot_config = res_cfg.scalar_one_or_none()
    if not bot_config:
        raise HTTPException(status_code=404, detail="Active bot config not found for user")

    resolved_phone_number_id = payload.phone_number_id or bot_config.phone_number_id

    if payload.message:
        await send_text_message(
            to_number=payload.phone_number,
            message=payload.message,
            phone_number_id=resolved_phone_number_id
        )
        
    if payload.video_url:
        await send_media_message(
            to_number=payload.phone_number,
            media_url=payload.video_url,
            media_type="video",
            caption="🎥 Here is your generated video!",
            phone_number_id=resolved_phone_number_id
        )
    elif payload.image_url:
        await send_media_message(
            to_number=payload.phone_number,
            media_url=payload.image_url,
            media_type="image",
            caption="🖼️ Here is your generated image/poster!",
            phone_number_id=resolved_phone_number_id
        )
        
    return {"status": "ok"}

