import streamlit as st
from groq import Groq
import json

st.set_page_config(page_title="Note Organizer", page_icon="🗂️")

# --- Connect to Groq using a securely stored key (set up in Streamlit secrets, not in this file) ---
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

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

st.title("🗂️ Note Organizer")
st.write("Paste any messy notes below. Missing owners or deadlines are handled automatically — anything genuinely unclear gets flagged for you to review.")

notes_input = st.text_area("Your notes", height=220, placeholder="Paste your messy notes here...")

if st.button("Organize my notes", type="primary"):
    if notes_input.strip() == "":
        st.warning("Paste some notes first.")
    else:
        st.session_state.saved_tasks = []
        st.session_state.flagged_items = []
        with st.spinner("Organizing your notes..."):
            run_agent(notes_input)

if st.session_state.saved_tasks:
    st.subheader("✅ Organized Tasks")
    st.dataframe(st.session_state.saved_tasks, use_container_width=True)

if st.session_state.flagged_items:
    st.subheader("⚠️ Needs Your Clarification")
    st.dataframe(st.session_state.flagged_items, use_container_width=True)
