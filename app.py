# --- Imports ---------------------------------------------------------------
import os
import streamlit as st
from PIL import Image
from google import genai
from google.genai import types
import json
from datetime import datetime, timedelta
import time

# --- Page Configuration ----------------------------------------------------
st.set_page_config(
    page_title="Sylvia - Learning Facilitator", 
    page_icon="📚", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Secrets ---------------------------------------------------------------
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
if not API_KEY:
    st.error("⚠️ 'GEMINI_API_KEY' is not set in st.secrets. Please add it before proceeding.")
    st.stop()

client = genai.Client(api_key=API_KEY)

# --- Identity / System Instructions ---------------------------------------
def load_developer_prompt() -> str:
    """Load the identity.txt file containing Sylvia's instructions"""
    try:
        with open("identity.txt") as f:
            return f.read()
    except FileNotFoundError:
        st.warning("⚠️ 'identity.txt' not found. Using default prompt.")
        return """You are Sylvia, a learning facilitator created by Yu. You help students set mastery learning goals, 
        plan effective learning strategies, and provide guidelines for their learning process and feedback for reflection.
        Follow the sequence: goals → task analysis → strategies → time plan → resources → reflect → feedback.
        Keep tone supportive, concise, and stepwise."""

system_instructions = load_developer_prompt()

# --- Generation Configuration ---------------------------------------------
generation_cfg = types.GenerateContentConfig(
    system_instruction=system_instructions,
    temperature=0.7,
    max_output_tokens=2048,
)

# --- Initialize Session State ----------------------------------------------
def init_session_state():
    """Initialize all session state variables"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'current_phase' not in st.session_state:
        st.session_state.current_phase = "Not Started"
    
    if 'learning_goals' not in st.session_state:
        st.session_state.learning_goals = []
    
    if 'task_info' not in st.session_state:
        st.session_state.task_info = ""
    
    if 'strategies' not in st.session_state:
        st.session_state.strategies = []
    
    if 'time_plan' not in st.session_state:
        st.session_state.time_plan = ""
    
    if 'reflections' not in st.session_state:
        st.session_state.reflections = []
    
    if 'session_start' not in st.session_state:
        st.session_state.session_start = datetime.now()
    
    if 'timer_running' not in st.session_state:
        st.session_state.timer_running = False
    
    if 'timer_start' not in st.session_state:
        st.session_state.timer_start = None
    
    if 'timer_duration' not in st.session_state:
        st.session_state.timer_duration = 25  # Default Pomodoro duration
    
    if 'saved_sessions' not in st.session_state:
        st.session_state.saved_sessions = []

init_session_state()

# --- Helper Functions ------------------------------------------------------
def get_phase_emoji(phase):
    """Return emoji for current learning phase"""
    emojis = {
        "Not Started": "🎯",
        "Goals": "🎯",
        "Task Analysis": "📋",
        "Strategies": "🧠",
        "Time Planning": "⏰",
        "Resources": "📚",
        "Working": "💪",
        "Reflection": "🤔",
        "Feedback": "✅"
    }
    return emojis.get(phase, "📝")

def format_time(seconds):
    """Format seconds to MM:SS"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{mins:02d}:{secs:02d}"

def save_session():
    """Save current session to session state"""
    session_data = {
        "timestamp": datetime.now().isoformat(),
        "goals": st.session_state.learning_goals,
        "task": st.session_state.task_info,
        "strategies": st.session_state.strategies,
        "time_plan": st.session_state.time_plan,
        "messages": st.session_state.messages[-10:],  # Save last 10 messages
        "reflections": st.session_state.reflections
    }
    st.session_state.saved_sessions.append(session_data)
    return session_data

def clear_session():
    """Clear current session data"""
    st.session_state.messages = []
    st.session_state.current_phase = "Not Started"
    st.session_state.learning_goals = []
    st.session_state.task_info = ""
    st.session_state.strategies = []
    st.session_state.time_plan = ""
    st.session_state.reflections = []
    st.session_state.session_start = datetime.now()

# --- Action Functions ------------------------------------------------------
def process_action(action_type, user_input=""):
    """Process specialized actions and generate appropriate prompts"""
    
    action_prompts = {
        "goal": f"""Help the student set mastery learning goals. Current input: '{user_input}'
                    Ask them to focus on what they want to learn and master, not just complete.
                    Guide them to be specific and measurable. Keep response concise and actionable.""",
        
        "taskanalysis": f"""Help analyze the task. Input: '{user_input}'
                            Ask about: 1) What they already know, 2) Task requirements, 
                            3) Key concepts to understand. Be specific and structured.""",
        
        "strategies": f"""Suggest learning strategies based on their goals and task. Context: '{user_input}'
                          Recommend 2-3 specific strategies like elaboration, practice testing, 
                          spaced repetition, etc. Explain briefly why each helps.""",
        
        "timemanagement": f"""Help plan study time. Context: '{user_input}'
                              Suggest time blocks, breaks, and realistic scheduling.
                              Recommend Pomodoro technique if appropriate.""",
        
        "timelog": f"""Help track time on task. Current status: '{user_input}'
                       Acknowledge their time tracking and suggest how to stay focused.""",
        
        "resources": f"""Suggest learning resources for: '{user_input}'
                        Recommend 2-3 specific types of resources and where to find them.""",
        
        "reflection": f"""Guide reflection on learning. Context: '{user_input}'
                         Ask about: Goals met? Time used effectively? Obstacles faced? 
                         Emotions? What worked? What to improve?""",
        
        "feedback": f"""Provide constructive feedback on: '{user_input}'
                       Acknowledge progress, identify strengths, suggest improvements.
                       Be specific and encouraging.""",
        
        "save": f"""Session saved. Summarize key points from: '{user_input}'
                   List main goals, strategies used, and next steps."""
    }
    
    return action_prompts.get(action_type, user_input)

# --- UI Components ---------------------------------------------------------
def render_sidebar():
    """Render the sidebar with tools and session management"""
    with st.sidebar:
        st.title("🎓 Learning Toolkit")
        
        # Progress Indicator
        st.markdown("### 📊 Current Phase")
        phase = st.session_state.current_phase
        st.info(f"{get_phase_emoji(phase)} **{phase}**")
        
        # Learning Workflow Actions
        st.markdown("### 🛠️ Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🎯 Set Goals", use_container_width=True):
                st.session_state.current_phase = "Goals"
                return "goal"
            
            if st.button("📋 Analyze Task", use_container_width=True):
                st.session_state.current_phase = "Task Analysis"
                return "taskanalysis"
            
            if st.button("🧠 Plan Strategies", use_container_width=True):
                st.session_state.current_phase = "Strategies"
                return "strategies"
            
            if st.button("⏰ Time Planning", use_container_width=True):
                st.session_state.current_phase = "Time Planning"
                return "timemanagement"
            
            if st.button("📚 Find Resources", use_container_width=True):
                st.session_state.current_phase = "Resources"
                return "resources"
        
        with col2:
            if st.button("⏱️ Log Time", use_container_width=True):
                return "timelog"
            
            if st.button("🤔 Reflect", use_container_width=True):
                st.session_state.current_phase = "Reflection"
                return "reflection"
            
            if st.button("✅ Get Feedback", use_container_width=True):
                st.session_state.current_phase = "Feedback"
                return "feedback"
            
            if st.button("💾 Save Session", use_container_width=True):
                save_session()
                st.success("Session saved!")
                return "save"
            
            if st.button("🗑️ Clear Session", use_container_width=True):
                clear_session()
                st.rerun()
        
        # Pomodoro Timer
        st.markdown("### ⏲️ Focus Timer")
        
        timer_col1, timer_col2 = st.columns(2)
        with timer_col1:
            duration = st.number_input("Minutes", min_value=1, max_value=60, value=25, step=5)
            st.session_state.timer_duration = duration
        
        with timer_col2:
            if not st.session_state.timer_running:
                if st.button("▶️ Start", use_container_width=True):
                    st.session_state.timer_running = True
                    st.session_state.timer_start = time.time()
                    st.rerun()
            else:
                if st.button("⏸️ Stop", use_container_width=True):
                    st.session_state.timer_running = False
                    st.session_state.timer_start = None
                    st.rerun()
        
        if st.session_state.timer_running and st.session_state.timer_start:
            elapsed = time.time() - st.session_state.timer_start
            remaining = (st.session_state.timer_duration * 60) - elapsed
            if remaining > 0:
                st.progress(1 - (remaining / (st.session_state.timer_duration * 60)))
                st.markdown(f"**Time Remaining:** {format_time(remaining)}")
            else:
                st.success("🎉 Timer Complete! Take a break!")
                st.session_state.timer_running = False
        
        # Session History
        if st.session_state.saved_sessions:
            st.markdown("### 📂 Saved Sessions")
            for idx, session in enumerate(reversed(st.session_state.saved_sessions[-3:])):
                timestamp = datetime.fromisoformat(session['timestamp'])
                if st.button(f"📄 {timestamp.strftime('%m/%d %H:%M')}", key=f"session_{idx}"):
                    st.session_state.messages = session.get('messages', [])
                    st.session_state.learning_goals = session.get('goals', [])
                    st.session_state.task_info = session.get('task', "")
                    st.rerun()
    
    return None

def render_chat_interface():
    """Render the main chat interface"""
    st.title("📚 Sylvia - Your Learning Facilitator")
    st.markdown("*Hi! I'm Sylvia, here to help you develop effective self-regulated learning skills. Let's work on your learning goals together!*")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Describe your learning task or ask for guidance..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Build conversation history
                    conversation = []
                    for msg in st.session_state.messages[-10:]:  # Last 10 messages for context
                        role = "user" if msg["role"] == "user" else "model"
                        conversation.append(types.Content(
                            role=role,
                            parts=[types.Part(text=msg["content"])]
                        ))
                    
                    # Generate response
                    response = client.models.generate_content(
                        model="gemini-2.0-flash-lite",
                        contents=conversation,
                        config=generation_cfg,
                    )
                    
                    assistant_response = response.text or "I'm here to help. Could you tell me more about your learning task?"
                    st.markdown(assistant_response)
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                    
                except Exception as e:
                    error_msg = f"I encountered an error: {str(e)}. Please try again."
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

def render_learning_summary():
    """Render a summary of current learning session"""
    if st.session_state.learning_goals or st.session_state.task_info:
        with st.expander("📝 Session Summary", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🎯 Learning Goals:**")
                if st.session_state.learning_goals:
                    for goal in st.session_state.learning_goals:
                        st.write(f"• {goal}")
                else:
                    st.write("*No goals set yet*")
                
                st.markdown("**📋 Task:**")
                st.write(st.session_state.task_info or "*No task defined yet*")
            
            with col2:
                st.markdown("**🧠 Strategies:**")
                if st.session_state.strategies:
                    for strategy in st.session_state.strategies:
                        st.write(f"• {strategy}")
                else:
                    st.write("*No strategies planned yet*")
                
                st.markdown("**⏰ Time Plan:**")
                st.write(st.session_state.time_plan or "*No time plan set*")

# --- Main App Logic --------------------------------------------------------
def main():
    """Main application logic"""
    # Render sidebar and get action if any
    action = render_sidebar()
    
    # Process action if triggered
    if action:
        action_prompt = process_action(action, "Please guide me with " + action)
        
        # Add action message to chat
        st.session_state.messages.append({"role": "user", "content": f"[Action: {action}]"})
        
        # Generate response for action
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=[types.Content(
                    role="user",
                    parts=[types.Part(text=action_prompt)]
                )],
                config=generation_cfg,
            )
            
            assistant_response = response.text or "Let me help you with that."
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            st.rerun()
            
        except Exception as e:
            st.error(f"Error processing action: {str(e)}")
    
    # Render main chat interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        render_chat_interface()
    
    with col2:
        render_learning_summary()

# --- Run App ---------------------------------------------------------------
if __name__ == "__main__":
    main()
