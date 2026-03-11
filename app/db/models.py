"""
Shared DB Models — mirrors only the tables needed by the WhatsApp plugin.
These MUST match the schema in catalyst-nexus-core exactly.
"""
import uuid
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    Float,
    Integer,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.db.base import Base


class User(Base):
    """Mirror of the core User table (read-only from plugin side)."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    wallet_balance = Column(Integer, default=500, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class KnowledgeChunk(Base):
    """Shared RAG knowledge base — the WhatsApp bot reads AND writes to this."""
    __tablename__ = "knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    project_id = Column(UUID(as_uuid=True), nullable=True)

    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))

    category = Column(String, index=True)
    source_type = Column(String)
    source_id = Column(String, nullable=True)
    confidence_score = Column(Float, default=1.0)
    created_at = Column(DateTime, server_default=func.now())
    
    __table_args__ = (
        Index(
            "ix_knowledge_chunk_embedding",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class WhatsAppBotConfig(Base):
    """Maps a WhatsApp business number to a specific owner/user (tenant isolation)."""
    __tablename__ = "whatsapp_bot_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    phone_number_id = Column(String, nullable=False, index=True)
    owner_phone_number = Column(String, nullable=True, index=True)
    whatsapp_phone_number = Column(String, nullable=True)
    business_display_name = Column(String, nullable=True)
    use_case_type = Column(String, nullable=False, default="restaurant") # Add use case type
    slot_config_id = Column(UUID(as_uuid=True), ForeignKey("slot_configs.id"), nullable=True)
    google_calendar_token = Column(JSON, nullable=True) # Stores the OAuth token
    google_doc_id = Column(String, nullable=True) # Connects to "Catalyst AI - Knowledge Base" doc
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SlotConfig(Base):
    """Business rules for the Slot Engine (hours, duration, capacity)."""
    __tablename__ = "slot_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # E.g. {"monday": [{"start": "09:00", "end": "13:00"}, {"start": "14:00", "end": "17:00"}], "saturday": []}
    working_hours = Column(JSON, nullable=False, default={})
    slot_duration_minutes = Column(Integer, default=15, nullable=False)
    max_capacity_per_slot = Column(Integer, default=1, nullable=False)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WhatsAppConversation(Base):
    """Conversation thread between one customer and one business tenant."""
    __tablename__ = "whatsapp_conversations"
    __table_args__ = (
        UniqueConstraint("user_id", "customer_phone", name="uq_whatsapp_conversation_user_customer"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    phone_number_id = Column(String, nullable=True, index=True)
    customer_phone = Column(String, nullable=False, index=True)
    last_message_preview = Column(Text, nullable=True)
    last_message_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    manual_mode = Column(Boolean, default=False, nullable=False)
    is_blocked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class WhatsAppMessage(Base):
    """Stores inbound/outbound WhatsApp messages for dashboard inbox."""
    __tablename__ = "whatsapp_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_conversations.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    wa_message_id = Column(String, unique=True, nullable=True, index=True)
    direction = Column(String, nullable=False, index=True)  # inbound | outbound
    message_type = Column(String, nullable=False, default="text")
    content = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="sent", index=True)
    is_ai_generated = Column(Boolean, default=False, nullable=False)
    raw_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)


class WhatsAppEscalation(Base):
    """Escalation tickets for conversations requiring owner attention."""
    __tablename__ = "whatsapp_escalations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_conversations.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    trigger_message_id = Column(UUID(as_uuid=True), ForeignKey("whatsapp_messages.id"), nullable=True, index=True)
    reason = Column(String, nullable=False, index=True)
    severity = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="open", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)


class WhatsAppProcessedMessage(Base):
    """Idempotency table to avoid duplicate processing of webhook retries."""
    __tablename__ = "whatsapp_processed_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wa_message_id = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


# ─── NEW TOOLS ARCHITECTURE MODELS ───────────────────────────────────────────

class Customer(Base):
    """Centralized customer record across all verticals."""
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("user_id", "phone", name="uq_customer_user_phone"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True) # owner/tenant ID
    phone = Column(String, nullable=False, index=True)
    name = Column(String, nullable=True)
    first_seen = Column(DateTime, server_default=func.now())
    last_interaction = Column(DateTime, server_default=func.now(), onupdate=func.now())
    language_preference = Column(String, default="en")
    notes = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # Store list of strings
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Booking(Base):
    """Universal booking tracker for all slot-based services."""
    __tablename__ = "bookings"
    __table_args__ = (
        UniqueConstraint("user_id", "booking_date", "booking_time", "customer_phone", name="uq_booking_slot"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True) # Business ID
    customer_phone = Column(String, nullable=False, index=True)
    customer_name = Column(String, nullable=True)
    service_type = Column(String, nullable=True)
    
    booking_date = Column(String, nullable=False, index=True) # e.g., "yyyy-mm-dd"
    booking_time = Column(String, nullable=False, index=True) # e.g., "hh:mm"
    
    status = Column(String, nullable=False, default="holding", index=True) # holding, confirmed, completed, cancelled, no_show
    booked_via = Column(String, nullable=False, default="whatsapp") # whatsapp, walkin, phone, app
    
    payment_status = Column(String, nullable=False, default="pending") # pending, paid, refunded
    payment_id = Column(String, nullable=True) # Links to Razorpay or Payments table
    
    version = Column(Integer, default=1, nullable=False) # For optimistic locking
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Payment(Base):
    """Tracks Razorpay generated links and payments."""
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    customer_phone = Column(String, nullable=False, index=True)
    
    razorpay_link_id = Column(String, nullable=True, unique=True)
    razorpay_payment_id = Column(String, nullable=True, index=True)
    
    amount_paise = Column(Integer, nullable=False)
    description = Column(String, nullable=True)
    
    status = Column(String, nullable=False, default="created") # created, paid, expired, cancelled, refunded
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    paid_at = Column(DateTime, nullable=True)


class ToolLog(Base):
    """Audit log for AI tool interactions."""
    __tablename__ = "tool_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    tool_name = Column(String, nullable=False, index=True)
    action = Column(String, nullable=False)
    params = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    
    success = Column(Boolean, nullable=False, default=True)
    duration_ms = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now(), index=True)

