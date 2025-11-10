
# --- Imports ---------------------------------------------------------------
import os
import io
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import streamlit as st                 # Streamlit
from PIL import Image                  # Image display

# Google GenAI SDK (modern SDK with tools support)
from google import genai               # Google GenAI SDK
from google.genai import types         # Tools (e.g., Google Search), configs


# --- Page Config -----------------------------------------------------------
st.set_page_config(
    page_title="Sylvia – Learning Facilitator",
    page_icon="🎓",
    layout="wide",
)


# --- Secrets ---------------------------------------------------------------
# In Streamlit Cloud, define in Secrets: GEMINI_API_KEY = "yourapikey"
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not API_KEY:
    st.warning("⚠️ 'GEMINI_API_KEY' is not set in st.secrets. Add it before deploying.")
client = genai.Client(api_key=API_KEY)


# --- Identity / System Instructions ---------------------------------------
# Reads 'identity.txt' if present; otherwise uses a friendly default.
@st.cache_data(show_spinner=False)
def load_developer_prompt() -> str:
    try:
        with open("identity.txt", "r", encoding="utf-8") as f:  # <-- name must match exactly
            return f.read()
    except FileNotFoundError:
        st.warning("⚠️ 'identity.txt' not found. Using default prompt.")
        return (
            "You are Sylvia, a helpful learning facilitator. Be friendly, supportive, "
            "and provide clear, concise, SRL-framed responses."
        )

system_instructions = load_developer_prompt()


# --- Helpers: Session State -----------------------------------------------
def _init_state():
    ss = st.session_state
    ss.setdefault("chat_history", [])   # list of {"role": "user"|"assistant"|"system", "content": str}
    ss.setdefault("files", [])          # list of {"name": str, "id": str, "mime": str}
    ss.setdefault("use_search", False)  # toggle for Google Search grounding
    ss.setdefault("use_code_exec", False)  # toggle for code execution tool
    ss.setdefault("progress_pct", 0)    # right-panel progress bar percent
    ss.setdefault("path_step", 1)       # 1..5 goals->resources
    ss.setdefault("sessions_dir", "sessions")
    ss.setdefault("url_context", "")    # optional URL(s)
    # Timer / Pomodoro (simple, step-based)
    ss.setdefault("timer_minutes", 25)      # current target duration
    ss.setdefault("timer_running", False)
    ss.setdefault("timer_start_ts", 0.0)
    ss.setdefault("timer_elapsed", 0)       # seconds elapsed in current run
    ss.setdefault("time_log", [])           # list of {"minutes": int, "label": str, "ended_at": iso}

_init_state()


# --- Files API -------------------------------------------------------------
def upload_to_gemini(file: Any, display_name: str) -> Optional[Dict[str, str]]:
    """
    Upload a Streamlit file-like object to Gemini Files API and return a dict with id, name, mime.
    """
    try:
        # file is a UploadedFile with .read() and .type
        # We pass a bytes-like object via file=file
        b = file.read()
        f = io.BytesIO(b)
        uploaded = client.files.upload(file=f, display_name=display_name)
        return {"name": display_name, "id": uploaded.name, "mime": getattr(uploaded, "mime_type", "application/octet-stream")}
    except Exception as e:
        st.error(f"Upload failed for {display_name}: {e}")
        return None


# --- Tools (Optional): Search, Code Execution ------------------------------
def build_tools(enable_search: bool, enable_code_exec: bool):
    tools = []
    if enable_search:
        tools.append(types.Tool(google_search=types.GoogleSearch()))
    if enable_code_exec:
        # Exposes a sand-boxed python execution (Gemini Code Execution tool)
        tools.append(types.Tool(code_execution=types.CodeExecution()))
    return tools


# --- Silent Action Prompts -------------------------------------------------
ACTION_PROMPTS = {
    "goal": "SILENT_ACTION: The user pressed 'Goals'. Use SRL to help define 1-2 mastery goals. Ask exactly one short follow-up question. Keep it under 4 sentences.",
    "taskanalysis": "SILENT_ACTION: The user pressed 'Task Analysis'. Identify prior knowledge, task constraints, and success criteria. Ask one clarifying question.",
    "learning strategies": "SILENT_ACTION: The user pressed 'Learning Strategies'. Provide 3 concrete strategies tied to the stated goal and task. Ask one short check question.",
    "time management": "SILENT_ACTION: The user pressed 'Time Management'. Suggest a Pomodoro-based micro-plan (e.g., 25-5 cycles) and a tiny next step (≤2 minutes).",
    "resources": "SILENT_ACTION: The user pressed 'Resources'. Suggest 3 types of targeted resources. If Search is enabled, ground suggestions.",
    "reflection": "SILENT_ACTION: The user pressed 'Reflect'. Prompt reflection on goals met, obstacles, strategies tried, emotion, effort. Keep it to 4 compact bullets.",
    "feedback": "SILENT_ACTION: The user pressed 'Feedback'. Provide 2 strengths and 2 growth points based on the last messages. Offer one concrete refinement.",
    "save": "SILENT_ACTION: Summarize and bookmark key points from this chat turn for next time. Keep it in bullet notes.",
}

def compose_silent_nudge(action_key: Optional[str]) -> Optional[str]:
    if not action_key:
        return None
    return ACTION_PROMPTS.get(action_key)


# --- Generation Configuration ---------------------------------------------
def build_generation_config(enable_search: bool, enable_code_exec: bool) -> types.GenerateContentConfig:
    tools = build_tools(enable_search, enable_code_exec)
    return types.GenerateContentConfig(
        system_instruction=system_instructions,
        tools=tools if tools else None,
        thinking_config=types.ThinkingConfig(thinking_budget=-1),  # dynamic thinking
        temperature=0.9,
        max_output_tokens=2048,
    )


# --- URL Context -----------------------------------------------------------
def prepare_url_context(url_text: str) -> List[str]:
    """
    Accepts a multi-line string of URLs. Returns a list of cleaned URL strings.
    Gemini URL context feature can accept URLs to fetch page content.
    """
    urls = []
    for line in (url_text or "").splitlines():
        u = line.strip()
        if u and ("http://" in u or "https://" in u):
            urls.append(u)
    return urls


# --- Chat Call -------------------------------------------------------------
def call_model(
    user_text: str,
    action_key: Optional[str] = None,
    attach_files: Optional[List[Dict[str, str]]] = None,
    url_text: str = "",
) -> str:
    """
    Compose contents from chat history + optional silent nudge + user text.
    Attach files/URL context if provided. Return assistant text.
    """
    # Build parts list for this turn
    parts: List[types.Part] = []

    # 1) Optional silent action prompt
    nudge = compose_silent_nudge(action_key)
    if nudge:
        parts.append(types.Part(text=f"[INTERNAL_COACHING]\n{nudge}"))

    # 2) URL context (OPTIONAL)
    urls = prepare_url_context(url_text)
    for u in urls:
        try:
            parts.append(types.Part(inline_data=types.Blob(mime_type="text/url", data=u.encode("utf-8"))))
        except Exception:
            # Gracefully fall back to plain text
            parts.append(types.Part(text=f"URL_CONTEXT: {u}"))

    # 3) Files references (OPTIONAL)
    if attach_files:
        for f in attach_files:
            # The modern SDK accepts file references by name (id) in parts:
            # types.Part(file_data=types.FileData(file_uri=f["id"]))  # in some SDKs
            # Use generic file_data; fallback to text mention if needed
            try:
                parts.append(types.Part(file_data=types.FileData(file_uri=f["id"])))
            except Exception:
                parts.append(types.Part(text=f"[FILE_REF name={f['name']} id={f['id']}]"))

    # 4) The visible user text
    if user_text.strip():
        parts.append(types.Part(text=user_text.strip()))

    # 5) Historical context
    history_parts: List[types.Content] = []
    for msg in st.session_state.chat_history:
        role = msg.get("role")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "user":
            history_parts.append(types.Content(role="user", parts=[types.Part(text=content)]))
        elif role == "assistant":
            history_parts.append(types.Content(role="model", parts=[types.Part(text=content)]))
        elif role == "system":
            # We normally keep system outside the history, but include if present
            history_parts.append(types.Content(role="system", parts=[types.Part(text=content)]))

    # 6) Build config
    gen_cfg = build_generation_config(
        enable_search=st.session_state.use_search,
        enable_code_exec=st.session_state.use_code_exec,
    )

    # 7) Make the call
    try:
        resp = client.models.generate_content(
            model="gemini-flash-lite-latest",
            contents=history_parts + [types.Content(parts=parts)],
            config=gen_cfg,
        )
        return getattr(resp, "text", "") or "(No text response)"
    except Exception as e:
        st.error(f"Model call failed: {e}")
        return "I hit a problem reaching the model. Please try again."


# --- UI: CSS (mirrors your palette & layout) ------------------------------
CSS = """
<style>
:root{
  --bg:#E8F5E9; --ink:#0D2B12; --muted:#5f7466; --brand:#1B5E20;
  --brand-700:#164a19; --brand-800:#0f3712; --card:#ffffff; --ring:#0f9159;
  --border:#B5DFB0; --accent:#10b981; --surface-alt:#C8E6C9;
}
html, body, .stApp { background: var(--bg); }
.block-container { padding-top: 1rem; padding-bottom: 1rem; }

/* Header */
.header-box{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px 18px;
  box-shadow: 0 4px 12px rgba(0,0,0,.06);
  margin-bottom: 8px;
}
.header-title { font-size: 28px; font-weight: 800; color: var(--brand); }
.header-sub{ font-size: 13px; color:#64748b; }

/* Chat */
.chat-card{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  height: 70vh;
  display:flex; flex-direction:column;
  overflow:hidden;
  box-shadow: 0 8px 24px rgba(0,0,0,.06);
}
.chat-head{
  border-bottom:1px solid var(--border);
  padding:10px 14px;
  font-weight:600;
  color:#1e293b;
}
.chat-scroll{
  flex:1 1 auto;
  overflow-y:auto;
  padding: 14px;
  background: linear-gradient(to bottom, #E8F5E9, #E8F5E9);
}
.bubble{
  max-width: 65ch; padding:10px 14px; border-radius:14px;
  margin-bottom: 10px; line-height:1.45; font-size: 0.96rem;
}
.user .bubble{ background: var(--brand); color:#fff; margin-left:auto; border-bottom-right-radius:6px; }
.assistant .bubble{ background: var(--surface-alt); border:1px solid var(--border); color:#0f172a; border-bottom-left-radius:6px; }
.meta{ font-size: 12px; color:#94a3b8; margin-top:-4px; margin-bottom: 6px; }

.chat-input-wrap{
  border-top:1px solid var(--border); padding:8px 10px; background:#fff;
}
.small-btn{ font-size: 12px; padding:6px 10px; border-radius:8px; border:1px solid var(--border); background:#ffffff; }
.small-btn:hover{ background:#eef6ef; border-color: var(--brand); }

/* Cards */
.side-card{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,.06);
}
.card-title{
  font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: .06em;
  color:#64748b; margin-bottom: 8px;
}

/* Progress */
.progress-outer{ width:100%; height:6px; background:#d7efdb; border-radius:4px; overflow:hidden; }
.progress-inner{ height:6px; background: linear-gradient(90deg, var(--brand), #2E7D32); }

/* Upload list */
.file-pill{ font-size:12px; padding:6px 8px; border-radius:10px; border:1px solid var(--border); margin:2px; display:inline-flex; gap:6px; }

/* Chips bar */
.chips{ display:flex; flex-wrap:wrap; gap:6px; margin:6px 0 2px 0; }
.chip{ font-size:12px; padding:6px 10px; border:1px solid var(--border); border-radius:999px; background:#f7fff9; }
.chip:hover{ background:#e9f7ee; }

/* Footer status */
.status-pill{ display:inline-flex; gap:8px; align-items:center; font-size:12px; padding:6px 10px; border-radius:999px; border:1px solid var(--border); background:#fff; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# --- Header ---------------------------------------------------------------
with st.container():
    st.markdown(
        '<div class="header-box"><div class="header-title">🎓 Sylvia</div>'
        '<div class="header-sub">Your personal learning facilitator: goals → task analysis → strategies → time plan → resources → reflect → feedback.</div></div>',
        unsafe_allow_html=True
    )


# --- Layout: 3 columns (Left actions / Center chat / Right panels) --------
left, center, right = st.columns([0.9, 1.8, 0.9], gap="medium")


# ================== LEFT: Learning Actions & Uploads ======================
with left:
    st.markdown('<div class="side-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Learning Actions</div>', unsafe_allow_html=True)

    act_cols = st.columns(2)
    with act_cols[0]:
        if st.button("🎯 Goals", use_container_width=True, key="btn_goals"):
            st.session_state._pending_action = "goal"
            st.toast("Goals action armed—type or send to apply.", icon="🎯")
            st.session_state.path_step = 1
    with act_cols[1]:
        if st.button("📊 Task Analysis", use_container_width=True, key="btn_task"):
            st.session_state._pending_action = "taskanalysis"
            st.toast("Task Analysis action armed—type or send to apply.", icon="📊")
            st.session_state.path_step = 2

    act_cols2 = st.columns(2)
    with act_cols2[0]:
        if st.button("💡 Strategies", use_container_width=True, key="btn_strat"):
            st.session_state._pending_action = "learning strategies"
            st.toast("Strategies action armed—type or send to apply.", icon="💡")
            st.session_state.path_step = 3
    with act_cols2[1]:
        if st.button("⏱️ Time", use_container_width=True, key="btn_time"):
            st.session_state._pending_action = "time management"
            st.toast("Time Management action armed—type or send to apply.", icon="⏱️")
            st.session_state.path_step = 4

    act_cols3 = st.columns(2)
    with act_cols3[0]:
        if st.button("📚 Resources", use_container_width=True, key="btn_res"):
            st.session_state._pending_action = "resources"
            st.toast("Resources action armed—type or send to apply.", icon="📚")
            st.session_state.path_step = 5
    with act_cols3[1]:
        if st.button("🤔 Reflect", use_container_width=True, key="btn_ref"):
            st.session_state._pending_action = "reflection"
            st.toast("Reflection action armed—type or send to apply.", icon="📝")

    if st.button("💬 Feedback", use_container_width=True, key="btn_feedback"):
        st.session_state._pending_action = "feedback"
        st.toast("Feedback action armed—type or send to apply.", icon="💬")

    st.divider()

    # Process Monitor (Pomodoro-lite)
    st.markdown('<div class="card-title">Process Monitor</div>', unsafe_allow_html=True)
    timer_cols = st.columns([1, 1, 1])
    with timer_cols[0]:
        if st.button("25m", key="t25", use_container_width=True):
            st.session_state.timer_minutes = 25
    with timer_cols[1]:
        if st.button("15m", key="t15", use_container_width=True):
            st.session_state.timer_minutes = 15
    with timer_cols[2]:
        if st.button("5m", key="t05", use_container_width=True):
            st.session_state.timer_minutes = 5

    # Display timer
    def _format_mmss(seconds: int) -> str:
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"

    # Compute remaining (non-realtime; updates when user interacts)
    elapsed = 0
    if st.session_state.timer_running:
        elapsed = int(time.time() - st.session_state.timer_start_ts)
        st.session_state.timer_elapsed = elapsed

    target = st.session_state.timer_minutes * 60
    remain = max(0, target - st.session_state.timer_elapsed)

    st.caption("Timer")
    st.subheader(_format_mmss(remain))

    pm_cols = st.columns(3)
    with pm_cols[0]:
        if st.button("Start", key="tstart", use_container_width=True, disabled=st.session_state.timer_running):
            st.session_state.timer_running = True
            st.session_state.timer_start_ts = time.time() - st.session_state.timer_elapsed
            st.toast("Timer started.", icon="⏱️")
    with pm_cols[1]:
        if st.button("Pause", key="tpause", use_container_width=True, disabled=not st.session_state.timer_running):
            st.session_state.timer_running = False
            st.session_state.timer_elapsed = int(time.time() - st.session_state.timer_start_ts)
            st.toast("Timer paused.", icon="⏸️")
    with pm_cols[2]:
        if st.button("Reset", key="treset", use_container_width=True):
            st.session_state.timer_running = False
            st.session_state.timer_elapsed = 0
            st.toast("Timer reset.", icon="🔄")

    # Log a block when it hits zero (user-triggered check)
    if remain == 0 and st.session_state.timer_running:
        st.session_state.timer_running = False
        st.session_state.timer_elapsed = 0
        st.session_state.time_log.append(
            {"minutes": st.session_state.timer_minutes, "label": "Focused block", "ended_at": datetime.utcnow().isoformat()}
        )
        st.success("Pomodoro complete! Logged a focused block.")
        # small nudge to keep
