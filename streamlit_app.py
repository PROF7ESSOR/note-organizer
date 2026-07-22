import streamlit as st
from groq import Groq
import json

st.set_page_config(page_title="Note Organizer", page_icon="🗂️", layout="centered")

# --- Connect to Groq using a securely stored key (set up in Streamlit secrets, not in this file) ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- Theme: dark, techy, matches the rest of the portfolio/brand ---
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700&family=Manrope:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --bg: #090b10;
  --panel: #12161f;
  --line: #262c39;
  --text: #edeae3;
  --muted: #8b92a3;
  --accent: #f2a65a;
  --ok: #5ec8b8;
}

@keyframes fadeInUp{
  from{ opacity:0; transform: translateY(14px); }
  to{ opacity:1; transform: translateY(0); }
}
@keyframes glow{
  0%,100%{ box-shadow: 0 0 0 rgba(242,166,90,0); }
  50%{ box-shadow: 0 0 18px rgba(242,166,90,.35); }
}
@keyframes dotPulse{
  0%,100%{ opacity:1; } 50%{ opacity:.35; }
}
@keyframes gradientShift{
  0%{ background-position: 0% 50%; }
  50%{ background-position: 100% 50%; }
  100%{ background-position: 0% 50%; }
}

[data-testid="stAppViewContainer"]{
  background: radial-gradient(1200px circle at 15% -10%, rgba(242,166,90,.08), transparent 45%),
              radial-gradient(900px circle at 100% 0%, rgba(94,200,184,.07), transparent 40%),
              var(--bg);
}
[data-testid="stHeader"]{ background: transparent; }

.hero-badge{
  display:inline-flex; align-items:center; gap:8px;
  font-family:'IBM Plex Mono', monospace; font-size:12px; color: var(--muted);
  border:1px solid var(--line); padding:6px 12px; border-radius:20px;
  margin-bottom:18px; animation: fadeInUp .6s ease both;
}
.hero-badge .dot{ width:6px; height:6px; border-radius:50%; background: var(--ok);
  box-shadow:0 0 8px var(--ok); animation: dotPulse 2s ease-in-out infinite; }

h1.app-title{
  font-family:'Bricolage Grotesque', sans-serif !important;
  font-size: 42px !important; font-weight:700 !important;
  letter-spacing:-0.01em; margin:0 0 8px 0 !important;
  background: linear-gradient(90deg, var(--text), var(--accent), var(--text));
  background-size: 200% auto;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: fadeInUp .7s ease both, gradientShift 6s ease-in-out infinite;
}

p.app-sub{
  font-family:'Manrope', sans-serif; color: var(--muted); font-size:15.5px;
  margin-bottom: 28px !important; animation: fadeInUp .8s ease .1s both;
}

.stTextArea textarea{
  background: var(--panel) !important; border:1px solid var(--line) !important;
  color: var(--text) !important; font-family:'Manrope', sans-serif !important;
  border-radius:10px !important; transition: border-color .2s ease, box-shadow .2s ease;
}
.stTextArea textarea:focus{
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 1px var(--accent) !important;
}

.stButton>button{
  font-family:'IBM Plex Mono', monospace !important; font-weight:500 !important;
  letter-spacing:.03em; background: var(--accent) !important; color:#1a1206 !important;
  border:none !important; border-radius:8px !important; padding:10px 22px !important;
  transition: transform .18s ease, background .18s ease;
}
.stButton>button:hover{
  background:#f5b979 !important; transform: translateY(-2px);
  animation: glow 1.4s ease-in-out infinite;
}

h3{
  font-family:'Bricolage Grotesque', sans-serif !important;
  color: var(--text) !important; animation: fadeInUp .5s ease both;
}

[data-testid="stDataFrame"]{
  animation: fadeInUp .55s ease both;
  border: 1px solid var(--line); border-radius: 10px; overflow:hidden;
}

.stAlert{
  font-family:'Manrope', sans-serif !important; border-radius:10px !important;
  animation: fadeInUp .4s ease both;
}
</style>
""", unsafe_allow_html=True)

# --- Keep results in session state so they survive between reruns of the page ---
if "saved_tasks" not in st.session_state:
    st.session_state.saved_tasks = []
if "flagged_items" not in st.session_state:
    st.session_state.flagged_items = []


def save_task(task, owner, status, deadline, notes):
    st.session_state.saved_tasks.append({
        "Task": task, "Owner": owner, "Status": status,
        "Deadline": deadline, "Notes": notes
    })


def flag_unclear(task, reason):
    st.session_state.flagged_items.append({
        "Task": task, "Reason": reason
    })


AVAILABLE_FUNCTIONS = {
    "save_task": save_task,
    "flag_unclear": flag_unclear
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "save_task",
            "description": "Save a task that is clear and unambiguous.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "owner": {"type": "string", "description": "Use 'Unassigned' if no owner is mentioned."},
                    "status": {"type": "string", "description": "Use 'Pending' if not mentioned."},
                    "deadline": {"type": "string", "description": "Use 'Not specified' if no deadline or date is mentioned."},
                    "notes": {"type": "string"}
                },
                "required": ["task", "owner", "status", "deadline", "notes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "flag_unclear",
            "description": "Flag a task for human review when something is genuinely ambiguous or contradictory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "reason": {"type": "string"}
                },
                "required": ["task", "reason"]
            }
        }
    }
]


def run_agent(notes_text, max_turns=12):
    messages = [
        {"role": "user", "content": f"""You will be given raw, unstructured notes. These could be in ANY format — bullet points, a rambling paragraph, a voice-memo style transcript, a numbered list, or even a single run-on sentence. Do not assume any particular structure.

Go through the notes and identify every distinct task, decision, or actionable item mentioned — regardless of how it's phrased or formatted.

For each item, decide between two actions:

1. Call save_task if the task itself is identifiable, even if owner, status, or deadline are missing. Use these exact defaults when information is simply not mentioned:
   - owner: "Unassigned"
   - status: "Pending"
   - deadline: "Not specified"
A missing detail is NOT a reason to flag something — only use these defaults and save it.

2. Call flag_unclear ONLY when there is a genuine contradiction or explicitly stated uncertainty that a default cannot resolve. Signals to check for: a question mark near the detail, words like "wait", "actually", "maybe", "or maybe", "did we", "someone said", or two different people/dates/numbers both associated with the same fact.

The test: if a default value resolves it, save it. If you'd have to guess between two conflicting facts, flag it.

Process one item at a time. I will tell you to continue after each call.

Notes:
{notes_text}"""}
    ]

    for _ in range(max_turns):
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            tools=tools
        )
        message = response.choices[0].message

        if not message.tool_calls:
            break

        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": message.tool_calls
        })

        for call in message.tool_calls:
            func_name = call.function.name
            args = json.loads(call.function.arguments)
            AVAILABLE_FUNCTIONS[func_name](**args)

            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": f"{func_name} completed successfully."
            })

        messages.append({
            "role": "user",
            "content": "Continue with the next item if any remain. If everything has been processed, say so."
        })


# ---------------- The actual webpage ----------------

st.markdown("""
<div class="hero-badge"><span class="dot"></span>status: ready to organize</div>
<h1 class="app-title">🗂️ Note Organizer</h1>
<p class="app-sub">Paste any messy notes below. Missing owners or deadlines are handled automatically — anything genuinely unclear gets flagged for you to review.</p>
""", unsafe_allow_html=True)

notes_input = st.text_area("Your notes", height=220, placeholder="Paste your messy notes here...", label_visibility="collapsed")

if st.button("Organize my notes", type="primary"):
    if notes_input.strip() == "":
        st.warning("Paste some notes first.")
    else:
        st.session_state.saved_tasks = []
        st.session_state.flagged_items = []
        with st.spinner("Organizing your notes..."):
            run_agent(notes_input)

if st.session_state.saved_tasks:
    st.markdown("### ✅ Organized Tasks")
    st.dataframe(st.session_state.saved_tasks, use_container_width=True)

if st.session_state.flagged_items:
    st.markdown("### ⚠️ Needs Your Clarification")
    st.dataframe(st.session_state.flagged_items, use_container_width=True)
