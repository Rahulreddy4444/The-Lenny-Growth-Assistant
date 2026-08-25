"""
Tests for session persistence — CRUD operations on sessions and messages.
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSessionModels:
    """Test session-related model instantiation (unit tests, no DB)."""

    def test_session_response_model(self):
        from backend.app.models import SessionResponse
        from datetime import datetime

        resp = SessionResponse(
            id="test-id",
            created_at=datetime.now(),
            metadata={"key": "value"},
        )
        assert resp.id == "test-id"
        assert resp.metadata == {"key": "value"}

    def test_session_list_response(self):
        from backend.app.models import SessionListResponse, SessionResponse
        from datetime import datetime

        sessions = SessionListResponse(
            sessions=[
                SessionResponse(id="1", created_at=datetime.now()),
                SessionResponse(id="2", created_at=datetime.now()),
            ]
        )
        assert len(sessions.sessions) == 2

    def test_session_detail_with_messages(self):
        from backend.app.models import SessionDetailResponse, MessageResponse
        from datetime import datetime

        detail = SessionDetailResponse(
            id="session-1",
            created_at=datetime.now(),
            messages=[
                MessageResponse(
                    id="msg-1",
                    session_id="session-1",
                    role="user",
                    content="Hello",
                    created_at=datetime.now(),
                ),
                MessageResponse(
                    id="msg-2",
                    session_id="session-1",
                    role="assistant",
                    content="Hi there!",
                    created_at=datetime.now(),
                ),
            ],
        )
        assert len(detail.messages) == 2
        assert detail.messages[0].role == "user"
        assert detail.messages[1].role == "assistant"

    def test_session_delete_endpoint_defined(self):
        from backend.app.routers.sessions import delete_session
        import inspect
        assert inspect.iscoroutinefunction(delete_session)


class TestHTMLSanitization:
    """Test HTML sanitization — critical security verification."""

    def test_script_tag_stripped(self):
        import nh3
        html = '<div>Hello</div><script>alert("xss")</script>'
        clean = nh3.clean(html)
        assert "<script>" not in clean
        assert "alert" not in clean
        assert "Hello" in clean

    def test_onclick_stripped(self):
        import nh3
        html = '<div onclick="alert(1)">Click me</div>'
        clean = nh3.clean(html)
        assert "onclick" not in clean
        assert "Click me" in clean

    def test_iframe_stripped(self):
        import nh3
        html = '<iframe src="https://evil.com"></iframe><p>Safe</p>'
        clean = nh3.clean(html)
        assert "<iframe" not in clean
        assert "Safe" in clean

    def test_safe_html_preserved(self):
        import nh3
        html = '<h1>Title</h1><p>Paragraph with <strong>bold</strong></p>'
        clean = nh3.clean(html)
        assert "<h1>" in clean
        assert "<strong>" in clean
