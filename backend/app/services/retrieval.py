"""
Vector similarity search over transcript chunks in pgvector.
"""

import logging
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import TranscriptChunk
from backend.app.services.llm import FastEmbedService

logger = logging.getLogger(__name__)


async def search_transcripts(
    query: str,
    db: AsyncSession,
    embedding_service: FastEmbedService,
    top_k: int = 5,
) -> list[dict]:
    """
    Embed the query and perform cosine similarity search against transcript chunks.

    Returns a list of dicts with chunk content and metadata.
    """
    # Embed the query
    try:
        embeddings = await embedding_service.embed(query)
        query_embedding = embeddings[0]
    except Exception as e:
        logger.error(f"Failed to embed query: {e}")
        return []

    # Cosine similarity search using pgvector
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text(f"""
        SELECT
            id,
            episode_title,
            guest,
            publish_date,
            youtube_url,
            video_id,
            section_speaker,
            section_timestamp,
            chunk_index,
            content,
            1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM transcript_chunks
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT :top_k
    """)

    result = await db.execute(
        sql,
        {"embedding": embedding_str, "top_k": top_k},
    )
    rows = result.fetchall()

    chunks = []
    for row in rows:
        chunks.append({
            "id": row.id,
            "episode_title": row.episode_title,
            "guest": row.guest,
            "publish_date": row.publish_date,
            "youtube_url": row.youtube_url,
            "video_id": row.video_id,
            "section_speaker": row.section_speaker,
            "section_timestamp": row.section_timestamp,
            "chunk_index": row.chunk_index,
            "content": row.content,
            "similarity": float(row.similarity),
        })

    logger.info(f"Retrieved {len(chunks)} chunks for query: '{query[:80]}...'")
    return chunks
