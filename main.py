"""
Catalyst Nexus Plugins — FastAPI Entry Point
=============================================
A standalone microservice for WhatsApp Bot integrations.
Connects to the same PostgreSQL database as catalyst-nexus-core.
Runs on port 8001 to avoid conflict with the core API on port 8000.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
import structlog

from app.core.config import settings
from app.api.whatsapp import router as whatsapp_router
from app.db.base import Base, engine
from app.db import models  # noqa: F401 - ensures model metadata is registered

# Structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

app = FastAPI(
    title="Catalyst Nexus Plugins",
    description="WhatsApp RAG Bot — AI-powered customer service & marketing for local businesses",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    default_response_class=ORJSONResponse,
)

@app.get("/health")
def read_health():
    return {"status": "ok", "version": "fix-deployment-v4"}


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

from app.api.calendar import router as calendar_router
from app.api.slots import router as slots_router
from app.api.dashboard import router as dashboard_router

# Register routers
app.include_router(whatsapp_router, prefix="/api/v1/whatsapp", tags=["WhatsApp Bot"])
app.include_router(calendar_router, prefix="/api/v1/calendar", tags=["Google Calendar"])
app.include_router(slots_router, prefix="/api/v1/slots", tags=["Booking Slots"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Bot Analytics Dashboard"])

@app.on_event("startup")
async def startup() -> None:
    """Ensure plugin-specific tables exist for inbox/escalation workflows."""
    import logging
    logger = logging.getLogger("startup")
    try:
        logger.info("Attempting DB table creation...")
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all,
                tables=[
                    models.SlotConfig.__table__,
                    models.WhatsAppBotConfig.__table__,
                    models.WhatsAppConversation.__table__,
                    models.WhatsAppMessage.__table__,
                    models.WhatsAppEscalation.__table__,
                    models.WhatsAppProcessedMessage.__table__,
                ],
            )
        logger.info("DB tables verified successfully.")
    except Exception as e:
        logger.error(f"Startup DB error (non-fatal): {e}")
        # Don't crash the pod — tables likely already exist


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "operational",
        "service": "Catalyst Nexus Plugins",
        "version": "0.1.0",
        "plugins": ["whatsapp-rag-bot"],
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy", "plugin": "whatsapp-bot", "database": "shared-with-core"}
