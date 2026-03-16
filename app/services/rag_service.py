"""
RAG service for embedding generation, retrieval, and CRAG-lite refinement.
Uses PostgreSQL + pgvector knowledge_chunks table.
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from openai import AsyncOpenAI
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.db.models import KnowledgeChunk

logger = structlog.get_logger(__name__)

_embed_client: Optional[AsyncOpenAI] = None

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "for", "of", "on", "in", "at",
    "by", "with", "and", "or", "from", "this", "that", "these", "those", "it", "its", "my",
    "your", "our", "their", "as", "do", "does", "did", "can", "could", "should", "would",
    "will", "i", "you", "we", "they", "he", "she", "me", "him", "her", "them", "about",
    "please", "tell", "what", "when", "where", "which", "who", "how", "why",
}


def _get_embed_client() -> AsyncOpenAI:
    global _embed_client
    if _embed_client is None:
        _embed_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _embed_client


def _clean_text(text: str, max_len: int = 8000) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:max_len]


def _tokenize(text: str, max_terms: int = 12) -> List[str]:
    raw_tokens = re.findall(r"[a-zA-Z0-9]{3,}", (text or "").lower())
    deduped: List[str] = []
    seen = set()
    for token in raw_tokens:
        if token in _STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)
        if len(deduped) >= max_terms:
            break
    return deduped


def rewrite_query_keywords(query: str, max_terms: int = 8) -> str:
    tokens = _tokenize(query, max_terms=max_terms)
    if not tokens:
        return query.strip()
    return " ".join(tokens)


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _distance_to_relevance(distance: Optional[float]) -> float:
    if distance is None:
        return 0.0
    d = max(0.0, min(2.0, float(distance)))
    return 1.0 - (d / 2.0)


def split_into_strips(text: str, max_chars: int = 260) -> List[str]:
    if not text or not text.strip():
        return []
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []

    strips: List[str] = []
    for para in paragraphs:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        if not sentences:
            continue
        bucket: List[str] = []
        bucket_len = 0
        for sentence in sentences:
            s_len = len(sentence)
            if bucket and bucket_len + s_len + 1 > max_chars:
                strips.append(" ".join(bucket).strip())
                bucket = [sentence]
                bucket_len = s_len
            else:
                bucket.append(sentence)
                bucket_len += s_len + (1 if bucket_len > 0 else 0)
        if bucket:
            strips.append(" ".join(bucket).strip())
    return strips


def merge_unique_strips(primary: List[str], secondary: List[str], max_items: int = 12) -> List[str]:
    merged: List[str] = []
    seen = set()
    for strip in primary + secondary:
        key = re.sub(r"\s+", " ", strip.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(strip.strip())
        if len(merged) >= max_items:
            break
    return merged


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    cleaned = [_clean_text(t) for t in texts]
    client = _get_embed_client()
    try:
        response = await client.embeddings.create(
            input=cleaned,
            model="text-embedding-3-small",
        )
        return [item.embedding for item in response.data]
    except Exception as exc:
        logger.error("Embedding batch generation failed", error=str(exc))
        raise RuntimeError(f"Failed to generate embeddings: {exc}")


async def generate_embedding(text: str) -> List[float]:
    vectors = await generate_embeddings([text])
    return vectors[0] if vectors else []


async def search_knowledge_scored(
    db: AsyncSession,
    query: str,
    user_id: UUID,
    limit: int = 8,
) -> List[Dict[str, Any]]:
    query_vec = await generate_embedding(query)
    distance_expr = KnowledgeChunk.embedding.cosine_distance(query_vec).label("distance")
    stmt = (
        select(KnowledgeChunk, distance_expr)
        .filter(KnowledgeChunk.user_id == user_id)
        .order_by(distance_expr)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    results: List[Dict[str, Any]] = []
    for chunk, distance in rows:
        results.append(
            {
                "chunk": chunk,
                "distance": float(distance),
                "relevance": _distance_to_relevance(float(distance)),
            }
        )
    return results


async def search_knowledge(
    db: AsyncSession,
    query: str,
    user_id: UUID,
    limit: int = 5,
) -> List[KnowledgeChunk]:
    scored = await search_knowledge_scored(db=db, query=query, user_id=user_id, limit=limit)
    chunks = [item["chunk"] for item in scored]
    if chunks:
        logger.info("RAG semantic search returned chunks", user_id=str(user_id), count=len(chunks))
    return chunks


async def search_knowledge_lexical(
    db: AsyncSession,
    query: str,
    user_id: UUID,
    limit: int = 8,
) -> List[KnowledgeChunk]:
    tokens = _tokenize(query, max_terms=8)
    if not tokens:
        return []

    conditions = [KnowledgeChunk.content.ilike(f"%{token}%") for token in tokens]
    candidate_limit = max(20, limit * 6)
    stmt = (
        select(KnowledgeChunk)
        .filter(KnowledgeChunk.user_id == user_id)
        .filter(or_(*conditions))
        .limit(candidate_limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    if not rows:
        return []

    ranked: List[tuple[float, KnowledgeChunk]] = []
    for row in rows:
        content_lower = (row.content or "").lower()
        hits = sum(1 for token in tokens if token in content_lower)
        if hits == 0:
            continue
        lexical_score = hits / max(1, len(tokens))
        ranked.append((lexical_score, row))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked[:limit]]


def evaluate_retrieval_action(
    scored_chunks: List[Dict[str, Any]],
    high_threshold: float,
    low_threshold: float,
) -> Dict[str, Any]:
    if not scored_chunks:
        return {"action": "incorrect", "top_relevance": 0.0, "avg_top3_relevance": 0.0}

    relevances = sorted((item["relevance"] for item in scored_chunks), reverse=True)
    top = relevances[0]
    top3 = relevances[:3]
    avg_top3 = sum(top3) / max(1, len(top3))

    if top >= high_threshold and avg_top3 >= low_threshold:
        action = "correct"
    elif top < low_threshold and avg_top3 < low_threshold:
        action = "incorrect"
    else:
        action = "ambiguous"

    return {
        "action": action,
        "top_relevance": round(top, 4),
        "avg_top3_relevance": round(avg_top3, 4),
    }


async def refine_chunks_for_query(
    query: str,
    chunks: List[KnowledgeChunk],
    max_strips: int = 10,
    min_similarity: float = 0.55,
) -> List[str]:
    if not chunks:
        return []

    candidate_strips: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        strips = split_into_strips(chunk.content, max_chars=260)
        source_weight = 1.0 - (idx / max(1, len(chunks)))
        for strip in strips:
            if strip:
                candidate_strips.append({"text": strip, "source_weight": source_weight})

    # Deduplicate while preserving order
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in candidate_strips:
        key = re.sub(r"\s+", " ", item["text"].strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= 40:
            break

    if not deduped:
        return []

    query_vec = await generate_embedding(query)
    strip_texts = [item["text"] for item in deduped]
    strip_vectors = await generate_embeddings(strip_texts)

    scored: List[tuple[float, float, str]] = []
    for meta, vec in zip(deduped, strip_vectors):
        semantic = _cosine_similarity(query_vec, vec)
        combined = (0.75 * semantic) + (0.25 * meta["source_weight"])
        scored.append((semantic, combined, meta["text"]))

    filtered = [item for item in scored if item[0] >= min_similarity]
    if not filtered:
        filtered = sorted(scored, key=lambda x: x[1], reverse=True)[: max(3, max_strips // 2)]
    else:
        filtered = sorted(filtered, key=lambda x: x[1], reverse=True)

    return [item[2] for item in filtered[:max_strips]]


async def ingest_text(
    db: AsyncSession,
    text: str,
    user_id: UUID,
    category: str = "whatsapp_knowledge",
    source_type: str = "whatsapp_upload",
) -> tuple[int, Optional[str]]:
    """
    Take raw text, split into chunks, embed, and save to knowledge_chunks.
    Returns (ingested_count, first_error_if_any).
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        if text.strip():
            chunks = [text.strip()]
        else:
            return 0, None
    elif len(lines) <= 3 or len(text) < 200:
        chunks = [text.strip()] if text.strip() else []
    else:
        chunks = []
        current_chunk: List[str] = []
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

    error_logs: List[str] = []
    ingested = 0
    for chunk_text in chunks:
        try:
            embedding = await generate_embedding(chunk_text)
            db.add(
                KnowledgeChunk(
                    user_id=user_id,
                    content=chunk_text,
                    embedding=embedding,
                    category=category,
                    source_type=source_type,
                    confidence_score=1.0,
                )
            )
            ingested += 1
        except Exception as exc:
            logger.warning("Skipped chunk ingestion", error=str(exc))
            error_logs.append(str(exc))

    if ingested > 0:
        await db.commit()
        logger.info("Ingested knowledge chunks", user_id=str(user_id), ingested=ingested)

    return ingested, (error_logs[0] if error_logs else None)
