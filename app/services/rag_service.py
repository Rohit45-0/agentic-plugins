"""
RAG Service (Lightweight) — Embedding generation, search, and document ingestion.
Connects to the shared knowledge_chunks table in PostgreSQL + pgvector.
"""
from typing import List, Any, Optional
from uuid import UUID

import structlog
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.models import KnowledgeChunk

logger = structlog.get_logger(__name__)

# Lazy-initialized embedding client
_embed_client: Optional[AsyncOpenAI] = None


def _get_embed_client() -> AsyncOpenAI:
    global _embed_client
    if _embed_client is None:
        _embed_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
        )
    return _embed_client


async def generate_embedding(text: str) -> List[float]:
    """Generate a 1536-dim embedding vector using pure OpenAI."""
    client = _get_embed_client()
    clean = text.replace("\n", " ").strip()[:8000]
    try:
        response = await client.embeddings.create(
            input=[clean],
            model="text-embedding-3-small",
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")
        raise RuntimeError(f"Failed to generate embedding: {e}")


async def search_knowledge(
    db: AsyncSession,
    query: str,
    user_id: UUID,
    limit: int = 5,
) -> List[KnowledgeChunk]:
    """Semantic search across knowledge_chunks for a specific user."""
    query_vec = await generate_embedding(query)
    
    stmt = (
        select(KnowledgeChunk)
        .filter(KnowledgeChunk.user_id == user_id)
        .order_by(KnowledgeChunk.embedding.cosine_distance(query_vec))
        .limit(limit)
    )
    res = await db.execute(stmt)
    results = res.scalars().all()
    if results:
        logger.info(f"[SEARCH] RAG search returned {len(results)} chunks for user {user_id}")
    return results


async def ingest_text(
    db: AsyncSession,
    text: str,
    user_id: UUID,
    category: str = "whatsapp_knowledge",
    source_type: str = "whatsapp_upload",
) -> int:
    """
    Take raw text, split into chunks, embed, and save to knowledge_chunks.
    Returns the number of chunks successfully ingested.
    """
    # Smart chunking: group lines into meaningful paragraphs (~500 chars each)
    # so related content (e.g., item name + price + description) stays together.
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    if not lines:
        if text.strip():
            chunks = [text.strip()]
        else:
            return 0, None

    # For short text (single WhatsApp message), keep as-is
    if len(lines) <= 3 or len(text) < 200:
        chunks = [text.strip()] if text.strip() else []
    else:
        # Group lines into paragraphs of ~500 characters
        chunks = []
        current_chunk = []
        current_len = 0
        for line in lines:
            current_chunk.append(line)
            current_len += len(line)
            if current_len >= 500:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_len = 0
        if current_chunk:
            chunks.append("\n".join(current_chunk))

    error_logs = []
    ingested = 0
    for chunk_text in chunks:
        try:
            embedding = await generate_embedding(chunk_text)
            new_chunk = KnowledgeChunk(
                user_id=user_id,
                content=chunk_text,
                embedding=embedding,
                category=category,
                source_type=source_type,
                confidence_score=1.0,
            )
            db.add(new_chunk)
            ingested += 1
        except Exception as e:
            logger.warning(f"Skipped chunk ingestion: {e}")
            error_logs.append(str(e))

    if ingested > 0:
        await db.commit()
        logger.info(f"[OK] Ingested {ingested} knowledge chunks for user {user_id}")
    return ingested, error_logs[0] if error_logs else None
