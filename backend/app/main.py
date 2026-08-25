"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.database import init_db
from backend.app.routers import health, sessions, chat

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — init DB on startup."""
    logger.info("Starting The Lenny Growth Assistant backend...")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    try:
        await init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.error(f"Database init failed (safe to ignore if tables exist): {e}")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="The Lenny Growth Assistant",
    description="RAG-powered Q&A grounded in Lenny's Podcast transcripts",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Single-user app, no auth
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(chat.router)
