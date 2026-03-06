from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

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

# PgBouncer (Supabase port 6543, transaction mode) does NOT support
# named prepared statements. We must fully disable them at both layers:
#   1. statement_cache_size=0            → asyncpg driver level
#   2. prepared_statement_cache_size=0   → asyncpg driver level
#   3. prepared_statement_name_func      → force anonymous stmts
engine = create_async_engine(
    async_url,
    pool_pre_ping=True,
    pool_timeout=10,
    pool_recycle=300,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "command_timeout": 30,
    },
)

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

