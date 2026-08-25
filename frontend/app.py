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
    page_title="Lenny Growth Assistant",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
    /* Typography and Spacing */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Main Chat Area adjustments */
    .block-container {
        padding-top: 5.5rem !important;
        padding-bottom: 5rem !important;
        max-width: 1400px;
    }

    header[data-testid="stHeader"] {
        background-color: transparent !important;
        pointer-events: none;
    }
    
    header[data-testid="stHeader"] > * {
        pointer-events: auto;
    }

    /* User Message Bubble */
    [data-testid="stChatMessage"] {
        padding: 1.5rem;
        border-radius: 0.75rem;
        margin-bottom: 1rem;
    }
    
    [data-testid="stChatMessage"][data-baseweb="card"] {
        background-color: transparent !important;
    }

    /* Target the user message container specifically if possible */
    [data-testid="chatAvatarIcon-user"] + div {
        background-color: rgba(128, 128, 128, 0.1);
        padding: 1rem 1.25rem;
        border-radius: 0.75rem;
        color: var(--text-color);
    }

    /* Assistant Typography */
    [data-testid="chatAvatarIcon-assistant"] + div p {
        line-height: 1.6;
        color: var(--text-color);
    }
    
    /* Session buttons */
    .stButton > button[kind="secondary"] {
        border: 1px solid transparent;
        background-color: transparent;
        color: var(--text-color);
        text-align: left;
        justify-content: flex-start;
        padding-left: 0.5rem;
        opacity: 0.8;
    }
    
    .stButton > button[kind="secondary"]:hover {
        background-color: rgba(128, 128, 128, 0.1);
        border-color: transparent;
        opacity: 1;
    }

    /* Artifact Viewer Title */
    .artifact-header {
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 1rem;
        color: var(--text-color);
        display: flex;
        align-items: center;
        gap: 0.5rem;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2);
        padding-bottom: 0.5rem;
    }

    .security-badge {
        font-size: 0.7rem;
        background-color: #dcfce7;
        color: #166534;
        padding: 0.1rem 0.5rem;
        border-radius: 1rem;
        font-weight: 500;
        margin-left: auto;
    }
    
    [data-theme="dark"] .security-badge {
        background-color: #064e3b;
        color: #34d399;
    }
    
    /* Citation Expander */
    [data-testid="stExpander"] {
        border-color: #e5e7eb;
        border-radius: 0.5rem;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    }
    
    [data-testid="stExpander"] summary {
        font-size: 0.85rem;
        color: #6b7280;
    }
    
    .citation-card {
        border-left: 3px solid #3b82f6;
        padding-left: 0.75rem;
        margin-bottom: 0.75rem;
    }
    
    .citation-title {
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.1rem;
    }
    
    .citation-meta {
        font-size: 0.8rem;
        color: #6b7280;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ── Helper functions ──────────────────────────────────────────────────────────

def api_call(method: str, path: str, **kwargs) -> dict | None:
    """Make an API call to the backend."""
    url = f"{BACKEND_URL}{path}"
    try:
        resp = getattr(requests, method)(url, timeout=300, **kwargs)
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


def delete_session(session_id: str) -> bool:
    """Delete a chat session."""
    return api_call("delete", f"/sessions/{session_id}") is not None


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

if "initial_prompt" not in st.session_state:
    st.session_state.initial_prompt = None


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
        st.markdown(f"<div style='font-size: 0.85rem; color: var(--text-color); opacity: 0.7; margin-bottom: 1rem;'>System: {status_emoji} &nbsp;|&nbsp; Provider: <strong>{health.get('llm_provider', 'unknown')}</strong></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='font-size: 0.85rem; color: #ef4444; margin-bottom: 1rem;'>Status: 🔴 Backend unreachable</div>", unsafe_allow_html=True)

    # New session button
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        result = create_session()
        if result:
            st.session_state.current_session_id = result["id"]
            st.session_state.messages = []
            st.session_state.current_artifact = None
            st.session_state.initial_prompt = None
            st.rerun()

    st.markdown("<h4 style='font-size: 0.9rem; color: var(--text-color); opacity: 0.9; margin-top: 1.5rem; margin-bottom: 0.5rem;'>Recent Chats</h4>", unsafe_allow_html=True)

    # Session list
    sessions = list_sessions()
    
    from datetime import datetime
    for sess in sessions:
        # Try to parse date nicely, fallback to raw
        try:
            dt = datetime.fromisoformat(sess['created_at'].replace('Z', '+00:00'))
            date_str = dt.strftime("%b %d, %H:%M")
        except:
            date_str = sess['created_at'][:16]
            
        label = f"💬 Chat ({date_str})"
        is_current = sess["id"] == st.session_state.current_session_id
        col_btn, col_del = st.columns([0.78, 0.22])
        with col_btn:
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
        with col_del:
            if st.button("🗑️", key=f"del_{sess['id']}", help="Delete this session", use_container_width=True):
                delete_session(sess["id"])
                if st.session_state.current_session_id == sess["id"]:
                    st.session_state.current_session_id = None
                    st.session_state.messages = []
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
    if not st.session_state.current_session_id:
        st.markdown("<h1 style='text-align: center; margin-top: 2rem; font-size: 2.5rem; color: var(--text-color);'>🎙️ Lenny Growth Assistant</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: var(--text-color); opacity: 0.7; margin-bottom: 3rem; font-size: 1.1rem;'>Explore product and growth insights from Lenny's Podcast transcripts, create essays, and generate reusable artifacts.</p>", unsafe_allow_html=True)
        
        st.markdown("<h3 style='text-align: center; margin-bottom: 1.5rem; font-size: 1.2rem; color: var(--text-color); opacity: 0.9;'>Try asking:</h3>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 4, 1])
        with col2:
            prompts = [
                "How do great products find product-market fit?",
                "What are effective user retention strategies?",
                "How should a startup prioritize features?",
                "Create a Ship 30 for 30 essay about product growth."
            ]
            for i, p in enumerate(prompts):
                if st.button(p, use_container_width=True, key=f"example_{i}"):
                    result = create_session()
                    if result:
                        st.session_state.current_session_id = result["id"]
                        st.session_state.messages = []
                        st.session_state.current_artifact = None
                        st.session_state.initial_prompt = p
                        st.rerun()
    else:
        # Display messages
        for i, msg in enumerate(st.session_state.messages):
            role = msg["role"]
            content = msg["content"]

            # Strip any <think> tags from historical or streaming output
            import re
            clean_display_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL | re.IGNORECASE)
            if clean_display_content.strip().startswith('<think>'):
                clean_display_content = re.sub(r'<think>.*?(?=\n\n|\n[#A-Z<]|$)', '', clean_display_content, flags=re.DOTALL | re.IGNORECASE)
            clean_display_content = clean_display_content.strip()
            if not clean_display_content and content.strip():
                clean_display_content = re.sub(r'</?think>', '', content, flags=re.IGNORECASE).strip()

            # Fallback artifact detection from content
            art = msg.get("artifact")
            if not art and role == "assistant" and "<artifact" in content:
                match = re.search(r'<artifact(?:\s+type=[\'"]?(\w+)[\'"]?)?(?:\s+title=[\'"]?([^\'">]*)[\'"]?)?[^>]*>(.*?)(?:</artifact>|$)', content, re.DOTALL | re.IGNORECASE)
                if match:
                    art = {
                        "type": match.group(1) or "markdown",
                        "title": match.group(2) or "Generated Essay",
                        "content": match.group(3).strip(),
                    }
                    clean_display_content = (
                        f"📄 **{art.get('title', 'Ship 30 for 30 Essay')}** has been generated! "
                        f"View the full essay in the **Artifact Viewer** panel on the right ➡️"
                    )

            with st.chat_message(role):
                st.markdown(clean_display_content)

                # Show citations for assistant messages
                if role == "assistant" and msg.get("cited_sources"):
                    with st.expander("📚 Sources"):
                        for src in msg["cited_sources"]:
                            yt_link = ""
                            if src.get("youtube_url"):
                                yt_link = f" &nbsp;•&nbsp; <a href='{src['youtube_url']}' target='_blank' style='color: #3b82f6; text-decoration: none;'>▶️ Watch</a>"
                            
                            st.markdown(f"""
                            <div class="citation-card">
                                <div class="citation-title">{src['episode_title']}</div>
                                <div class="citation-meta">with {src['guest']} &nbsp;•&nbsp; {src.get('publish_date', 'N/A')}{yt_link}</div>
                            </div>
                            """, unsafe_allow_html=True)

                # Show artifact button
                if role == "assistant" and art:
                    if st.button(
                        f"📄 Open in Artifact Viewer: {art.get('title', 'Artifact')}",
                        key=f"art_btn_{msg.get('id', i)}_{i}",
                        type="primary" if st.session_state.current_artifact == art else "secondary",
                    ):
                        st.session_state.current_artifact = art
                        st.rerun()

        # Chat input handling
        prompt = st.chat_input("Ask about product, growth, startups...")
        if st.session_state.initial_prompt:
            prompt = st.session_state.initial_prompt
            st.session_state.initial_prompt = None

        if prompt:
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

                    # Add to local state
                    st.session_state.messages.append(msg_data)

                    # Update provider info
                    st.session_state.provider = result.get("provider", st.session_state.provider)

                    # Auto-open artifact panel if artifact is present
                    if msg_data.get("artifact"):
                        st.session_state.current_artifact = msg_data["artifact"]

                    st.rerun()
                else:
                    st.warning("Oops! We couldn't get a response. Please try asking again.")

# ── Artifact Viewer ───────────────────────────────────────────────────────

if artifact_col and st.session_state.current_artifact:
    with artifact_col:
        artifact = st.session_state.current_artifact
        art_type = artifact.get("type", "markdown")
        art_content = artifact.get("content", "")

        # Header with security badge
        st.markdown(f"""
        <div class="artifact-header">
            📄 {artifact.get('title', 'Artifact')}
            <span class="security-badge">Rendered safely</span>
        </div>
        """, unsafe_allow_html=True)

        # Action toolbar: Download and Close buttons (Claude Artifacts style)
        col_dl, col_close = st.columns([1, 1])
        with col_dl:
            ext = ".html" if art_type == "html" else ".md"
            mime = "text/html" if art_type == "html" else "text/markdown"
            safe_title = "".join(c for c in artifact.get("title", "artifact") if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            st.download_button(
                label=f"⬇️ Download {ext}",
                data=art_content,
                file_name=f"{safe_title}{ext}",
                mime=mime,
                use_container_width=True,
                type="primary",
            )
        with col_close:
            if st.button("✖ Close", use_container_width=True):
                st.session_state.current_artifact = None
                st.rerun()

        st.markdown("---")

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
