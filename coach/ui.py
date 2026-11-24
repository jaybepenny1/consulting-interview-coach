"""Gradio chat UI: colors, approval card (exact arguments), spoken answers, and a webcam recorder
that never leaves the visitor's browser."""
import base64
import json
import gradio as gr

from . import config, security
from .runtime import Hub
from .store import doc_choices, read_doc

WELCOME = (
    "Welcome! I'm an AI consulting interview coach, a team of four agents: Coach, Researcher, Interviewer and Critic. "
    "Tell me which firm and role you're interviewing for, how many days you have, and how much case practice you've done, "
    "or tap an example on the right. You can type or speak your answers, and turn on 'Read replies aloud' to listen. "
    "Type /help for commands and /stop to end a practice session early.")
PRIVACY = (
    "**Privacy and safety.** This is a class demo. Your messages go to Google's Gemini API and, for research, search queries go to Tavily. "
    "If you use the microphone, the recording is sent to Gemini to be turned into text and is then deleted. "
    "Webcam recordings never leave your device, and 'Read replies aloud' uses your browser's own voice, so nothing is sent anywhere for it. Don't enter personal or sensitive information. Everything you create is stored only "
    "temporarily and you can erase it with **Delete my data**. Nothing real is connected: no email, payments or company data.")

EXAMPLES = [
    ("Example 1: beginner", "I'm a junior with no case practice. I have a Bain Associate Consultant Intern interview in 10 days. Please start my prep."),
    ("Example 2: advanced", "I'm advanced, I've done 40+ cases for McKinsey and my weak spot is market sizing math. I have 5 days. Run a market sizing case."),
]
CLUB_URL = "https://www.consultingclubgsu.com/"
CLUB_PLUG = ('<div id="club-plug"><span>🎓💼 Interested in learning more about consulting? Connect with the Consulting Club at GSU. 🚀🤝</span>'
             f'<a href="{CLUB_URL}" target="_blank" rel="noopener noreferrer">CCG Website 🔗</a></div>')
DL_NAMES = {"Firm brief": "firm-brief.md", "Prep plan": "prep-plan.md", "Story bank": "story-bank.md"}
DOC_EMPTY = ("_Nothing saved yet. Your firm brief, prep plan and stories show up here after they are saved. "
             "Documents are temporary, so download anything you want to keep._")
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
#cam-box video {width: 100%; max-height: 240px; object-fit: cover; border-radius: 12px; background: #0f172a; margin-top: 8px;}
#gate-text {max-height: 440px; overflow-y: auto; font-size: .95rem; line-height: 1.55; overflow-wrap: anywhere;}
#gate-text h1, #doc-view h1 {font-size: 1.1rem; margin: .7em 0 .25em;}
#gate-text h2, #doc-view h2 {font-size: 1.02rem; margin: .6em 0 .2em;}
#gate-text h3 {font-size: 1.05rem;}
#gate-text pre, #doc-view pre {white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere;}
#gate-text summary {cursor: pointer; font-weight: 600; color: #4338ca;}
#doc-view {max-height: 380px; overflow-y: auto; font-size: .92rem; line-height: 1.5; overflow-wrap: anywhere;
           border: 1px solid #e2e8f0; border-radius: 12px; padding: 8px 12px;}
.dl-btn {display: inline-block; margin-top: 6px; padding: 6px 14px; border-radius: 10px; background: #4f46e5;
         color: #fff !important; font-weight: 600; font-size: .9rem; text-decoration: none;}
#club-plug {display: flex; align-items: center; justify-content: space-between; gap: 10px 16px; flex-wrap: wrap;
            font-size: .95rem; padding: 10px 14px; border-radius: 12px; background: rgba(79,70,229,.08);
            border: 1px solid rgba(79,70,229,.30);}
#club-plug a {display: inline-block; padding: 10px 24px; border-radius: 12px; background: #4f46e5; color: #fff !important;
              font-weight: 700; font-size: 1.05rem; text-decoration: none; white-space: nowrap;
              box-shadow: 0 4px 12px rgba(79,70,229,.35); transition: transform .12s ease, box-shadow .12s ease;}
#club-plug a:hover {transform: translateY(-1px); box-shadow: 0 6px 16px rgba(79,70,229,.45);}
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
HEAD = r"""<script>
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

// Read replies aloud: the browser's own text-to-speech. Text never leaves the tab.
(function () {
  window.__spoken = 1;               // the welcome message is already on screen
  var PITCH = { Coach: 1.0, Researcher: 0.9, Interviewer: 1.1, Critic: 0.85, System: 1.0 };
  var RATE = { Coach: 1.0, Researcher: 1.0, Interviewer: 1.0, Critic: 0.95, System: 1.0 };
  function readable(content) {
    var t = '';
    if (typeof content === 'string') { t = content; }
    else if (Array.isArray(content)) {   // the page stores message content as a list of parts
      t = content.map(function (c) { return typeof c === 'string' ? c : ((c && c.text) || ''); }).join(' ');
    } else { t = (content && content.text) || ''; }
    var m = t.match(/<span class="who[^"]*">([^<]+)<\/span>/);
    var who = m ? m[1] : 'Coach';
    t = t.replace(/<[^>]*>/g, ' ')
         .replace(/```[\s\S]*?```/g, ' ')
         .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
         .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
         .replace(/https?:\/\/\S+/g, ' ')
         .split('\n').filter(function (l) { return !/^\s*\|/.test(l); }).join('\n')
         .replace(/^[#>\-\*\s]+/gm, '')
         .replace(/[*_`~]/g, '')
         .replace(/\s+/g, ' ').trim();
    return { who: who, text: t };
  }
  function pieces(t) {
    var out = [], cur = '';
    (t.match(/[^.!?]+[.!?]*\s*/g) || [t]).forEach(function (s) {
      if (cur && (cur + s).length > 180) { out.push(cur); cur = s; } else { cur += s; }
    });
    if (cur) out.push(cur);
    return out;
  }
  window.coachSpeak = function (history, on) {
    if (!history) return;
    if (history.length < window.__spoken) window.__spoken = history.length;
    var fresh = history.slice(window.__spoken);
    window.__spoken = history.length;
    if (!on || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    fresh.forEach(function (m) {
      if (!m || m.role !== 'assistant') return;
      var r = readable(m.content), text = r.text, cut = false;
      if (text.length > 700) { text = text.slice(0, 700); cut = true; }
      if (!text) return;
      pieces(text).forEach(function (chunk) {
        var u = new SpeechSynthesisUtterance(chunk);
        u.pitch = PITCH[r.who] || 1.0; u.rate = RATE[r.who] || 1.0;
        window.speechSynthesis.speak(u);
      });
      if (cut) window.speechSynthesis.speak(new SpeechSynthesisUtterance('The rest is on screen.'));
    });
  };
  window.coachStopSpeaking = function () { if (window.speechSynthesis) window.speechSynthesis.cancel(); };
  if (window.speechSynthesis) window.speechSynthesis.getVoices();
})();
</script>"""

SPEAK_JS = "(history, on) => window.coachSpeak(history, on)"
LAUNCH_KWARGS = {"theme": THEME, "css": CSS, "head": HEAD}


# ---------------------------------------------------------------- rendering helpers
def bubble(who: str, body: str) -> str:
    return f'<span class="who who-{who.lower()}">{who}</span>\n\n{security.shorten_links(body)}'


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


def _fence(text: str) -> str:
    longest = max([len(m) for m in __import__("re").findall(r"`+", text)] or [0])
    return "`" * max(3, longest + 1)


def gate_md(p):
    """The approval card. The brief is shown as readable text (images removed, links shown as site names);
    the exact text that will be saved, with full links, is one click away so nothing is hidden."""
    if not p:
        return ""
    shown, raw = [], []
    for k, val in (p["args"] or {}).items():
        text = val if isinstance(val, str) else json.dumps(val, indent=2)
        f = _fence(text)
        raw.append(f"**{k}**\n\n{f}\n{text}\n{f}")
        if k == "brief":
            shown.append(security.shorten_links(security.sanitize_output(text, log=False)))
        else:
            shown.append(f"_{k}: {text}_")
    return (f"### Approval needed\nThe **{p['who']}** wants to run **`{p['tool']}`**, which saves this text to your session "
            f"so the Coach can build your plan from it. Nothing is saved until you approve.\n\n"
            + "\n\n".join(shown)
            + "\n\n<details><summary>Show the exact text that will be saved (full links)</summary>\n\n"
            + "\n\n".join(raw) + "\n\n</details>")


def dl_link(label, text):
    """Download link built in the page itself (a data: link), so no file is served from the server."""
    data = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return (f'<a class="dl-btn" download="{DL_NAMES.get(label, "document.md")}" '
            f'href="data:text/markdown;charset=utf-8;base64,{data}">⬇ Download this document</a>')


def doc_md(text):
    return security.shorten_links(security.sanitize_output(text, log=False))


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

    def refresh_docs(v, selected):
        """Fill the documents dropdown from THIS visitor's own folder (fixed labels, fixed filenames)."""
        choices = doc_choices(v["id"]) if v else []
        sel = selected if selected in choices else (choices[0] if choices else None)
        raw = read_doc(v["id"], sel) if sel else None
        if raw is None:
            return gr.update(choices=choices, value=sel), DOC_EMPTY, ""
        return gr.update(choices=choices, value=sel), doc_md(raw), dl_link(sel, raw)

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
                    gate_text = gr.Markdown("", elem_id="gate-text")
                    with gr.Row():
                        approve = gr.Button("✅ Approve and save", variant="primary")
                        reject = gr.Button("❌ Reject", variant="stop")
                msg = gr.Textbox(placeholder="Type a message, or a command like /case operations", show_label=False)
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    stop_btn = gr.Button("Stop session", elem_id="stop-btn")
                    wipe_btn = gr.Button("Delete my data", variant="secondary")
                with gr.Row():
                    speak = gr.Checkbox(label="🔊 Read replies aloud", value=False, elem_id="speak-toggle", scale=3)
                    stop_speak = gr.Button("Stop speaking", size="sm", scale=1)
                voice = gr.Audio(sources=["microphone"], type="filepath", format="wav", elem_id="voice",
                                 label=f"Speak your answer (up to {config.MAX_AUDIO_SECONDS} seconds). It appears as text for you to check before sending.")
                gr.HTML(CLUB_PLUG)
                voice_note = gr.Markdown("")
                left = gr.Markdown(left_md(None))
            with gr.Column(scale=2):
                with gr.Accordion("Record yourself on camera (stays on your device)", open=True):
                    gr.HTML(CAM_HTML)
                with gr.Accordion("My documents (view only)", open=True):
                    doc_sel = gr.Dropdown(choices=[], value=None, label="Saved documents", interactive=True)
                    doc_view = gr.Markdown(DOC_EMPTY, elem_id="doc-view")
                    doc_dl = gr.HTML("")
                gr.Markdown("**Try an example**")
                ex_btns = [(gr.Button(label, size="sm"), prompt) for label, prompt in EXAMPLES]
                gr.Markdown("**Quick actions**")
                q_btns = [(gr.Button(label, size="sm"), cmd) for label, cmd in QUICK]
                with gr.Accordion("What the agents are doing", open=True):
                    activity = gr.Markdown(steps_md(None))
                with gr.Accordion("What the coach remembers", open=False):
                    memory_box = gr.Textbox(lines=8, interactive=False, show_label=False)
        outs = [chat, activity, memory_box, state, msg, gate, gate_text, left]
        docs_outs = [doc_sel, doc_view, doc_dl]

        def after(evt):
            """After every turn: refresh the documents list, then read the new replies aloud if the toggle is on."""
            return (evt.then(refresh_docs, [state, doc_sel], docs_outs, api_name=False)
                       .then(None, [chat, speak], None, js=SPEAK_JS, api_name=False, queue=False))

        demo.load(on_load, None, [state, left], api_name=False)
        after(msg.submit(respond, [msg, chat, state], outs, api_name="respond"))
        after(send.click(respond, [msg, chat, state], outs, api_name=False))
        after(approve.click(decide, [gr.State(True), chat, state], outs, api_name=False))
        after(reject.click(decide, [gr.State(False), chat, state], outs, api_name=False))
        after(wipe_btn.click(wipe, [chat, state], outs, api_name=False))
        doc_sel.input(refresh_docs, [state, doc_sel], docs_outs, api_name=False)
        stop_speak.click(None, None, None, js="() => window.coachStopSpeaking()", queue=False, api_name=False)
        voice.stop_recording(on_voice, [voice, msg, state], [msg, voice, voice_note, state], api_name=False)
        for btn, text in ex_btns + q_btns + [(stop_btn, "/stop")]:
            after(btn.click(lambda t=text: t, None, msg, queue=False, api_name=False).then(
                respond, [msg, chat, state], outs, api_name=False))
    return demo
