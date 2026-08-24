"""
Pydantic models for API request/response contracts.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field
import uuid


# --- Session Models ---

class SessionCreate(BaseModel):
    """Request to create a new chat session."""
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    """Response for a single session."""
    id: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionListResponse(BaseModel):
    """Response for listing sessions."""
    sessions: list[SessionResponse]


# --- Message Models ---

class CitedSource(BaseModel):
    """A source citation from a transcript chunk."""
    episode_title: str
    guest: str
    publish_date: Optional[str] = None
    youtube_url: Optional[str] = None
    section_timestamp: Optional[str] = None
    content_preview: str = ""


class MessageResponse(BaseModel):
    """A single chat message."""
    id: str
    session_id: str
    role: str  # "user", "assistant"
    content: str
    cited_sources: list[CitedSource] = Field(default_factory=list)
    artifact: Optional[dict[str, Any]] = None  # {type: "markdown"|"html", content: str, title: str}
    created_at: datetime


class SessionDetailResponse(BaseModel):
    """Response for a session with its messages."""
    id: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    messages: list[MessageResponse] = Field(default_factory=list)


# --- Chat Models ---

class ChatRequest(BaseModel):
    """Request to send a chat message."""
    session_id: str
    message: str


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    message: MessageResponse
    provider: str  # which LLM provider handled this


# --- Health Models ---

class HealthResponse(BaseModel):
    """System health check response."""
    status: str  # "healthy", "degraded", "unhealthy"
    database: str  # "connected", "disconnected"
    ollama: str  # "connected", "disconnected", "not_configured"
    llm_provider: str
    version: str = "0.1.0"


# --- Error Models ---

class ErrorResponse(BaseModel):
    """Structured error response."""
    error: str
    detail: Optional[str] = None
    code: str = "internal_error"
