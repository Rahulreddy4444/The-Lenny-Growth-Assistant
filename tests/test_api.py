"""
Tests for API contracts — status codes, response shapes, error handling.
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPydanticModels:
    """Test Pydantic model validation and serialization."""

    def test_session_create_default_metadata(self):
        from backend.app.models import SessionCreate
        session = SessionCreate()
        assert session.metadata == {}

    def test_session_create_with_metadata(self):
        from backend.app.models import SessionCreate
        session = SessionCreate(metadata={"name": "test"})
        assert session.metadata == {"name": "test"}

    def test_chat_request_validation(self):
        from backend.app.models import ChatRequest
        req = ChatRequest(session_id="abc-123", message="Hello")
        assert req.session_id == "abc-123"
        assert req.message == "Hello"

    def test_chat_request_missing_fields(self):
        from backend.app.models import ChatRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChatRequest(session_id="abc")  # missing message

    def test_health_response(self):
        from backend.app.models import HealthResponse
        health = HealthResponse(
            status="healthy",
            database="connected",
            ollama="connected",
            llm_provider="ollama",
        )
        assert health.status == "healthy"
        assert health.version == "0.1.0"

    def test_error_response(self):
        from backend.app.models import ErrorResponse
        err = ErrorResponse(error="Not found", detail="Session not found", code="not_found")
        assert err.error == "Not found"

    def test_cited_source_model(self):
        from backend.app.models import CitedSource
        src = CitedSource(
            episode_title="Test Episode",
            guest="Test Guest",
            publish_date="2024-01-01",
            youtube_url="https://youtube.com/watch?v=abc",
            content_preview="Some content...",
        )
        assert src.episode_title == "Test Episode"

    def test_message_response_with_artifact(self):
        from backend.app.models import MessageResponse
        from datetime import datetime
        msg = MessageResponse(
            id="123",
            session_id="456",
            role="assistant",
            content="Here is your essay",
            artifact={"type": "markdown", "title": "Essay", "content": "# Hello"},
            created_at=datetime.now(),
        )
        assert msg.artifact["type"] == "markdown"
