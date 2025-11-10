# --- Imports ---------------------------------------------------------------
import os
import io
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import streamlit as st                 # Streamlit
from PIL import Image                  # Image display

# Google GenAI SDK (modern)
try:
    from google import genai               # Google GenAI SDK
    from google.genai import types         # configs & tools
except Exception as _e:
    genai = None
    types = None


# --- Page Config -----------------------------------------------------------
st.set_page_config(
    page_title="Sylvia – Learning Facilitator",
    page_icon="🎓",
    layout="wide",
)


# --- Secrets ---------------------------------------------------------------
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not API_KEY:
    st.warning("⚠️ 'GEMINI_API_KEY' is not set in st.secrets. Add it before deploying.")
if genai:
    client = genai.Client(api_key=API_KEY) if API_KEY else None
else:
    client = None


# --- Identity / System Instructions ---------------------------------------
@st.cache_data(show_spinner=False)
def load_developer_prompt() -> str:
    try:
        with open("identity.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.warning("⚠️ 'identity.txt' not found. Using default prompt.")
        return (
            "You are Sylvia, a supportive learning facilitator. "
            "Use SRL framing: goals → task analysis → strategies → time plan → resources → reflect → feedback."
        )

SYSTEM_PROMPT = load_developer_prompt()


# --- Session State ---------------------------------------------------------
def _init_state():
    ss = st.session_state
    ss.setdefault("chat_history", [])          # list of {role, content}
    ss.setdefault("files", [])                 # list of {"name": str, "bytes": int, "mime": str}
    ss.setdefault("ground_search", False)      # UI checkbox
    ss.setdefault("use_code_exec", False)
    ss.setdefault("progress_pct", 0)
    ss.setdefault("path_step", 1)
    ss.setdefault("sessions_dir", "sessions")
    # Timer
    ss.setdefault("timer_minutes", 25)
    ss.setdefault("timer_running", False)
    ss.setdefault("timer_start_ts", 0.0)
    ss.setdefault("timer_elapsed", 0)
    ss.setdefault("time_log", [])
    ss.setdefault("_pending_action", None)

_init_state()


# --- “Silent” Action Nudges -----------------------------------------------
ACTION_PROMPTS = {
    "goal": "SILENT_ACTION: User pressed Goals. Help define 1–2 mastery goals. Ask ONE short follow-up question.",
    "taskanalysis": "SILENT_ACTION: User pressed Task Analysis. Identify prior knowledge, constraints, success criteria. Ask ONE clarifier.",
    "learning strategies": "SILENT_ACTION: User pressed Learning Strategies. Suggest 3 concrete strategies tied to their goal.",
    "time management": "SILENT_ACTION: User pressed Time Management. Offer a 25–5 Pomodoro micro-plan and a ≤2 min next step.",
    "resources": "SILENT_ACTION: User pressed Resources. Suggest 3 targeted resource types. If search is enabled, cite likely sources.",
    "reflection": "SILENT_ACTION: User pressed Reflect. Prompt reflection on goals met, obstacles, strategies tried, emotion, effort (≤4 bullets).",
    "feedback": "SILENT_ACTION: User pressed Feedback. Provide 2 strengths + 2 growth points; give one concrete refinement.",
}

def compose_turn(user_text: str, action_key: Optional[str], filenames: List[str]) -> List[types.Content]:
    """
    Build the full contents list for generate_content using chat history
    plus a single new turn that may include a silent action nudge and file names.
    This avoids fragile file-data APIs and keeps first run reliable.
    """
    # Convert history
    contents: List[types.Content] = []
    for msg in st.session_state.chat_history:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    # Compose the current user turn
    current_parts = []
    if action_key and action_key in ACTION_PROMPTS:
        current_parts.append(types.Part(text=f"[INTERNAL_COACHING]\n{ACTION_PROMPTS[action_key]}"))
    if filenames:
        current_parts.append(types.Part(text=f"[FILES]\nAttached: {', '.join(filenames[:10])}"))
    if user_text.strip():
        current_parts.append(types.Part(text=user_text.strip()))

    contents.append(types.Content(parts=current_parts))
    return contents


# --- CSS (faithful to your palette) ---------------------------------------
CSS = """
<style>
:root{
  --bg:#E8F5E9; --ink:#0D2B12; --muted:#5f7466; --brand:#1B5E20;
  --brand-700:#164a19; --brand-800:#0f3712; --card:#ffffff; --ring:#0f9159;
  --border:#B5DFB0; --accent:#10b981; --surface-alt:#C8E6C9;
}
html, body, .stApp { background: var(--bg); }
.block-container { padding-top: 0.75rem; padding-bottom: 0.75rem; }

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
  padding:10px 14px; font-weight:600; color:#1e293b;
}
.chat-scroll{
  flex:1 1 auto; overflow-y:auto; padding: 14px;
  background: linear-gradient(to bottom, #E8F5E9, #E8F5E9);
}
.bubble{
  max-width: 65ch; padding:10px 14px; border-radius:14px;
  margin-bottom: 10px; line-height:1.45; font-size: 0.96rem;
}
.user .bubble{ background: var(--brand); color:#fff; margin-left:auto; border-bottom-right-radius:6px; }
.assistant .bubble{ background: var(--surface-alt); border:1px solid var(--border); color:#0f172a; border-bottom-left-radius:6px; }
.meta{ font-size: 12px; color:#94a3b8; margin-top:-4px; margin-bottom: 6px; }

.chat-input-wrap{ border-top:1px solid var(--border); padding:10px; background:#fff; }

/* Cards */
.side-card{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,.06);
  margin-bottom: 12px;
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
.chips{ display:flex; flex-wrap:wrap; gap:6px; margin:6px 0; }
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


# --- Layout ---------------------------------------------------------------
left, center, right = st.columns([0.9, 1.8, 0.9], gap="medium")


# ================= LEFT: Actions + Timer + Uploads ========================
with left:
    st.markdown('<div class="side-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">Learning Actions</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    if c1.button("🎯 Goals", use_container_width=True): st.session_state._pending_action, st.session_state.path_step = "goal", 1
    if c2.button("📊 Task Analysis", use_container_width=True): st.session_state._pending_action, st.session_state.path_step = "taskanalysis", 2
    c3, c4 = st.columns(2)
    if c3.button("💡 Strategies", use_container_width=True): st.session_state._pending_action, st.session_state.path_step = "learning strategies", 3
    if c4.button("⏱️ Time", use_container_width=True): st.session_state._pending_action, st.session_state.path_step = "time management", 4
    c5, c6 = st.columns(2)
    if c5.button("📚 Resources", use_container_width=True): st.session_state._pending_action, st.session_state.path_step = "resources", 5
    if c6.button("🤔 Reflect", use_container_width=True): st.session_state._pending_action = "reflection"
    if st.button("💬 Feedback", use_container_width=True): st.session_state._pending_action = "feedback"

    st.divider()
    st.markdown('<div class="card-title">Process Monitor</div>', unsafe_allow_html=True)

    # timer presets
    p1, p2, p3 = st.columns(3)
    if p1.button("25m", use_container_width=True): st.session_state.timer_minutes = 25
    if p2.button("15m", use_container_width=True): st.session_state.timer_minutes = 15
    if p3.button("5m", use_container_width=True): st.session_state.timer_minutes = 5

    # timer display (step-updated)
    def fmt(sec: int) -> str:
        m, s = sec // 60, sec % 60
        return f"{m:02d}:{s:02d}"

    if st.session_state.timer_running:
        st.session_state.timer_elapsed = int(time.time() - st.session_state.timer_start_ts)

    total = st.session_state.timer_minutes * 60
    remain = max(0, total - st.session_state.timer_elapsed)

    st.caption("Timer")
    st.subheader(fmt(remain))

    t1, t2, t3 = st.columns(3)
    if t1.button("Start", use_container_width=True, disabled=st.session_state.timer_running):
        st.session_state.timer_running = True
        st.session_state.timer_start_ts = time.time() - st.session_state.timer_elapsed
    if t2.button("Pause", use_container_width=True, disabled=not st.session_state.timer_running):
        st.session_state.timer_running = False
        st.session_state.timer_elapsed = int(time.time() - st.session_state.timer_start_ts)
    if t3.button("Reset", use_container_width=True):
        st.session_state.timer_running = False
        st.session_state.timer_elapsed = 0

    if remain == 0 and st.session_state.timer_running:
        st.session_state.timer_running = False
        st.session_state.timer_elapsed = 0
        st.session_state.time_log.append(
            {"minutes": st.session_state.timer_minutes, "label": "Focused block", "ended_at": datetime.utcnow().isoformat()}
        )
        st.session_state._pending_action = "reflection"
        st.success("Pomodoro complete! Logged a focused block.")

    if st.session_state.time_log:
        st.caption("Today’s time log")
        for item in reversed(st.session_state.time_log[-5:]):
            st.markdown(f"- **{item['minutes']}m** · {item['label']} · {item['ended_at'].split('T')[0]}")

    st.divider()
    st.markdown('<div class="card-title">📎 Upload Materials</div>', unsafe_allow_html=True)

    files = st.file_uploader(
        "Drop or choose files (PDF/DOCX/TXT/Images)",
        type=["pdf", "doc", "docx", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    if files:
        for f in files:
            # store only meta for now; keeps first-run bulletproof
            pos = f.tell()
            data = f.read()
            f.seek(pos)
            st.session_state.files.append({"name": f.name, "bytes": len(data), "mime": f.type or "application/octet-stream"})
        st.success(f"Added {len(files)} file(s) to context (names shared with the model).")

    if st.session_state.files:
        st.caption("Attached (names only):")
        st.markdown("".join([f"<span class='file-pill'>🗂️ {f['name']}</span>" for f in st.session_state.files[-10:]]), unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ================= CENTER: Chat ===========================================
with center:
    # Top switches + URL context
    top = st.container()
    with top:
        cA, cB, cC = st.columns([1, 1, 2])
        st.session_state.ground_search = cA.checkbox("🔎 Search grounding", value=st.session_state.ground_search)
        st.session_state.use_code_exec = cB.checkbox("🧮 Code execution", value=st.session_state.use_code_exec)
        url_context = cC.text_input("Optional URL context (paste one per line or leave blank)", value="", placeholder="https://example.com/article …")

    # Chat card
    st.markdown('<div class="chat-card">', unsafe_allow_html=True)
    st.markdown('<div class="chat-head">Chat with Sylvia</div>', unsafe_allow_html=True)

    # Seed assistant greeting
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({"role": "assistant", "content": "Hello! I’m Sylvia. What are you working on today?"})

    # Scroll area
    scroll = st.container()
    with scroll:
        st.markdown('<div class="chat-scroll">', unsafe_allow_html=True)
        for msg in st.session_state.chat_history:
            cls = "assistant" if msg["role"] == "assistant" else "user"
            st.markdown(f"<div class='{cls}'><div class='bubble'>{msg['content']}</div></div>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Input area (kept inside the card)
    with st.form("chat_form", clear_on_submit=True):
        st.markdown('<div class="chat-input-wrap">', unsafe_allow_html=True)
        user_text = st.text_area("Type your message…", height=90, label_visibility="collapsed")
        submitted = st.form_submit_button("Send", type="primary", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Handle send
    if submitted and user_text.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        assistant_text = "(Model unavailable) Please add GEMINI_API_KEY in Secrets and install requirements."

        if client:
            try:
                # Build tools (optional) – we won't pass fragile objects; model still benefits from instruction
                tools = []
                if st.session_state.ground_search:
                    tools.append(types.Tool(google_search=types.GoogleSearch()))
                if st.session_state.use_code_exec:
                    tools.append(types.Tool(code_execution=types.CodeExecution()))

                # Compose contents (history + current turn)
                contents = compose_turn(
                    user_text=user_text,
                    action_key=st.session_state._pending_action,
                    filenames=[f["name"] for f in st.session_state.files],
                )

                # Generate
                resp = client.models.generate_content(
                    model="gemini-flash-lite-latest",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=tools if tools else None,
                        temperature=0.9,
                        max_output_tokens=2048,
                    ),
                )
                assistant_text = getattr(resp, "text", "") or "(No text response)"
            except Exception as e:
                assistant_text = f"Model call failed: {e}"

        st.session_state.chat_history.append({"role": "assistant", "content": assistant_text})
        st.session_state.progress_pct = min(100, st.session_state.progress_pct + 5)
        st.session_state._pending_action = None
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)  # chat-card end


# ================= RIGHT: Path / Progress / Sessions ======================
with right:
    # Learning Path
    st.markdown('<div class="side-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📍 Learning Path</div>', unsafe_allow_html=True)
    steps = ["Goals", "Task Analysis", "Strategies", "Time Plan", "Resources"]
    for i, name in enumerate(steps, start=1):
        badge = "✓" if st.session_state.path_step > i else ("●" if st.session_state.path_step == i else str(i))
        st.markdown(f"- **{badge} {name}**")
    st.markdown('</div>', unsafe_allow_html=True)

    # Progress
    st.markdown('<div class="side-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎯 Progress</div>', unsafe_allow_html=True)
    st.write(f"Task Completion: **{st.session_state.progress_pct}%**")
    st.markdown(
        f'<div class="progress-outer"><div class="progress-inner" style="width:{st.session_state.progress_pct}%;"></div></div>',
        unsafe_allow_html=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # Sessions
    st.markdown('<div class="side-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📁 Session</div>', unsafe_allow_html=True)
    os.makedirs(st.session_state.sessions_dir, exist_ok=True)
    s1, s2 = st.columns(2)
    if s1.button("💾 Save Session", use_container_width=True):
        payload = {
            "ts": datetime.utcnow().isoformat(),
            "chat_history": st.session_state.chat_history,
            "files": st.session_state.files,
            "progress_pct": st.session_state.progress_pct,
            "path_step": st.session_state.path_step,
            "time_log": st.session_state.time_log,
        }
        fname = os.path.join(st.session_state.sessions_dir, f"session_{int(time.time())}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        st.success(f"Session saved: {os.path.basename(fname)}")
    if s2.button("🗑️ Clear", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.files = []
        st.session_state.progress_pct = 0
        st.session_state.path_step = 1
        st.session_state.time_log = []
        st.success("Cleared current session.")

    e1, e2 = st.columns(2)
    export_payload = json.dumps(
        {
            "chat_history": st.session_state.chat_history,
            "files": st.session_state.files,
            "progress_pct": st.session_state.progress_pct,
            "path_step": st.session_state.path_step,
            "time_log": st.session_state.time_log,
        }, ensure_ascii=False, indent=2
    ).encode("utf-8")
    e1.download_button("📤 Export JSON", export_payload, file_name="sylvia_session.json", mime="application/json", use_container_width=True)
    if e2.button("➕ New Session", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.progress_pct = 0
        st.session_state.path_step = 1
        st.session_state.time_log = []
        st.toast("Started a new session.", icon="✨")

    # Saved sessions list
    saved = sorted(
        (fn for fn in os.listdir(st.session_state.sessions_dir) if fn.endswith(".json")),
        key=lambda x: os.path.getmtime(os.path.join(st.session_state.sessions_dir, x)),
        reverse=True
    )[:5]
    if saved:
        st.markdown('<div class="card-title">📜 Saved</div>', unsafe_allow_html=True)
        for fn in saved:
            p = os.path.join(st.session_state.sessions_dir, fn)
            cL, cR = st.columns([0.65, 0.35])
            cL.markdown(f"- {fn}")
            if cR.button("Load", key=f"load_{fn}"):
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                st.session_state.chat_history = data.get("chat_history", [])
                st.session_state.files = data.get("files", [])
                st.session_state.progress_pct = data.get("progress_pct", 0)
                st.session_state.path_step = data.get("path_step", 1)
                st.session_state.time_log = data.get("time_log", [])
                st.success(f"Loaded {fn}")
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# --- Footer status ---------------------------------------------------------
with st.container():
    status = []
    status.append(("Model", "gemini-flash-lite-latest"))
    status.append(("Search", "ON" if st.session_state.ground_search else "OFF"))
    status.append(("CodeExec", "ON" if st.session_state.use_code_exec else "OFF"))
    status.append(("Files", f"{len(st.session_state.files)}"))
    st.caption(" | ".join([f"**{k}**: {v}" for k, v in status]))
