"""
Session management endpoints.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.database import get_db
from backend.app.db.models import Session, Message
from backend.app.models import (
    SessionCreate,
    SessionResponse,
    SessionListResponse,
    SessionDetailResponse,
    MessageResponse,
    CitedSource,
    ErrorResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_to_response(session: Session) -> SessionResponse:
    return SessionResponse(
        id=str(session.id),
        created_at=session.created_at,
        metadata=session.metadata_ or {},
    )


def _message_to_response(msg: Message) -> MessageResponse:
    cited = []
    if msg.cited_sources:
        for src in msg.cited_sources:
            cited.append(CitedSource(**src))
    return MessageResponse(
        id=str(msg.id),
        session_id=str(msg.session_id),
        role=msg.role,
        content=msg.content,
        cited_sources=cited,
        artifact=msg.artifact,
        created_at=msg.created_at,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new chat session."""
    session = Session(metadata_=body.metadata or {})
    db.add(session)
    await db.commit()
    await db.refresh(session)
    logger.info(f"Created session: {session.id}")
    return _session_to_response(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all chat sessions, most recent first."""
    result = await db.execute(
        select(Session).order_by(Session.created_at.desc())
    )
    sessions = result.scalars().all()
    return SessionListResponse(
        sessions=[_session_to_response(s) for s in sessions]
    )


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get a session with all its messages."""
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.messages))
        .where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionDetailResponse(
        id=str(session.id),
        created_at=session.created_at,
        metadata=session.metadata_ or {},
        messages=[_message_to_response(m) for m in session.messages],
    )
