"""
Chat endpoint — receives user messages, orchestrates the agent, returns responses.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.config import get_settings, Settings
from backend.app.database import get_db
from backend.app.db.models import Session, Message
from backend.app.models import ChatRequest, ChatResponse, MessageResponse, CitedSource, ErrorResponse
from backend.app.services.agent import AgentService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        404: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Send a message and get an AI response grounded in Lenny's Podcast transcripts."""
    # Validate session exists
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.messages))
        .where(Session.id == body.session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save user message
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=body.message,
        cited_sources=[],
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Build conversation history
    history = []
    for msg in session.messages:
        history.append({"role": msg.role, "content": msg.content})
    # Add current user message
    history.append({"role": "user", "content": body.message})

    # Run agent
    try:
        agent = AgentService(settings)
        agent_response = await agent.run(history, db)
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=f"Agent error: {str(e)}",
        )

    # Save assistant message
    assistant_msg = Message(
        session_id=session.id,
        role="assistant",
        content=agent_response["content"],
        cited_sources=agent_response.get("cited_sources", []),
        artifact=agent_response.get("artifact"),
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    # Build response
    cited = [CitedSource(**src) for src in agent_response.get("cited_sources", [])]
    msg_response = MessageResponse(
        id=str(assistant_msg.id),
        session_id=str(assistant_msg.session_id),
        role="assistant",
        content=agent_response["content"],
        cited_sources=cited,
        artifact=agent_response.get("artifact"),
        created_at=assistant_msg.created_at,
    )

    return ChatResponse(
        message=msg_response,
        provider=settings.llm_provider,
    )
