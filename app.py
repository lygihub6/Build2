# --- Imports ---------------------------------------------------------------
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import streamlit as st                 # Streamlit
from PIL import Image                  # Image display

# Google GenAI SDK (per your guidelines)
from google import genai               # Google GenAI SDK
from google.genai import types         # Tools (e.g., Google Search), configs


# --- Page Config -----------------------------------------------------------
st.set_page_config(
    page_title="Sylvia — Learning Facilitator",
    page_icon="🎓",
    layout="wide",
)


# --- CSS: Match the provided screenshot -----------------------------------
MOCKUP_CSS = """
<style>
:root{
  --bg:#E8F5E9; --ink:#0D2B12; --muted:#5f7466; --brand:#1B5E20;
  --brand-700:#164a19; --brand-800:#0f3712; --card:#ffffff; --ring:#0f9159;
}
html, body, .stApp { background: var(--bg) !important; color: var(--ink); font-size:16px; }
.block-container { padding-top: 1.2rem; padding-bottom: 2rem; }

/* Header */
.header-card{ background:var(--card); border-radius:20px; padding:24px 28px;
  box-shadow:0 6px 18px rgba(0,0,0,.08); margin-bottom:18px; }
.header-title{ color:var(--brand); font-size:28px; font-weight:800; display:flex; gap:10px; align-items:center; }
.header-sub{ color:var(--muted); font-size:17px; }

/* Cards */
.card{ background:var(--card); border-radius:20px; padding:22px; box-shadow:0 6px 18px rgba(0,0,0,.08); margin-bottom:16px; }
.section-title{ display:flex; align-items:center; gap:10px; color:var(--brand); font-size:24px; font-weight:800; margin:0 0 14px 0; }
.section-title.small{ font-size:20px; }

/* Left Quick Actions (all st.button) */
.stButton>button{ background:var(--brand)!important; color:#fff!important; border:0; border-radius:12px; padding:14px 16px;
  font-weight:700; transition:all .2s ease; width:100%; margin-bottom:10px; }
.stButton>button:hover{ background:var(--brand-700)!important; transform:translateY(-1px); box-shadow:0 5px 20px rgba(27,94,32,.25); }

/* Chat */
.chat-wrap{ display:flex; flex-direction:column; gap:12px; }
.messages{ background:#f0f9f2; border-radius:16px; padding:18px; min-height:420px; max-height:520px;
  overflow-y:auto; border:1px solid #d4eed8; }
.msg{ margin-bottom:14px; padding:14px 16px; border-radius:16px; max-width:70ch; line-height:1.55; font-size:16px; }
.msg.assistant{ background:var(--brand); color:#fff; border-bottom-left-radius:6px; width:fit-content; }
.msg.user{ background:#d4eed8; color:var(--ink); margin-left:auto; border-bottom-right-radius:6px; width:fit-content; }

/* Input row */
.input-row{ display:grid; grid-template-columns:1fr 120px; gap:12px; margin-top:12px; }
.stTextInput>div>div>input{ padding:14px 16px; border:2px solid #d4eed8; border-radius:999px; font-size:16px; }
.stTextInput>div>div>input:focus{ border-color:var(--ring); box-shadow:0 0 0 3px rgba(15,145,89,.12); }
.input-row .stButton>button{ background:var(--brand)!important; color:#fff!important; border-radius:999px; padding:12px 20px; font-weight:800; }
.input-row .stButton>button:hover{ background:var(--brand-700)!important; }

/* Stats */
.stat-box{ background:#f7fbf8; padding:16px; border-radius:16px; text-align:center; border:1px solid #e0f0e5; margin-bottom:12px; }
.stat-box h4{ color:var(--brand); font-size:34px; margin:0 0 6px 0; font-weight:800; }
.stat-box p{ color:var(--muted); margin:0; font-size:14px; }
.progress{ background:#d4eed8; height:8px; border-radius:10px; overflow:hidden; margin-top:8px; }
.progress>div{ background:var(--brand); height:8px; width:75%; }

/* Recent sessions (thick green scrollbar look for preview; list kept short in app) */
.recent{ max-height:380px; overflow-y:auto; padding-right:6px; }
.recent::-webkit-scrollbar{ width:10px; }
.recent::-webkit-scrollbar-track{ background:#e9f6ec; border-radius:12px; }
.recent::-webkit-scrollbar-thumb{ background:var(--brand); border-radius:12px; }
.recent::-webkit-scrollbar-thumb:hover{ background:var(--brand-700); }
.session-item{ background:#f0f9f2; border-left:6px solid var(--brand); border-radius:12px; padding:12px 14px; margin-bottom:10px; }
.session-item h4{ margin:0 0 4px 0; color:var(--ink); font-size:16px; font-weight:800; }
.session-item p{ margin:0; color:var(--muted); font-size:14px; }
</style>
"""
st.markdown(MOCKUP_CSS, unsafe_allow_html=True)


# --- Secrets ---------------------------------------------------------------
import streamlit as st, re
API_KEY = st.secrets.get("GEMINI_API_KEY","")

st.write({
    "present": bool(API_KEY),
    "looks_like_ai_studio": API_KEY.startswith("AIza"),
    "length": len(API_KEY),
    "has_whitespace": bool(re.search(r"\s", API_KEY)),
})

# --- Identity / System Instructions ---------------------------------------
def load_developer_prompt() -> str:
    try:
        with open("identity.txt", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        st.warning("⚠️ 'identity.txt' not found. Using default prompt.")
        return (
            "You are Sylvia, a supportive self-regulated learning facilitator. "
            "Help the learner set mastery goals, analyze tasks, choose strategies, plan time, "
            "reflect, and build agency—step by step. Keep responses concise and encouraging."
        )

system_instructions = load_developer_prompt()


# --- Session State ---------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages: List[Dict[str, str]] = [
        {
            "role": "assistant",
            "content": (
                "Hello! I'm Sylvia, your learning facilitator. I'm here to help you develop effective "
                "learning strategies and achieve your academic goals through self-regulated learning. "
                "What task are you working on today?"
            ),
        }
    ]
if "sessions" not in st.session_state:
    st.session_state.sessions: Dict[str, Dict[str, Any]] = {}
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
if "session_start_ts" not in st.session_state:
    st.session_state.session_start_ts = time.time()
if "goals_count" not in st.session_state:
    st.session_state.goals_count = 0
if "coach_mode" not in st.session_state:
    st.session_state.coach_mode: Optional[str] = None


# --- Silent Coaching Prompts (Optional enhancement) ------------------------
COACH_PROMPTS = {
    "goal": (
        "SRL coaching: Help the learner articulate 1–3 mastery goals (SMART-ish). "
        "Ask what they want to learn or master beyond ‘finishing the assignment’. "
        "Negotiate 1–2 observable criteria of success. Close by asking them to confirm."
    ),
    "taskanalysis": (
        "SRL coaching: Prompt for task requirements, rubric, due date, and constraints. "
        "Elicit prior knowledge and uncertainties. Summarize a short actionable plan."
    ),
    "strategies": (
        "SRL coaching: Offer 3–5 tailored strategies for the task, time available, and goals. "
        "Ask the learner to pick 1–2 to try first and specify when to start."
    ),
    "motivation": (
        "SRL coaching: Brief value/interest reframe. Ask what matters to them and why. "
        "Suggest a 2-minute starter step to build momentum."
    ),
    "timelog": (
        "SRL coaching: Log time-on-task, propose a realistic schedule (e.g., Pomodoro), "
        "and negotiate the next 25-minute block with a concrete micro-goal."
    ),
    "resources": (
        "SRL coaching: With the learner’s permission, suggest 3–5 credible, level-appropriate "
        "resources aligned to goals. Summarize why each is helpful."
    ),
    "reflection": (
        "SRL coaching: Prompt reflection on outcomes, strategies, obstacles, emotions, effort. "
        "Extract 1 insight and 1 improvement for next time."
    ),
    "feedback": (
        "SRL coaching: Model an effective feedback request. Offer a short checklist "
        "the learner can use before submission."
    ),
    "save": (
        "SRL coaching: Write a concise session summary: goals, steps taken, time used, "
        "takeaways, next step. Then confirm saving."
    ),
}


# --- Header ---------------------------------------------------------------
with st.container():
    st.markdown(
        """
        <div class="header-card">
          <div class="header-title">🎓 Sylvia</div>
          <div class="header-sub">
            Your personal learning facilitator, designed to help you develop mastery goals, effective learning strategies,
            and self-regulated learning capacities for deep, meaningful learning.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- Layout: 3 columns (left actions, center chat, right sidebar) ----------
col_left, col_center, col_right = st.columns([0.95, 2, 1.05], gap="large")


# --- Left: Quick Actions ---------------------------------------------------
with col_left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🚀 Quick Actions</div>', unsafe_allow_html=True)

    def qa(label: str, mode: str, seed: str) -> None:
        if st.button(label, key=f"qa_{mode}"):
            st.session_state.coach_mode = mode
            st.session_state.messages.append({"role": "assistant", "content": seed})

    qa("🎯 Set Learning Goals", "goal",
       "Let’s set 1–3 mastery goals for this task. What do you want to learn or master?")
    qa("📋 Analyze Task", "taskanalysis",
       "Share the task requirements, rubric, due date, and any constraints.")
    qa("💡 Learning Strategies", "strategies",
       "I can propose several strategies. Tell me your timeline and where you usually get stuck.")
    qa("⚡ Get Motivated", "motivation",
       "What about this task matters to you (or your future self)?")
    qa("⏱️ Time Management", "timelog",
       "How much time do you have today? We can plan a focused 25-minute block.")
    qa("📚 Find Resources", "resources",
       "Want me to suggest a few credible resources aligned with your goals?")
    qa("🤔 Reflect on Learning", "reflection",
       "How did it go so far? What worked, what didn’t, and what will you change?")
    qa("💬 Request Feedback", "feedback",
       "What kind of feedback do you want: clarity, structure, evidence, or tone?")
    qa("💾 Save Session", "save",
       "I’ll summarize this session and save it. Anything you want to highlight first?")

    if st.button("➕ New Session", key="qa_new_session"):
        sid = st.session_state.current_session_id
        st.session_state.sessions[sid] = {
            "id": sid,
            "created": sid,
            "messages": list(st.session_state.messages),
            "goals_count": st.session_state.goals_count,
            "elapsed_sec": int(time.time() - st.session_state.session_start_ts),
            "title": f"Session {sid}",
        }
        st.session_state.current_session_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        st.session_state.messages = [
            {"role": "assistant", "content": "New session started. What would you like to work on?"}
        ]
        st.session_state.session_start_ts = time.time()
        st.session_state.goals_count = 0
        st.session_state.coach_mode = None

    st.markdown("</div>", unsafe_allow_html=True)


# --- Center: Chat Area -----------------------------------------------------
with col_center:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">💬 Learning Conversation</div>', unsafe_allow_html=True)

    # Message bubbles inside scrollable chat canvas
    st.markdown('<div class="chat-wrap"><div class="messages">', unsafe_allow_html=True)
    for m in st.session_state.messages:
        role_class = "assistant" if m["role"] == "assistant" else "user"
        st.markdown(f'<div class="msg {role_class}">{m["content"]}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Input row
    st.markdown('<div class="input-row">', unsafe_allow_html=True)
    user_text = st.text_input("Type your message", label_visibility="collapsed", key="user_text")
    send_clicked = st.button("Send", key="send_btn")
    st.markdown("</div>", unsafe_allow_html=True)

    # Advanced options
    with st.expander("Advanced"):
        temperature = st.slider("Temperature", 0.0, 2.0, 1.0, 0.1)
        max_tokens = st.slider("Max output tokens", 256, 4096, 2048, 64)
        use_search_tool = st.checkbox("Enable Google Search grounding (optional)", value=False)
        show_system_info = st.checkbox("Show identity.txt diagnostics", value=False)
        if show_system_info:
            st.caption("identity.txt status:")
            st.write(f"Characters: {len(system_instructions)}")
            st.code(
                system_instructions[:400]
                + ("\n...\n" if len(system_instructions) > 400 else "")
                + system_instructions[-400:]
            )

    # Gemini call helper
    def call_model(user_message: str, coach_mode: Optional[str]) -> str:
        if not client:
            return "Model not initialized—set GEMINI_API_KEY in Streamlit secrets."

        tools = []
        if use_search_tool:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        generation_cfg = types.GenerateContentConfig(
            system_instruction=system_instructions,
            tools=tools if tools else None,
            thinking_config=types.ThinkingConfig(thinking_budget=-1),  # dynamic thinking
            temperature=temperature,
            max_output_tokens=int(max_tokens),
        )

        # Prepare parts: (optional) coach prompt + truncated transcript + new user message
        parts: List[types.Part] = []
        if coach_mode and coach_mode in COACH_PROMPTS:
            parts.append(types.Part(text=f"[Coach Instruction]\n{COACH_PROMPTS[coach_mode]}"))

        recent_msgs = st.session_state.messages[-16:]
        for msg in recent_msgs:
            prefix = "User: " if msg["role"] == "user" else "Assistant: "
            parts.append(types.Part(text=f"{prefix}{msg['content']}"))

        parts.append(types.Part(text=f"User: {user_message}"))

        try:
            resp = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=[types.Content(parts=parts)],
                config=generation_cfg,
            )
            text = getattr(resp, "text", None)
            if not text and hasattr(resp, "candidates") and resp.candidates:
                for c in resp.candidates:
                    if getattr(c, "content", None) and c.content and getattr(c.content, "parts", None):
                        for p in c.content.parts:
                            if getattr(p, "text", None):
                                return p.text
            return text or "(No text response)"
        except Exception as e:
            return f"Model call failed: {e}"

    # Handle send
    if send_clicked and user_text.strip():
        msg = user_text.strip()
        st.session_state.messages.append({"role": "user", "content": msg})
        # simple heuristic to bump goals count when in goal mode
        if "goal" in (st.session_state.coach_mode or "") and any(
            k in msg.lower() for k in ["goal", "learn", "master", "my goal"]
        ):
            st.session_state.goals_count += 1

        assistant_text = call_model(msg, st.session_state.coach_mode)
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        st.session_state.coach_mode = None
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# --- Right: Current Session + Recent Sessions ------------------------------
with col_right:
    # Current Session
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title small">📊 Current Session</div>', unsafe_allow_html=True)
    elapsed_sec = int(time.time() - st.session_state.session_start_ts)
    expected_min = 60  # placeholder expectation
    st.markdown(
        f"""
        <div class="stat-box">
          <h4>{int(elapsed_sec/60)}m / {expected_min}m</h4>
          <p>Time Used / Expected</p>
          <div class="progress"><div style="width:{min(100, int((elapsed_sec/60)/expected_min*100))}%"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="stat-box">
          <h4>{st.session_state.goals_count}</h4>
          <p>Goals Set</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # Recent Sessions (stacked under stats)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title small">🗂️ Recent Sessions</div>', unsafe_allow_html=True)

    if not st.session_state.sessions:
        st.caption("No archived sessions yet. Use **Save Session** or **New Session**.")
    else:
        # Limit visible items so the sidebar stays compact like the screenshot
        items = sorted(st.session_state.sessions.values(), key=lambda x: x["id"], reverse=True)[:8]
        st.markdown('<div class="recent">', unsafe_allow_html=True)
        for s in items:
            c1, c2 = st.columns([0.7, 0.3])
            with c1:
                st.markdown(
                    f"""
                    <div class="session-item">
                      <h4>{s.get('title','(Untitled)')}</h4>
                      <p>{s['id']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with c2:
                if st.button("Load", key=f"load_{s['id']}"):
                    st.session_state.current_session_id = s["id"]
                    st.session_state.messages = s["messages"]
                    st.session_state.goals_count = s.get("goals_count", 0)
                    st.session_state.session_start_ts = time.time()
                    st.session_state.coach_mode = None
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


# --- Save Session helper ---------------------------------------------------
def save_current_session():
    sid = st.session_state.current_session_id
    st.session_state.sessions[sid] = {
        "id": sid,
        "created": sid,
        "messages": list(st.session_state.messages),
        "goals_count": st.session_state.goals_count,
        "elapsed_sec": int(time.time() - st.session_state.session_start_ts),
        "title": f"Session {sid}",
    }


# If last action was "save", auto-save and confirm in the chat
if st.session_state.coach_mode == "save":
    save_current_session()
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": "✅ Session saved. Download from **Export / Utilities** (Advanced) or load it later in **Recent Sessions**.",
        }
    )
    st.session_state.coach_mode = None
