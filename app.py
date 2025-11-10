<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sylvia — Streamlit UI Preview (Screenshot Match)</title>
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
      --shadow: 0 6px 18px rgba(0,0,0,.08);
      --pill: 14px;
      --radius: 18px;
    }
    html,body { margin:0; background: var(--bg); color: var(--ink);
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .container { max-width: 1400px; margin: 0 auto; padding: 20px; }

    /* Header */
    .header-card{
      background: var(--card);
      border-radius: 20px;
      padding: 24px 28px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }
    .header-title { color: var(--brand); font-size: 28px; display:flex; gap:10px; align-items:center; }
    .header-sub { color: var(--muted); font-size: 17px; }

    /* Grid layout */
    .grid {
      display: grid;
      grid-template-columns: 290px 1fr 310px;
      grid-template-areas:
        "left center right"
        "left center right2";
      gap: 24px;
    }
    .left { grid-area: left; }
    .center { grid-area: center; }
    .right { grid-area: right; }
    .right2 { grid-area: right2; }

    /* Cards */
    .card {
      background: var(--card);
      border-radius: 20px;
      padding: 22px;
      box-shadow: var(--shadow);
    }
    h2, h3 { color: var(--brand); margin: 0 0 14px 0; }
    .section-title { display:flex; align-items:center; gap:10px; color: var(--brand);
      font-size: 24px; font-weight: 800; }
    .section-title.small { font-size: 20px; }

    /* Left quick actions */
    .btn {
      background: var(--brand);
      color: #fff;
      display: flex; align-items:center; gap:10px;
      width: 100%;
      padding: 14px 16px;
      border-radius: 12px;
      margin-bottom: 10px;
      text-decoration: none;
      font-weight: 700;
      box-shadow: 0 1px 0 rgba(0,0,0,.06) inset;
    }
    .btn:hover { background: var(--brand-700); }
    .btn .icon { width:22px; display:inline-block; text-align:center; }

    /* Conversation area */
    .chat-wrap { display:flex; flex-direction:column; gap:12px; }
    .chat-canvas {
      background: #f0f9f2;
      border-radius: 16px;
      padding: 18px;
      min-height: 420px;
      max-height: 520px;
      overflow-y: auto;
      border: 1px solid #d4eed8;
    }
    .bubble {
      margin-bottom: 14px;
      padding: 14px 16px;
      border-radius: 16px;
      max-width: 70ch;
      line-height: 1.55;
      font-size: 16px;
    }
    .assistant { background: var(--brand); color:#fff; border-bottom-left-radius: 6px; width: fit-content; }
    .user { background: #d4eed8; color: var(--ink); margin-left: auto; border-bottom-right-radius: 6px; width: fit-content; }

    /* Input row: pill style */
    .input-row {
      display: grid; grid-template-columns: 1fr 120px; gap: 12px; margin-top: 12px;
    }
    .input-row input {
      padding: 14px 16px; border: 2px solid #d4eed8; border-radius: 999px;
      font-size: 16px; outline: none;
    }
    .input-row input:focus { border-color: var(--ring); box-shadow: 0 0 0 3px rgba(15,145,89,.12); }
    .input-row button {
      background: var(--brand); color:#fff; border:0; border-radius:999px; padding: 12px 20px; font-weight: 800;
    }
    .input-row button:hover { background: var(--brand-700); }

    /* Right sidebar */
    .stat-box {
      background: #f7fbf8;
      padding: 16px;
      border-radius: 16px;
      text-align: center;
      border: 1px solid #e0f0e5;
      margin-bottom: 12px;
    }
    .big { font-size: 34px; font-weight: 800; color: var(--brand); }
    .label { color: var(--muted); font-size: 14px; }
    .progress { background: #d4eed8; height: 8px; border-radius: 10px; overflow: hidden; margin-top: 8px; }
    .progress > div { background: var(--brand); height:8px; width:75%; }

    /* Recent sessions scroll with thick green scrollbar */
    .recent {
      max-height: 380px; overflow-y: auto; padding-right: 6px;
    }
    .recent::-webkit-scrollbar { width: 10px; }
    .recent::-webkit-scrollbar-track { background: #e9f6ec; border-radius: 12px; }
    .recent::-webkit-scrollbar-thumb { background: var(--brand); border-radius: 12px; }
    .recent::-webkit-scrollbar-thumb:hover { background: var(--brand-700); }

    .session-item {
      background: #f0f9f2;
      border-left: 6px solid var(--brand);
      border-radius: 12px;
      padding: 12px 14px;
      margin-bottom: 10px;
    }
    .session-title { font-weight: 800; color: var(--ink); margin-bottom: 4px; }
    .session-meta { color: var(--muted); font-size: 14px; }

    @media (max-width: 1200px) {
      .grid { grid-template-columns: 1fr; grid-template-areas: "left" "center" "right" "right2"; }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header-card">
      <div class="header-title">🎓 Sylvia</div>
      <div class="header-sub">
        Your personal learning facilitator, designed to help you develop mastery goals, effective learning strategies, and self-regulated learning capacities for deep, meaningful learning.
      </div>
    </div>

    <div class="grid">
      <!-- Left -->
      <div class="card left">
        <div class="section-title">🚀 Quick Actions</div>
        <a class="btn"><span class="icon">🎯</span> Set Learning Goals</a>
        <a class="btn"><span class="icon">💡</span> Learning Strategies</a>
        <a class="btn"><span class="icon">⏱️</span> Time Management</a>
        <a class="btn"><span class="icon">📚</span> Find Resources</a>
        <a class="btn"><span class="icon">🤔</span> Reflect on Learning</a>
        <a class="btn"><span class="icon">💬</span> Request Feedback</a>
        <a class="btn"><span class="icon">💾</span> Save Session</a>
        <a class="btn"><span class="icon">➕</span> New Session</a>
      </div>

      <!-- Center -->
      <div class="card center">
        <div class="section-title">💬 Learning Conversation</div>
        <div class="chat-wrap">
          <div class="chat-canvas">
            <div class="bubble assistant">Hello! I'm Sylvia, your learning facilitator. I'm here to help you develop effective learning strategies and achieve your academic goals through self-regulated learning. What task are you working on today?</div>
            <div class="bubble user">I need to write a research paper on climate change, but I'm not sure where to start.</div>
            <div class="bubble assistant">Great topic! Let's start by setting some mastery learning goals. What specific aspects of climate change interest you most? And what would you like to learn or master through this research paper beyond just completing the assignment?</div>
          </div>
          <div class="input-row">
            <input placeholder="Type your message here..." />
            <button>Send</button>
          </div>
        </div>
      </div>

      <!-- Right: Current Session -->
      <div class="card right">
        <div class="section-title small">📊 Current Session</div>
        <div class="stat-box">
          <div class="big">45m / 60m</div>
          <div class="label">Time Used / Expected</div>
          <div class="progress"><div></div></div>
        </div>
        <div class="stat-box">
          <div class="big">3</div>
          <div class="label">Goals Set</div>
        </div>
      </div>

      <!-- Right2: Recent Sessions -->
      <div class="card right2">
        <div class="section-title small">🗂️ Recent Sessions</div>
        <div class="recent">
          <div class="session-item">
            <div class="session-title">Research Paper Analysis</div>
            <div class="session-meta">2 hours ago</div>
          </div>
          <div class="session-item">
            <div class="session-title">Math Problem Set</div>
            <div class="session-meta">Yesterday</div>
          </div>
          <div class="session-item">
            <div class="session-title">Essay Planning</div>
            <div class="session-meta">3 days ago</div>
          </div>
          <div class="session-item">
            <div class="session-title">Biology Notes Review</div>
            <div class="session-meta">4 days ago</div>
          </div>
        </div>
      </div>

    </div>
  </div>
</body>
</html>
