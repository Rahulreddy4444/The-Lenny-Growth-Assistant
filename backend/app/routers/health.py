"""
Health check endpoint.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from backend.app.config import get_settings, Settings
from backend.app.database import get_db
from backend.app.models import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Check system health: database, Ollama, and LLM provider status."""
    # Check database
    db_status = "disconnected"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    # Check Ollama
    ollama_status = "not_configured"
    if settings.llm_provider == "ollama" or True:  # Always check Ollama since it's used for embeddings
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{settings.ollama_base_url}/api/tags")
                ollama_status = "connected" if resp.status_code == 200 else "disconnected"
        except Exception as e:
            ollama_status = "disconnected"
            logger.warning(f"Ollama health check failed: {e}")

    # Overall status
    if db_status == "connected":
        if settings.llm_provider == "ollama" and ollama_status != "connected":
            overall = "degraded"
        else:
            overall = "healthy"
    else:
        overall = "unhealthy"

    return HealthResponse(
        status=overall,
        database=db_status,
        ollama=ollama_status,
        llm_provider=settings.llm_provider,
    )
