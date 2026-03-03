from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    # App
    PROJECT_NAME: str = "Catalyst Nexus Plugins"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    SECRET_KEY: str = "catalyst-plugins-secret-key-change-in-production"
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8001",
    ]

    # Database (shared with catalyst-nexus-core)
    DATABASE_URL: str

    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_ENDPOINT: str
    AZURE_DEPLOYMENT_NAME: str = "gpt-4o"
    
    # Pure OpenAI (for missing Azure embeddings)
    OPENAI_API_KEY: Optional[str] = None

    # WhatsApp Cloud API
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_BUSINESS_ACCOUNT_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_APP_SECRET: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: str = "catalyst_nexus_webhook_secret"

    # Owner phone number (used to distinguish admin from customer)
    OWNER_PHONE_NUMBER: Optional[str] = None

    # Inbox / escalation behavior
    ESCALATION_KEYWORDS: str = "human,agent,complaint,refund,cancel,angry,issue,problem"

    # Celery & Redis Queue
    REDIS_URL: str
    
    @property
    def CELERY_BROKER_URL(self) -> str:
        # Upstash rediss:// URLs require SSL cert requirements explicitly defined for Celery
        if self.REDIS_URL.startswith("rediss://") and "?" not in self.REDIS_URL:
            return f"{self.REDIS_URL}?ssl_cert_reqs=CERT_NONE"
        return self.REDIS_URL
        
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        if self.REDIS_URL.startswith("rediss://") and "?" not in self.REDIS_URL:
            return f"{self.REDIS_URL}?ssl_cert_reqs=CERT_NONE"
        return self.REDIS_URL

    # Google Calendar
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
