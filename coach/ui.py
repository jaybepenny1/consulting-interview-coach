"""Gradio chat UI: colors, approval card (exact arguments), spoken answers, and a webcam recorder
that never leaves the visitor's browser."""
import json
import gradio as gr

from . import config
from .runtime import Hub

WELCOME = (
    "Welcome! I'm an AI consulting interview coach, a team of four agents: Coach, Researcher, Interviewer and Critic. "
    "Tell me which firm and role you're interviewing for, how many days you have, and how much case practice you've done, "
    "or tap an example on the right. You can type or speak your answers. Type /help for commands and /stop to end a "
    "practice session early.")
PRIVACY = (
    "**Privacy and safety.** This is a class demo. Your messages go to Google's Gemini API and, for research, search queries go to Tavily. "
    "If you use the microphone, the recording is sent to Gemini to be turned into text and is then deleted. "
    "Webcam recordings never leave your device. Don't enter personal or sensitive information. Everything you create is stored only "
    "temporarily and you can erase it with **Delete my data**. Nothing real is connected: no email, payments or company data.")

EXAMPLES = [
    ("Example 1: beginner", "I'm a junior with no case practice. I have a Bain Associate Consultant Intern interview in 10 days. Please start my prep."),
    ("Example 2: advanced", "I'm advanced, I've done 40+ cases for McKinsey and my weak spot is market sizing math. I have 5 days. Run a market sizing case."),
]
QUICK = [("Mock case", "/case"), ("Behavioral", "/behavioral"), ("Framework drill", "/framework"),
         ("Math drill", "/math"), ("Get feedback", "/feedback"), ("Write a story", "/story"), ("What do you remember?", "/memory")]

# ---------------------------------------------------------------- look and feel
THEME = gr.themes.Soft(primary_hue="indigo", secondary_hue="teal", neutral_hue="slate", radius_size="lg")

CSS = """
.gradio-container {max-width: 1280px !important;}
#hero {background: linear-gradient(120deg, #4338ca 0%, #7c3aed 45%, #0d9488 100%); border-radius: 18px;
       padding: 22px 26px; color: #fff; box-shadow: 0 8px 24px rgba(67,56,202,.25);}
#hero h1 {color: #fff !important; margin: 0 0 4px; font-size: 1.9rem;}
#hero p {color: #eef2ff !important; margin: 0; font-size: 1rem;}
#hero .chips {margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap;}
#hero .chip {background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.35); border-radius: 999px;
             padding: 3px 12px; font-size: .85rem; color: #fff;}
#privacy {border-left: 4px solid #0d9488; padding-left: 12px; font-size: .88rem;}
.who {display: inline-block; border-radius: 999px; padding: 1px 10px; font-size: .78rem; font-weight: 700; color: #fff;}
.who-coach {background: #4f46e5;} .who-researcher {background: #0d9488;} .who-interviewer {background: #d97706;}
.who-critic {background: #db2777;} .who-system {background: #64748b;}
#gate {border: 2px solid #f59e0b; border-radius: 14px; background: rgba(245,158,11,.08); padding: 10px 14px;}
#stop-btn {background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;}
#cam-box video {width: 100%; border-radius: 12px; background: #0f172a; margin-top: 8px;}
#cam-box .cam-row {display: flex; gap: 8px; flex-wrap: wrap; align-items: center;}
#cam-box button, #cam-box a.cam-btn {border: 0; border-radius: 10px; padding: 7px 14px; font-weight: 600; cursor: pointer;
     background: #4f46e5; color: #fff; text-decoration: none; font-size: .9rem;}
#cam-box #cam-stop {background: #dc2626;}
#cam-box button:disabled {opacity: .45; cursor: not-allowed;}
#cam-status {font-size: .85rem; margin-top: 6px;}
"""

HERO = """<div id="hero"><h1>Consulting Interview Coach</h1>
<p>Research your firm, build a plan, run mock interviews by typing or speaking, and get honest feedback.</p>
<div class="chips"><span class="chip">Coach</span><span class="chip">Researcher</span>
<span class="chip">Interviewer</span><span class="chip">Critic</span></div></div>"""

CAM_HTML = """<div id="cam-box">
<div class="cam-row">
  <button id="cam-start" type="button">Start recording</button>
  <button id="cam-stop" type="button" disabled>Stop</button>
  <a id="cam-dl" class="cam-btn" style="display:none">Download</a>
</div>
<div id="cam-status">Record yourself answering, then watch it back. The video stays in this browser tab: it is never uploaded, and the AI never sees it.</div>
<video id="cam-live" autoplay muted playsinline style="display:none"></video>
<video id="cam-play" controls playsinline style="display:none"></video>
</div>"""

# Runs in the visitor's browser only. Nothing here sends video anywhere.
HEAD = """<script>
(function () {
  var stream = null, rec = null, chunks = [], timer = null, lastUrl = null, MAX_MS = 180000;
  function el(id) { return document.getElementById(id); }
  function say(t) { var s = el('cam-status'); if (s) s.textContent = t; }
  function stopAll() {
    if (timer) { clearTimeout(timer); timer = null; }
    if (rec && rec.state !== 'inactive') rec.stop();
  }
  async function start() {
    if (!navigator.mediaDevices || !window.MediaRecorder) { say('This browser does not support recording.'); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    } catch (e) {
      say('Camera or microphone permission was not granted. Allow access in your browser and try again.'); return;
    }
    chunks = [];
    var live = el('cam-live'), play = el('cam-play');
    live.srcObject = stream; live.style.display = 'block'; play.style.display = 'none';
    el('cam-dl').style.display = 'none';
    rec = new MediaRecorder(stream);
    rec.ondataavailable = function (e) { if (e.data && e.data.size) chunks.push(e.data); };
    rec.onstop = function () {
      stream.getTracks().forEach(function (t) { t.stop(); });
      live.srcObject = null; live.style.display = 'none';
      if (lastUrl) URL.revokeObjectURL(lastUrl);
      var type = rec.mimeType || 'video/webm';
      lastUrl = URL.createObjectURL(new Blob(chunks, { type: type }));
      play.src = lastUrl; play.style.display = 'block';
      var dl = el('cam-dl');
      dl.href = lastUrl; dl.download = 'practice-answer.' + (type.indexOf('mp4') >= 0 ? 'mp4' : 'webm');
      dl.style.display = 'inline-block';
      el('cam-start').disabled = false; el('cam-stop').disabled = true;
      say('Recording finished. Watch it back or download it. It exists only in this tab.');
    };
    rec.start();
    el('cam-start').disabled = true; el('cam-stop').disabled = false;
    say('Recording... (stops automatically after 3 minutes)');
    timer = setTimeout(stopAll, MAX_MS);
  }
  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest ? e.target.closest('#cam-start, #cam-stop') : null;
    if (!t) return;
    if (t.id === 'cam-start') start(); else stopAll();
  });
})();
</script>"""

LAUNCH_KWARGS = {"theme": THEME, "css": CSS, "head": HEAD}


# ---------------------------------------------------------------- rendering helpers
def bubble(who: str, body: str) -> str:
    return f'<span class="who who-{who.lower()}">{who}</span>\n\n{body}'


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


# ---------------------------------------------------------------- app
def build_demo(hub: Hub = None):
    hub = hub or Hub()

    def view(v, history):
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
            history.append({"role": "assistant", "content": bubble(who, body)})
        return view(v, history)

    async def decide(approved, history, v):
        v = v or hub.new_visitor()
        history = list(history or [])
        history.append({"role": "user", "content": "✅ Approved" if approved else "❌ Rejected"})
        r = await hub.decide(v, approved)
        for who, body in r["messages"]:
            history.append({"role": "assistant", "content": bubble(who, body)})
        return view(v, history)

    def wipe(history, v):
        v = v or hub.new_visitor()
        hub.delete_data(v)
        history = [{"role": "assistant", "content": bubble("System", "Your saved data (profile, brief, plan, stories, history) was deleted and the conversation was reset.")}]
        return view(v, history)

    async def on_voice(path, current, v):
        v = v or hub.new_visitor()
        if not path:
            return gr.update(), None, gr.update(), v
        r = await hub.transcribe(v, path)
        merged = ((current or "").strip() + " " + r["text"]).strip() if r["text"] else (current or "")
        return gr.update(value=merged[:config.MAX_INPUT_CHARS]), None, r["note"], v

    with gr.Blocks(title="Consulting Interview Coach", delete_cache=(1800, 1800)) as demo:
        gr.HTML(HERO)
        gr.Markdown(PRIVACY, elem_id="privacy")
        state = gr.State(None)
        with gr.Row():
            with gr.Column(scale=3):
                chat = gr.Chatbot(value=[{"role": "assistant", "content": bubble("Coach", WELCOME)}], height=480, label="Chat")
                with gr.Group(visible=False, elem_id="gate") as gate:
                    gate_text = gr.Markdown("")
                    with gr.Row():
                        approve = gr.Button("✅ Approve and save", variant="primary")
                        reject = gr.Button("❌ Reject", variant="stop")
                msg = gr.Textbox(placeholder="Type a message, or a command like /case operations", show_label=False)
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    stop_btn = gr.Button("Stop session", elem_id="stop-btn")
                    wipe_btn = gr.Button("Delete my data", variant="secondary")
                voice = gr.Audio(sources=["microphone"], type="filepath", format="wav", elem_id="voice",
                                 label=f"Speak your answer (up to {config.MAX_AUDIO_SECONDS} seconds). It appears as text for you to check before sending.")
                voice_note = gr.Markdown("")
                left = gr.Markdown(left_md(None))
            with gr.Column(scale=2):
                gr.Markdown("**Try an example**")
                ex_btns = [(gr.Button(label, size="sm"), prompt) for label, prompt in EXAMPLES]
                gr.Markdown("**Quick actions**")
                q_btns = [(gr.Button(label, size="sm"), cmd) for label, cmd in QUICK]
                with gr.Accordion("Record yourself on camera (stays on your device)", open=False):
                    gr.HTML(CAM_HTML)
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
        voice.stop_recording(on_voice, [voice, msg, state], [msg, voice, voice_note, state], api_name=False)
        for btn, text in ex_btns + q_btns + [(stop_btn, "/stop")]:
            btn.click(lambda t=text: t, None, msg, queue=False, api_name=False).then(
                respond, [msg, chat, state], outs, api_name=False)
    return demo
