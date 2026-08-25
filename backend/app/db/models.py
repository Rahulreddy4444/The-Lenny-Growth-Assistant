"""
SQLAlchemy ORM models for sessions, messages, and transcript chunks.
"""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from backend.app.database import Base
from backend.app.config import get_settings

settings = get_settings()


class Session(Base):
    """Chat session."""
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata_ = Column("metadata", JSONB, default=dict)

    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    """Chat message within a session."""
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    cited_sources = Column(JSONB, default=list)
    artifact = Column(JSONB, nullable=True)  # {type, content, title}
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session", back_populates="messages")


class TranscriptChunk(Base):
    """Embedded transcript chunk for vector search."""
    __tablename__ = "transcript_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_hash = Column(Text, unique=True, nullable=False)
    episode_title = Column(Text, nullable=False)
    guest = Column(Text)
    publish_date = Column(Text)
    youtube_url = Column(Text)
    video_id = Column(Text)
    section_speaker = Column(Text)
    section_timestamp = Column(Text)
    chunk_index = Column(Integer)
    keywords = Column(ARRAY(Text))
    content = Column(Text, nullable=False)
    embedding = Column(Vector(settings.embedding_dim), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
