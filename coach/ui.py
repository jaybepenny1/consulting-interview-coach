"""Gradio chat UI. The approval card shows the exact arguments of the pending action."""
import json
import gradio as gr

from . import config
from .runtime import Hub, HELP

WELCOME = (
    "Welcome! I'm an AI consulting interview coach (a team of 4 agents: Coach, Researcher, Interviewer, Critic). "
    "Tell me which firm and role you're interviewing for, how many days you have, and how much case practice you've done, "
    "or tap an example on the right. Type /help for commands.")
PRIVACY = (
    "**Privacy & safety.** This is a class demo. Your messages go to Google's Gemini API and, for research, search queries go to Tavily. "
    "Don't enter personal or sensitive information. Everything you create is stored only temporarily on the server and "
    "you can erase it with **Delete my data**. Connected to nothing real: no email, payments or company data.")

EXAMPLES = [
    ("Example 1: beginner", "I'm a junior with no case practice. I have a Bain Associate Consultant Intern interview in 10 days. Please start my prep."),
    ("Example 2: advanced", "I'm advanced, I've done 40+ cases for McKinsey and my weak spot is market sizing math. I have 5 days. Run a market sizing case."),
]
QUICK = [("Mock case", "/case"), ("Behavioral", "/behavioral"), ("Framework drill", "/framework"),
         ("Math drill", "/math"), ("Get feedback", "/feedback"), ("Write a story", "/story"), ("What do you remember?", "/memory")]


def steps_md(v):
    if not v or not v["steps"]:
        return "_Nothing yet. Send a message to see each agent's handoffs, reasoning and tool calls here._"
    out = []
    for s in v["steps"][-60:]:
        t = s["text"].replace("\n", " ")
        t = t if len(t) <= 220 else t[:220] + "..."
        if s["kind"] == "handoff":
            out.append(f"- **Handoff:** {t}")
        elif s["kind"] == "reasoning":
            out.append(f"- **{s['who']} reasoning:** {t}")
        elif s["kind"] == "tool":
            out.append(f"- **{s['who']} tool:** `{t}`")
        elif s["kind"] == "result":
            out.append(f"- **Result:** `{t}`")
        else:
            out.append(f"- **{s['who']} error:** {t}")
    return "\n".join(out)


def gate_md(p):
    if not p:
        return ""
    blocks = []
    for k, val in (p["args"] or {}).items():
        blocks.append(f"**{k}**\n\n```\n{val if isinstance(val, str) else json.dumps(val, indent=2)}\n```")
    return (f"### Approval needed\nThe **{p['who']}** wants to run **`{p['tool']}`**, which saves this text to your session "
            f"so the Coach can build your plan from it. Nothing is saved until you approve. Exactly what it will use:\n\n" + "\n\n".join(blocks))


def left_md(v):
    left = max(0, config.MAX_MESSAGES_PER_SESSION - (v["count"] if v else 0))
    return f"Messages left in this session: **{left}** of {config.MAX_MESSAGES_PER_SESSION}"


def build_demo(hub: Hub = None):
    hub = hub or Hub()

    def view(v, history, extra=None):
        pending = v["pending"]
        return (history, steps_md(v), hub.memory(v), v,
                gr.update(value="", interactive=not pending, placeholder=("Approve or reject the action above first" if pending else "Type a message, or a command like /case operations")),
                gr.update(visible=bool(pending)), gate_md(pending), left_md(v))

    def on_load():
        v = hub.new_visitor()
        return v, left_md(v)

    async def respond(message, history, v):
        v = v or hub.new_visitor()
        history = list(history or [])
        text = (message or "").strip()
        if not text:
            return view(v, history)
        history.append({"role": "user", "content": text})
        r = await hub.send(v, text)
        for who, body in r["messages"]:
            history.append({"role": "assistant", "content": f"**{who}**\n\n{body}"})
        return view(v, history)

    async def decide(approved, history, v):
        v = v or hub.new_visitor()
        history = list(history or [])
        history.append({"role": "user", "content": "✅ Approved" if approved else "❌ Rejected"})
        r = await hub.decide(v, approved)
        for who, body in r["messages"]:
            history.append({"role": "assistant", "content": f"**{who}**\n\n{body}"})
        return view(v, history)

    def wipe(history, v):
        v = v or hub.new_visitor()
        hub.delete_data(v)
        history = [{"role": "assistant", "content": "Your saved data (profile, brief, plan, stories, history) was deleted and the conversation was reset."}]
        return view(v, history)

    with gr.Blocks(title="Consulting Interview Coach") as demo:
        gr.Markdown("# Consulting Interview Coach\nA team of AI agents that researches your firm, builds your plan, runs mock interviews and gives feedback.")
        gr.Markdown(PRIVACY)
        state = gr.State(None)
        with gr.Row():
            with gr.Column(scale=3):
                chat = gr.Chatbot(value=[{"role": "assistant", "content": WELCOME}], height=480, label="Chat")
                with gr.Group(visible=False) as gate:
                    gate_text = gr.Markdown("")
                    with gr.Row():
                        approve = gr.Button("✅ Approve and save", variant="primary")
                        reject = gr.Button("❌ Reject", variant="stop")
                msg = gr.Textbox(placeholder="Type a message, or a command like /case operations", show_label=False)
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    wipe_btn = gr.Button("Delete my data", variant="secondary")
                left = gr.Markdown(left_md(None))
            with gr.Column(scale=2):
                gr.Markdown("**Try an example**")
                ex_btns = [(gr.Button(label, size="sm"), prompt) for label, prompt in EXAMPLES]
                gr.Markdown("**Quick actions**")
                q_btns = [(gr.Button(label, size="sm"), cmd) for label, cmd in QUICK]
                with gr.Accordion("What the agents are doing", open=True):
                    activity = gr.Markdown(steps_md(None))
                with gr.Accordion("What the coach remembers", open=False):
                    memory_box = gr.Textbox(lines=8, interactive=False, show_label=False)
        outs = [chat, activity, memory_box, state, msg, gate, gate_text, left]
        demo.load(on_load, None, [state, left], api_name=False)
        msg.submit(respond, [msg, chat, state], outs, api_name="respond")
        send.click(respond, [msg, chat, state], outs, api_name=False)
        approve.click(decide, [gr.State(True), chat, state], outs, api_name=False)
        reject.click(decide, [gr.State(False), chat, state], outs, api_name=False)
        wipe_btn.click(wipe, [chat, state], outs, api_name=False)
        for btn, text in ex_btns + q_btns:
            btn.click(lambda t=text: t, None, msg, queue=False, api_name=False).then(
                respond, [msg, chat, state], outs, api_name=False)
    return demo
