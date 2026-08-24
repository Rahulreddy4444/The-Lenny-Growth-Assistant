"""
The Lenny Growth Assistant — Streamlit Frontend

Features:
- Chat UI with st.chat_message / st.chat_input
- Session management sidebar
- Artifact viewer (Markdown + sanitized HTML) 
- Provider display in sidebar
"""

import json
import streamlit as st
import requests
import nh3
import os

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Page config
st.set_page_config(
    page_title="The Lenny Growth Assistant",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Helper functions ──────────────────────────────────────────────────────────

def api_call(method: str, path: str, **kwargs) -> dict | None:
    """Make an API call to the backend."""
    url = f"{BACKEND_URL}{path}"
    try:
        resp = getattr(requests, method)(url, timeout=120, **kwargs)
        if resp.status_code >= 400:
            st.error(f"API Error ({resp.status_code}): {resp.text}")
            return None
        return resp.json()
    except requests.ConnectionError:
        st.error(f"Cannot connect to backend at {BACKEND_URL}. Is the backend running?")
        return None
    except Exception as e:
        st.error(f"API Error: {e}")
        return None


def get_health() -> dict | None:
    """Check backend health."""
    return api_call("get", "/health")


def create_session() -> dict | None:
    """Create a new chat session."""
    return api_call("post", "/sessions", json={"metadata": {}})


def list_sessions() -> list:
    """List all sessions."""
    data = api_call("get", "/sessions")
    return data.get("sessions", []) if data else []


def get_session(session_id: str) -> dict | None:
    """Get session with messages."""
    return api_call("get", f"/sessions/{session_id}")


def send_message(session_id: str, message: str) -> dict | None:
    """Send a chat message."""
    return api_call("post", "/chat", json={
        "session_id": session_id,
        "message": message,
    })


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML using nh3 — strips scripts, event handlers, iframes."""
    return nh3.clean(
        html_content,
        tags={
            "h1", "h2", "h3", "h4", "h5", "h6",
            "p", "br", "hr",
            "strong", "em", "b", "i", "u", "s", "mark",
            "ul", "ol", "li",
            "table", "thead", "tbody", "tr", "th", "td",
            "blockquote", "pre", "code",
            "a", "img",
            "div", "span",
            "details", "summary",
        },
        attributes={
            "a": {"href", "title"},
            "img": {"src", "alt", "width", "height"},
            "td": {"colspan", "rowspan"},
            "th": {"colspan", "rowspan"},
            "*": {"class", "style"},
        },
    )


# ── Session State Initialization ─────────────────────────────────────────────

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_artifact" not in st.session_state:
    st.session_state.current_artifact = None

if "provider" not in st.session_state:
    st.session_state.provider = "unknown"


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🎙️ Lenny Growth Assistant")
    st.markdown("---")

    # Health check & provider display
    health = get_health()
    if health:
        st.session_state.provider = health.get("llm_provider", "unknown")
        status_emoji = {"healthy": "🟢", "degraded": "🟡", "unhealthy": "🔴"}.get(
            health.get("status"), "⚪"
        )
        st.markdown(f"**Status:** {status_emoji} {health.get('status', 'unknown').title()}")
        st.markdown(f"**Provider:** `{health.get('llm_provider', 'unknown')}`")
        st.markdown(f"**Database:** {health.get('database', 'unknown')}")
        st.markdown(f"**Ollama:** {health.get('ollama', 'unknown')}")
    else:
        st.markdown("**Status:** 🔴 Backend unreachable")

    st.markdown("---")
    st.markdown("### Sessions")

    # New session button
    if st.button("➕ New Session", use_container_width=True):
        result = create_session()
        if result:
            st.session_state.current_session_id = result["id"]
            st.session_state.messages = []
            st.session_state.current_artifact = None
            st.rerun()

    # Session list
    sessions = list_sessions()
    for sess in sessions:
        label = f"💬 {sess['created_at'][:16]}"
        is_current = sess["id"] == st.session_state.current_session_id
        if st.button(
            label,
            key=f"sess_{sess['id']}",
            use_container_width=True,
            type="primary" if is_current else "secondary",
        ):
            st.session_state.current_session_id = sess["id"]
            # Load messages
            detail = get_session(sess["id"])
            if detail:
                st.session_state.messages = detail.get("messages", [])
                # Check for any artifact in last message
                if st.session_state.messages:
                    last = st.session_state.messages[-1]
                    if last.get("artifact"):
                        st.session_state.current_artifact = last["artifact"]
                    else:
                        st.session_state.current_artifact = None
            st.rerun()

    st.markdown("---")
    st.markdown(
        "<small>Powered by Lenny's Podcast transcripts.<br>"
        "Not affiliated with Lenny Rachitsky.</small>",
        unsafe_allow_html=True,
    )


# ── Main Content ─────────────────────────────────────────────────────────────

# Determine layout based on whether artifact is visible
if st.session_state.current_artifact:
    chat_col, artifact_col = st.columns([3, 2])
else:
    chat_col = st.container()
    artifact_col = None

# ── Chat Panel ────────────────────────────────────────────────────────────

with chat_col:
    st.markdown("# 🎙️ The Lenny Growth Assistant")
    st.markdown(
        f"*Ask product & growth questions grounded in Lenny's Podcast transcripts. "
        f"Provider: **{st.session_state.provider}***"
    )

    if not st.session_state.current_session_id:
        st.info("👈 Create a new session to start chatting.")
    else:
        # Display messages
        for msg in st.session_state.messages:
            role = msg["role"]
            content = msg["content"]

            with st.chat_message(role):
                st.markdown(content)

                # Show citations for assistant messages
                if role == "assistant" and msg.get("cited_sources"):
                    with st.expander("📚 Sources"):
                        for src in msg["cited_sources"]:
                            yt_link = ""
                            if src.get("youtube_url"):
                                yt_link = f" [▶️ Watch]({src['youtube_url']})"
                            st.markdown(
                                f"- **{src['episode_title']}** "
                                f"with {src['guest']}"
                                f" ({src.get('publish_date', 'N/A')})"
                                f"{yt_link}"
                            )

                # Show artifact button
                if role == "assistant" and msg.get("artifact"):
                    if st.button(
                        f"📄 View: {msg['artifact'].get('title', 'Artifact')}",
                        key=f"art_{msg['id']}",
                    ):
                        st.session_state.current_artifact = msg["artifact"]
                        st.rerun()

        # Chat input
        if prompt := st.chat_input("Ask about product, growth, startups..."):
            # Display user message immediately
            with st.chat_message("user"):
                st.markdown(prompt)

            # Add to local state
            st.session_state.messages.append({
                "role": "user",
                "content": prompt,
                "cited_sources": [],
                "id": "pending",
            })

            # Send to backend
            with st.chat_message("assistant"):
                with st.spinner("Searching transcripts and thinking..."):
                    result = send_message(
                        st.session_state.current_session_id,
                        prompt,
                    )

                if result:
                    msg_data = result["message"]
                    st.markdown(msg_data["content"])

                    # Show citations
                    if msg_data.get("cited_sources"):
                        with st.expander("📚 Sources"):
                            for src in msg_data["cited_sources"]:
                                yt_link = ""
                                if src.get("youtube_url"):
                                    yt_link = f" [▶️ Watch]({src['youtube_url']})"
                                st.markdown(
                                    f"- **{src['episode_title']}** "
                                    f"with {src['guest']}"
                                    f" ({src.get('publish_date', 'N/A')})"
                                    f"{yt_link}"
                                )

                    # Handle artifact
                    if msg_data.get("artifact"):
                        st.session_state.current_artifact = msg_data["artifact"]
                        if st.button(
                            f"📄 View: {msg_data['artifact'].get('title', 'Artifact')}",
                            key="new_artifact",
                        ):
                            st.rerun()

                    # Add to local state
                    st.session_state.messages.append(msg_data)

                    # Update provider info
                    st.session_state.provider = result.get("provider", st.session_state.provider)
                else:
                    st.error("Failed to get a response. Please try again.")

# ── Artifact Viewer ───────────────────────────────────────────────────────

if artifact_col and st.session_state.current_artifact:
    with artifact_col:
        artifact = st.session_state.current_artifact

        st.markdown(f"### 📄 {artifact.get('title', 'Artifact')}")

        # Close button
        if st.button("✖ Close Artifact"):
            st.session_state.current_artifact = None
            st.rerun()

        art_type = artifact.get("type", "markdown")
        art_content = artifact.get("content", "")

        if art_type == "markdown":
            st.markdown(art_content)

        elif art_type == "html":
            # Sanitize HTML server-side using nh3
            sanitized = sanitize_html(art_content)

            # Show if sanitization changed anything
            if sanitized != art_content:
                st.warning("⚠️ Unsafe HTML elements were removed for security.")

            st.components.v1.html(sanitized, height=600, scrolling=True)

        else:
            st.code(art_content, language=art_type)
