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
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
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

import time
from collections import defaultdict
from typing import Optional

# Lazy LLM client
_llm_client: Optional[AsyncOpenAI] = None

# Naive In-Memory Rate Limiting
_rate_limits = defaultdict(list)
RATE_LIMIT_MAX_MESSAGES = 10
RATE_LIMIT_WINDOW_SECONDS = 60

def _is_rate_limited(identifier: str) -> bool:
    now = time.time()
    # Prune old timestamps
    _rate_limits[identifier] = [t for t in _rate_limits[identifier] if now - t < RATE_LIMIT_WINDOW_SECONDS]
    
    if len(_rate_limits[identifier]) >= RATE_LIMIT_MAX_MESSAGES:
        return True
        
    _rate_limits[identifier].append(now)
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
    business_display_name: Optional[str] = None
    use_case_type: str = "restaurant"
    is_active: bool = True


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


def _is_owner_message(from_number: str, owner_phone_number: Optional[str]) -> bool:
    return bool(owner_phone_number and from_number == owner_phone_number)


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


async def _resolve_owner_context(db: AsyncSession, phone_number_id: Optional[str]) -> tuple[Optional[User], Optional[WhatsAppBotConfig], Optional[str]]:
    config = None
    owner = None

    if phone_number_id:
        stmt = (
            select(WhatsAppBotConfig)
            .filter(
                WhatsAppBotConfig.phone_number_id == phone_number_id,
                WhatsAppBotConfig.is_active.is_(True),
            )
        )
        res = await db.execute(stmt)
        config = res.scalar_one_or_none()

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
        logger.info("✅ Meta WhatsApp Webhook verified!")
        return int(hub_challenge)

    logger.warning("❌ Webhook verification failed: token mismatch")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/webhook")
async def handle_incoming(request: Request, background_tasks: BackgroundTasks):
    """Main listener. Meta POSTs here every time someone messages the bot."""
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    _verify_meta_signature(raw_body, signature)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Run processing directly in the background without Celery
    background_tasks.add_task(_process_payload, payload)
    
    return {"status": "ok"}


async def _process_payload(payload: dict):
    """Parse Meta webhook payload and process all message events in the batch."""
    async with AsyncSessionLocal() as db:
        try:
            for entry in payload.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    metadata = value.get("metadata", {})
                    phone_number_id = metadata.get("phone_number_id") or settings.WHATSAPP_PHONE_NUMBER_ID

                    owner, config, owner_phone_number = await _resolve_owner_context(db, phone_number_id)
                    if owner is None:
                        logger.warning("No owner found for incoming message batch")
                        continue

                    for msg in value.get("messages", []) or []:
                        await _process_single_message(
                            db=db,
                            owner=owner,
                            config=config,
                            msg=msg,
                            owner_phone_number=owner_phone_number,
                            phone_number_id=phone_number_id,
                        )

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
    if _is_rate_limited(f"customer:{from_number}"):
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
                        f"GREET|hello - when owner just says hi, hello, or tests the bot.\n"
                        f"CANCEL|<phone_number>|<date> - when owner wants to completely cancel a specific customer's booking. (e.g. {ex_cancel})\n"
                        f"CANCEL|ALL|<date> - when owner wants to cancel ALL schedule/appointments for a day. (e.g. {ex_cancel_all})\n"
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
            
            if intent_type == "CANCEL" and len(parts) >= 3:
                # Format: CANCEL|<phone>|<date>
                intent_content = parts[1].strip()
                extra_content = parts[2].strip()
            elif len(parts) >= 2:
                # Format: TYPE|<content>
                intent_content = parts[1].strip()
            else:
                intent_content = intent_raw
        else:
            intent_content = intent_raw

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

    chunks = await rag_service.search_knowledge(db, question, owner.id, limit=5)
    context = "\n".join([f"- {c.content}" for c in chunks]) if chunks else "No specific business context found."

    use_case = config.use_case_type if config else "general"
    
    # Dynamic personas based on business type
    personas = {
        "restaurant": "restaurant or mess",
        "salon": "salon or parlour",
        "tiffin": "daily tiffin or meal subscription service",
        "kirana": "kirana or grocery store",
        "coaching": "coaching class or tuition center",
        "general": "local business"
    }
    
    persona_desc = personas.get(use_case, "local business")

    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')

    client = _get_llm_client()
    system_prompt = (
        f"You are a helpful WhatsApp customer support assistant for a {persona_desc}. "
        f"Today's date is {today_str}. "
        "Below is information from the business's knowledge base. "
        "Use this information to answer the customer's question accurately and confidently. "
        "List specific items, prices, and details when available. "
        "Only say you don't have information if the knowledge base truly contains nothing relevant. "
        "Keep answers concise but complete. Hinglish is fine if the customer uses Hindi.\n\n"
        "If the customer wants to check availability, book a slot, check their own existing appointments, or cancel appointments, ALWAYS use the provided tools. You DO have access to managing their calendar through these tools. Do NOT say you don't have access.\n\n"
        f"=== BUSINESS KNOWLEDGE ===\n{context}\n=== END ==="
    )

    tools = [
        {
            "type": "function",
            "function": {
                "name": "check_available_slots",
                "description": "Get available booking slots for a specific date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_date": {
                            "type": "string",
                            "description": "The date to check in YYYY-MM-DD format (e.g. 2026-03-02)."
                        }
                    },
                    "required": ["target_date"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "book_slot",
                "description": "Book a specific slot time. Use this ONLY after the customer has agreed to a specific available time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "date_time": {
                            "type": "string",
                            "description": "The full start date and time of the booking in YYYY-MM-DD HH:MM format (e.g. 2026-03-02 14:30)."
                        }
                    },
                    "required": ["date_time"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "cancel_bookings",
                "description": "Cancel all bookings for a specific customer phone number on a specific date. This will remove the events from Google Calendar.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_date": {
                            "type": "string",
                            "description": "The date to cancel bookings for in YYYY-MM-DD format (e.g. 2026-03-06)."
                        }
                    },
                    "required": ["target_date"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "check_customer_bookings",
                "description": "Check if this customer has any existing appointments already booked on a specific date.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_date": {
                            "type": "string",
                            "description": "The date to check appointments for in YYYY-MM-DD format (e.g. 2026-03-06)."
                        }
                    },
                    "required": ["target_date"],
                },
            }
        }
    ]

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
                    tool_result = "Unknown function call."
                    
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

    should_escalate, reason, severity = _should_escalate(question, len(chunks), reply)
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

    stmt = select(WhatsAppBotConfig).filter(WhatsAppBotConfig.phone_number_id == payload.phone_number_id)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        existing.user_id = payload.user_id
        existing.owner_phone_number = payload.owner_phone_number
        existing.business_display_name = payload.business_display_name
        existing.use_case_type = payload.use_case_type
        existing.is_active = payload.is_active
        existing.updated_at = _utcnow()
        await db.commit()
        await db.refresh(existing)
        cfg = existing
    else:
        cfg = WhatsAppBotConfig(
            user_id=payload.user_id,
            phone_number_id=payload.phone_number_id,
            owner_phone_number=payload.owner_phone_number,
            business_display_name=payload.business_display_name,
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
            "business_display_name": cfg.business_display_name,
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
            "business_display_name": config.business_display_name,
            "use_case_type": config.use_case_type,
            "is_active": config.is_active,
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
