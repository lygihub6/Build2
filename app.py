# --- Imports ---------------------------------------------------------------
import os
import json
import time
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

import streamlit as st                 # Streamlit
from PIL import Image                  # Image display

# Google GenAI SDK (per guideline)
from google import genai               # Google GenAI SDK
from google.genai import types         # Tools (e.g., Google Search), configs

# --- Page Config -----------------------------------------------------------
st.set_page_config(page_title="Sylvia — Learning Facilitator", page_icon="🎓", layout="wide")

# --- CSS: Theme based on provided mockup -----------------------------------
MOCKUP_CSS = """
<style>
:root {
  --bg: #E8F5E9;
  --ink: #0D2B12;
  --muted: #5f7466;
  --brand: #1B5E20;
  --brand-700: #164a19;
  --brand-800: #0f3712;
  --card: #ffffff;
  --ring: #0f9159;
}

/* Streamlit base */
html, body, .stApp {
  background: var(--bg) !important;
  color: var(--ink);
  font-size: 16px; /* enforce min 16px body */
}

/* Cards */
.block-container {
  padding-top: 1.2rem;
  padding-bottom: 2rem;
}

/* Header card mimic */
.header-card {
  background: var(--card);
  border-radius: 20px;
  padding: 24px 28px;
  box-shadow: 0 6px 18px rgba(0,0,0,.08);
  margin-bottom: 18px;
}
.header-title {
  color: var(--brand); 
  font-size: 28px;     /* H1 ~28px */
  display: flex; 
  align-items: center; 
  gap: 10px;
  margin: 0 0 6px 0;
}
.header-sub {
  color: var(--muted);
  font-size: 17px;
}

/* Cards */
.card {
  background: var(--card);
  border-radius: 15px;
  padding: 18px;
  box-shadow: 0 6px 18px rgba(0,0,0,.08);
  margin-bottom: 16px;
}

/* Section titles */
.card h3, .card h2, .card h4 {
  color: var(--brand);
  margin: 0 0 12px 0;
}
h2 { font-size: 22px; } /* H2 ~22px */
h3 { font-size: 18px; } /* H3 ~18px */

/* Buttons */
.stButton>button {
  background: var(--brand) !important;
  color: #fff !important;
  border: 0;
  border-radius: 10px;
  padding: 10px 16px;
  font-weight: 600;
  transition: all .2s ease;
}
.stButton>button:hover {
  background: var(--brand-700) !important;
  transform: translateY(-1px);
  box-shadow: 0 5px 20px rgba(27, 94, 32, 0.25);
}

/* Quick Actions grid look */
.quick-btn {
  width: 100%;
  text-align: left;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 10px;
  padding: 12px 14px;
  margin-bottom: 8px;
  background: var(--brand);
  color: #fff !important;
  font-weight: 600;
}
.quick-btn:hover { background: var(--brand-700); }
.quick-btn small { opacity: .9; font-weight: 400; }

/* Chat area */
.chat-wrap {
  display: flex; 
  flex-direction: column; 
  gap: 12px;
}
.messages {
  background: var(--bg);
  border-radius: 10px;
  padding: 14px;
  height: 440px;
  overflow-y: auto;
  border: 1px solid #d4eed8;
}
.msg {
  margin-bottom: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  max-width: 85%;
  line-height: 1.55;
  font-size: 16px;
}
.msg.assistant {
  background: var(--brand);
  color: #fff;
  margin-right: auto;
  border-bottom-left-radius: 6px;
}
.msg.user {
  background: #d4eed8;
  color: var(--ink);
  margin-left: auto;
  border-bottom-right-radius: 6px;
}

/* Input row */
.input-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
}

/* Stats */
.stat-box {
  background: var(--bg);
  padding: 12px;
  border-radius: 10px;
  text-align: center;
  border: 1px solid #d4eed8;
}
.stat-box h4 {
  color: var(--brand);
  font-size: 20px;
  margin: 0 0 4px 0;
}
.stat-box p {
  color: var(--muted);
  margin: 0;
  font-size: 14px;
}
.progress {
  background: #d4eed8;
  height: 8px;
  border-radius: 10px;
  overflow: hidden;
  margin-top: 8px;
}
.progress > div {
  background: var(--brand);
  height: 8px;
  width: 65%;
}

/* Recent sessions list */
.session-item {
  background: var(--bg);
  border-left: 4px solid var(--brand);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
  cursor: pointer;
}
.session-item:hover { background: #d4eed8; }
.session-item h4 {
  margin: 0 0 4px 0;
  color: var(--ink);
  font-size: 16px;
}
.session-item p {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}

/* Advanced expander text size guard */
.css-1v3fvcr p, .css-1v3fvcr li { font-size: 16px !important; }
</style>
"""
st.markdown(MOCKUP_CSS, unsafe_allow_html=True)

# --- Secrets ---------------------------------------------------------------
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not API_KEY:
    st.warning("⚠️ 'GEMINI_API_KEY' is not set in st.secrets. Add it before deploying.")

# Client
client = genai.Client(api_key=API_KEY) if API_KEY else None

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
        {"role": "assistant", "content": "Hello! I’m Sylvia. What task are you working on today?"}
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
    st.session_state.coach_mode: Optional[str] = None  # active quick action

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
            Your personal learning facilitator, designed to help you develop mastery goals, effective learning strategies, and self-regulated learning capacities for deep, meaningful learning.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --- Layout: 3 columns -----------------------------------------------------
col_left, col_center, col_right = st.columns([0.9, 2, 0.9], gap="large")

# --- Left: Quick Actions ---------------------------------------------------
with col_left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🚀 Quick Actions", unsafe_allow_html=True)

    def qa_btn(label: str, key: str, help_text: str = "") -> bool:
        return st.button(f"{label}", key=key, help=help_text, use_container_width=True)

    # Map buttons to coach modes
    quick_actions = [
        ("🎯 Set Learning Goals", "goal"),
        ("📋 Analyze Task", "taskanalysis"),
        ("💡 Learning Strategies", "strategies"),
        ("⚡ Get Motivated", "motivation"),
        ("⏱️ Time Log / Plan", "timelog"),
        ("📚 Find Resources", "resources"),
        ("🤔 Reflect on Learning", "reflection"),
        ("💬 Request Feedback", "feedback"),
        ("💾 Save Session", "save"),
    ]
    for label, mode in quick_actions:
        if qa_btn(label, f"qa_{mode}"):
            st.session_state.coach_mode = mode
            # Lightweight assistant prompt to guide next turn
            assistant_seed = {
                "goal": "Let’s set 1–3 mastery goals for this task. What do you really want to learn or master?",
                "taskanalysis": "Tell me the task requirements, due date, rubric (if any), and any constraints.",
                "strategies": "I can propose several strategies. Tell me your timeline and where you usually get stuck.",
                "motivation": "What about this task matters to you (or your future self)?",
                "timelog": "How much time do you have today? We can plan a focused 25-minute block.",
                "resources": "Want me to suggest a few credible resources aligned with your goals?",
                "reflection": "How did it go so far? What worked, what didn’t, and what will you change?",
                "feedback": "What kind of feedback do you want: clarity, structure, evidence, or tone?",
                "save": "I’ll summarize this session and save it. Anything you want to highlight first?",
            }[mode]
            st.session_state.messages.append({"role": "assistant", "content": assistant_seed})

    if qa_btn("➕ New Session", "qa_new_session"):
        # Archive current session
        sid = st.session_state.current_session_id
        st.session_state.sessions[sid] = {
            "id": sid,
            "created": sid,
            "messages": list(st.session_state.messages),
            "goals_count": st.session_state.goals_count,
            "elapsed_sec": int(time.time() - st.session_state.session_start_ts),
            "title": f"Session {sid}",
        }
        # Reset current
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
    st.markdown("## 💬 Learning Conversation", unsafe_allow_html=True)

    # Messages
    st.markdown('<div class="chat-wrap"><div class="messages">', unsafe_allow_html=True)
    for m in st.session_state.messages:
        role_class = "assistant" if m["role"] == "assistant" else "user"
        st.markdown(
            f'<div class="msg {role_class}">{m["content"]}</div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    # Input row
    with st.container():
        st.markdown('<div class="input-row">', unsafe_allow_html=True)
        user_text = st.text_input("Type your message", label_visibility="collapsed", key="user_text")
        send_clicked = st.button("Send", type="primary")
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
            st.code(system_instructions[:400] + ("\n...\n" if len(system_instructions) > 400 else "") + system_instructions[-400:])

    # --- Gemini Call Helper ------------------------------------------------
    def call_model(user_message: str, coach_mode: Optional[str]) -> str:
        """Send conversation to Gemini with optional silent coaching prompt."""
        if not client:
            return "Model not initialized—set GEMINI_API_KEY in Streamlit secrets."

        # Build tool list conditionally
        tools = []
        if use_search_tool:
            tools.append(types.Tool(google_search=types.GoogleSearch()))

        # Generation config (per guideline)
        generation_cfg = types.GenerateContentConfig(
            system_instruction=system_instructions,
            tools=tools if tools else None,
            thinking_config=types.ThinkingConfig(thinking_budget=-1),  # dynamic thinking
            temperature=temperature,
            max_output_tokens=int(max_tokens),
        )

        # Compose contents: (optional coach prompt) + conversation + last user message
        parts: List[types.Part] = []

        # Silent coaching (Optional section)
        if coach_mode and coach_mode in COACH_PROMPTS:
            parts.append(types.Part(text=f"[Coach Instruction]\n{COACH_PROMPTS[coach_mode]}"))

        # Include recent transcript (truncate to last ~16 turns for token safety)
        recent_msgs = st.session_state.messages[-16:]
        for msg in recent_msgs:
            prefix = "User: " if msg["role"] == "user" else "Assistant: "
            parts.append(types.Part(text=f"{prefix}{msg['content']}"))

        # Append the new user message
        parts.append(types.Part(text=f"User: {user_message}"))

        # Minimal call (non-streaming for SDK consistency)
        try:
            resp = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=[types.Content(parts=parts)],
                config=generation_cfg,
            )
            # Fallback if text is None
            text = getattr(resp, "text", None)
            if not text and hasattr(resp, "candidates") and resp.candidates:
                # Try to extract candidate text if available
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
        st.session_state.messages.append({"role": "user", "content": user_text.strip()})
        # Heuristic: if user sets goals, bump counter (simple detection)
        if "goal" in (st.session_state.coach_mode or "") and any(k in user_text.lower() for k in ["goal", "learn", "master", "my goal"]):
            st.session_state.goals_count += 1

        assistant_text = call_model(user_text.strip(), st.session_state.coach_mode)
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        st.session_state.coach_mode = None  # consume coach prompt
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Right: Stats + Sessions ----------------------------------------------
with col_right:
    # Stats
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📊 Current Session", unsafe_allow_html=True)
    elapsed_sec = int(time.time() - st.session_state.session_start_ts)
    expected_min = 60  # placeholder expectation
    used = f"{int(elapsed_sec/60)}m / {expected_min}m"
    st.markdown(
        f"""
        <div class="stat-box">
          <h4>{used}</h4>
          <p>Time Used / Expected</p>
          <div class="progress"><div style="width:{min(100, int((elapsed_sec/60)/expected_min*100))}%"></div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="stat-box" style="margin-top:10px">
          <h4>{st.session_state.goals_count}</h4>
          <p>Goals Set</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Export options
    with st.expander("Export / Utilities"):
        # Download transcript JSON
        sid = st.session_state.current_session_id
        transcript = {
            "id": sid,
            "created": sid,
            "messages": st.session_state.messages,
            "elapsed_sec": elapsed_sec,
            "goals_count": st.session_state.goals_count,
        }
        st.download_button(
            "Download transcript (JSON)",
            data=json.dumps(transcript, ensure_ascii=False, indent=2),
            file_name=f"sylvia_session_{sid}.json",
            mime="application/json",
            use_container_width=True,
        )
        # Download transcript as Markdown
        md_lines = [f"# Sylvia Session {sid}", ""]
        for m in st.session_state.messages:
            who = "🧑 User" if m["role"] == "user" else "🤖 Sylvia"
            md_lines.append(f"**{who}:** {m['content']}")
            md_lines.append("")
        st.download_button(
            "Download transcript (Markdown)",
            data="\n".join(md_lines),
            file_name=f"sylvia_session_{sid}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        if st.button("Clear chat"):
            st.session_state.messages = [{"role": "assistant", "content": "Chat cleared. What next?"}]
            st.session_state.coach_mode = None
            st.session_state.goals_count = 0
            st.session_state.session_start_ts = time.time()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # Recent Sessions
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📁 Recent Sessions", unsafe_allow_html=True)

    if not st.session_state.sessions:
        st.caption("No archived sessions yet. Use **Save Session** or **New Session**.")
    else:
        # Show up to 8 recent
        items = sorted(st.session_state.sessions.values(), key=lambda x: x["id"], reverse=True)[:8]
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
                    # Reset timer from now (we can't resume exact start reliably)
                    st.session_state.session_start_ts = time.time()
                    st.session_state.coach_mode = None
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# --- Save Session Action (when clicked) ------------------------------------
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

# If last action was "save", auto-save and confirm
if st.session_state.coach_mode == "save":
    save_current_session()
    st.session_state.messages.append(
        {"role": "assistant", "content": "✅ Session saved. You can download it from **Export / Utilities** or load it later in **Recent Sessions**."}
    )
    st.session_state.coach_mode = None
