from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

_engine_kwargs = {
    "pool_pre_ping": True,
    "pool_timeout": 10,
    "pool_recycle": 300,
    "connect_args": {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
}

# Convert any PostgreSQL URL variant to asyncpg
_raw_url = settings.DATABASE_URL
if _raw_url.startswith("postgresql+asyncpg://"):
    async_url = _raw_url  # already correct
elif _raw_url.startswith("postgresql://"):
    async_url = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _raw_url.startswith("postgres://"):
    async_url = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    async_url = _raw_url  # fallback

engine = create_async_engine(async_url, **_engine_kwargs)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
