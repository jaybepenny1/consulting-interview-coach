"""Runs the agents for many visitors, enforces the caps, and exposes the human approval gate."""
import os
import re
import json
import uuid
import time
import wave
import asyncio

from google.adk.agents.run_config import RunConfig
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from . import config, security
from .agents import build_agents
from .store import _short, _memory_text, delete_user_data, cleanup_old, STOP_MARK

LABELS = {"coach": "Coach", "researcher": "Researcher", "interviewer": "Interviewer", "critic": "Critic"}

SLASH = {
    "/start": "Please start my prep: research my target firm and role, then build my prep plan.",
    "/research": "Please research my target firm and role and save a prep brief.",
    "/plan": "Please build my day-by-day prep plan.",
    "/case": "Run a mock case interview now. {arg}",
    "/behavioral": "Run a mock behavioral interview now. {arg}",
    "/framework": "Run a framework drill now.",
    "/math": "Run a math drill now.",
    "/feedback": "Give me feedback on my last practice session.",
    "/story": "Help me write a behavioral story. {arg}",
}
HELP = """Commands:
  /start      research the firm, then build your plan    /feedback   feedback on your last session
  /research   firm brief only                             /story      write a STAR/CAR story
  /plan       prep plan only                              /memory     show what the coach remembers
  /case [type]  profitability, market_entry,              /new        start a fresh conversation
                market_sizing, operations                 /help       show this list
  /behavioral [theme]   /framework   /math                /stop       end the current practice session early
Or just type naturally. You can also speak an answer with the microphone."""

STOP_PROMPT = STOP_MARK + " I want to stop this practice session now."
AUDIO_TYPES = {".wav": "audio/wav", ".mp3": "audio/mp3", ".ogg": "audio/ogg", ".m4a": "audio/m4a",
               ".webm": "audio/webm", ".flac": "audio/flac"}
TRANSCRIBE_PROMPT = ("Transcribe this recording of a job candidate speaking. Output only the words that were spoken, "
                     "with no commentary, labels or formatting. If there is no clear speech, output nothing.")


async def gemini_transcribe(data: bytes, mime: str) -> str:
    from google import genai
    client = genai.Client()
    resp = await client.aio.models.generate_content(
        model=config.MODEL,
        contents=[types.Part.from_bytes(data=data, mime_type=mime), TRANSCRIBE_PROMPT],
        config=types.GenerateContentConfig(temperature=0, max_output_tokens=600))
    return resp.text or ""

_global = {"count": 0, "day": time.strftime("%Y-%m-%d")}


class Hub:
    def __init__(self, model=None, transcriber=None):
        self.transcriber = transcriber or gemini_transcribe
        self.sessions = InMemorySessionService()
        self.runner = Runner(app_name=config.APP_NAME, agent=build_agents(model),
                             session_service=self.sessions, auto_create_session=True)

    # ---- visitors ----
    def new_visitor(self) -> dict:
        cleanup_old()
        uid = "v" + uuid.uuid4().hex[:10]
        security.log_event("visitor_new", visitor=security.visitor_hash(uid))
        return {"id": uid, "session": uid + "-1", "count": 0, "pending": None, "steps": [], "transcripts": 0}

    def delete_data(self, v: dict) -> dict:
        removed = delete_user_data(v["id"])
        security.log_event("data_deleted", visitor=security.visitor_hash(v["id"]), removed=removed)
        n = int(v["session"].rsplit("-", 1)[1]) + 1
        v.update(session=f"{v['id']}-{n}", pending=None, steps=[], count=v["count"])
        return v

    def memory(self, v: dict) -> str:
        return _memory_text(v["id"])

    # ---- one run ----
    async def _run(self, v: dict, content: types.Content) -> dict:
        msgs, steps = [], []
        try:
            async for ev in self.runner.run_async(
                    user_id=v["id"], session_id=v["session"], new_message=content,
                    run_config=RunConfig(max_llm_calls=config.MAX_LLM_CALLS_PER_TURN)):
                who = LABELS.get(ev.author, ev.author)
                if getattr(ev, "error_message", None):
                    steps.append({"who": who, "kind": "error", "text": _short(ev.error_message, 200)})
                    security.log_event("model_error", visitor=security.visitor_hash(v["id"]), error=_short(ev.error_message, 200))
                if not ev.content or not ev.content.parts:
                    continue
                for p in ev.content.parts:
                    if getattr(p, "thought", False):
                        continue
                    fc, fr = p.function_call, p.function_response
                    if fc:
                        a = dict(fc.args or {})
                        if fc.name == "transfer_to_agent":
                            tgt = LABELS.get(a.get("agent_name"), a.get("agent_name"))
                            steps.append({"who": who, "kind": "handoff", "text": f"{who} hands off to {tgt}"})
                        elif fc.name == "adk_request_confirmation":
                            orig = a.get("originalFunctionCall", {})
                            v["pending"] = {"id": fc.id, "tool": orig.get("name"), "args": orig.get("args", {}), "who": who}
                            security.log_event("gate_request", visitor=security.visitor_hash(v["id"]), tool=orig.get("name"),
                                               arg_chars={k: len(str(x)) for k, x in (orig.get("args") or {}).items()})
                        else:
                            why = a.pop("reasoning", None)
                            if why:
                                steps.append({"who": who, "kind": "reasoning", "text": why})
                            steps.append({"who": who, "kind": "tool", "text": f"{fc.name}({_short(json.dumps(a), 200)})"})
                            security.log_event("tool_call", visitor=security.visitor_hash(v["id"]), agent=ev.author, tool=fc.name)
                    elif fr:
                        if fr.name in ("transfer_to_agent", "adk_request_confirmation"):
                            continue
                        steps.append({"who": who, "kind": "result", "text": _short(fr.response, 220)})
                    elif p.text and ev.author != "user":
                        msgs.append((who, security.sanitize_output(p.text)))
        except Exception as e:
            security.log_event("run_error", visitor=security.visitor_hash(v["id"]), error=type(e).__name__, detail=_short(e, 200))
            msgs.append(("System", f"Something went wrong ({type(e).__name__}). Please try again in a moment."))
        v["steps"] = (v["steps"] + steps)[-120:]
        return {"messages": msgs, "steps": steps, "pending": v["pending"]}

    # ---- public entry points ----
    async def send(self, v: dict, text: str) -> dict:
        """Handle one user message. Returns {'messages': [(who, text)], 'pending': dict|None, 'notice': str}."""
        text = (text or "").strip()
        if not text:
            return {"messages": [], "pending": v["pending"]}
        if v["pending"]:
            return {"messages": [("System", "Please approve or reject the pending action first.")], "pending": v["pending"]}
        if len(text) > config.MAX_INPUT_CHARS:
            return {"messages": [("System", f"That message is too long (max {config.MAX_INPUT_CHARS} characters).")], "pending": None}
        cmd, _, arg = text.partition(" ")
        cmd = cmd.lower()
        if cmd == "/help":
            return {"messages": [("Coach", "```\n" + HELP + "\n```")], "pending": None}
        if cmd == "/memory":
            return {"messages": [("Coach", "**What I remember about you**\n\n```\n" + self.memory(v) + "\n```")], "pending": None}
        if cmd == "/new":
            n = int(v["session"].rsplit("-", 1)[1]) + 1
            v["session"] = f"{v['id']}-{n}"
            return {"messages": [("Coach", "Started a fresh conversation. Your saved profile and history are kept.")], "pending": None}

        if cmd == "/stop" and not await self.interview_active(v):
            return {"messages": [("Coach", "No practice session is running right now. Start one with /case, /behavioral, /framework or /math.")], "pending": None}

        if self._over_cap(v["count"], config.MAX_MESSAGES_PER_SESSION):
            security.log_event("cap_hit", cap="messages", visitor=security.visitor_hash(v["id"]))
            return {"messages": [("System", "This demo has reached its usage limit to keep costs bounded. Please try again later.")], "pending": None}
        flags = security.injection_flags(text)
        if flags:
            security.log_event("injection_flag", where="user_message", visitor=security.visitor_hash(v["id"]),
                               patterns=flags, text=_short(text, 300))
        v["count"] += 1
        _global["count"] += 1
        prompt = STOP_PROMPT if cmd == "/stop" else SLASH[cmd].format(arg=arg).strip() if cmd in SLASH else text
        security.log_event("message", visitor=security.visitor_hash(v["id"]), chars=len(text), n=v["count"])
        return await self._run(v, types.Content(role="user", parts=[types.Part(text=prompt)]))

    @staticmethod
    def _over_cap(used: int, limit: int) -> bool:
        today = time.strftime("%Y-%m-%d")
        if _global["day"] != today:
            _global.update(day=today, count=0)
        return used >= limit or _global["count"] >= config.GLOBAL_MESSAGES_PER_DAY

    async def interview_active(self, v: dict) -> bool:
        sess = await self.sessions.get_session(app_name=config.APP_NAME, user_id=v["id"], session_id=v["session"])
        return bool(sess and (sess.state.get("interview") or {}).get("active"))

    async def transcribe(self, v: dict, path: str) -> dict:
        """Turn one spoken answer into text for the message box. Returns {'text': str, 'note': str}.
        The recording is deleted as soon as it has been read."""
        try:
            if not path or not os.path.exists(path):
                return {"text": "", "note": "No recording was received."}
            ext = os.path.splitext(path)[1].lower()
            size = os.path.getsize(path)
            seconds = None
            if ext == ".wav":
                try:
                    with wave.open(path, "rb") as w:
                        seconds = w.getnframes() / float(w.getframerate() or 1)
                except Exception:
                    seconds = None
            with open(path, "rb") as f:
                data = f.read(config.MAX_AUDIO_BYTES + 1)
        finally:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        if ext not in AUDIO_TYPES:
            return {"text": "", "note": "That audio format is not supported."}
        if size > config.MAX_AUDIO_BYTES or (seconds or 0) > config.MAX_AUDIO_SECONDS + 2:
            return {"text": "", "note": f"That recording is too long. Please keep spoken answers under {config.MAX_AUDIO_SECONDS} seconds."}
        if self._over_cap(v["transcripts"], config.MAX_TRANSCRIPTIONS_PER_SESSION):
            security.log_event("cap_hit", cap="transcriptions", visitor=security.visitor_hash(v["id"]))
            return {"text": "", "note": "The voice limit for this demo has been reached. Please type your answer."}
        v["transcripts"] += 1
        _global["count"] += 1
        security.log_event("transcribe", visitor=security.visitor_hash(v["id"]), bytes=size, seconds=round(seconds or 0, 1))
        try:
            text = await self.transcriber(data, AUDIO_TYPES[ext])
        except Exception as e:
            security.log_event("transcribe_error", visitor=security.visitor_hash(v["id"]), error=type(e).__name__, detail=_short(e, 200))
            return {"text": "", "note": "Sorry, the recording could not be transcribed. Please try again or type your answer."}
        text = " ".join(security.sanitize_output(text).split())[:config.MAX_INPUT_CHARS]
        if not text:
            return {"text": "", "note": "No speech was detected. Please try again."}
        return {"text": text, "note": "Transcribed. Check the text, edit it if needed, then press Send."}

    async def decide(self, v: dict, approved: bool) -> dict:
        """Answer the pending approval request (the human gate)."""
        p = v["pending"]
        if not p:
            return {"messages": [], "pending": None}
        v["pending"] = None
        security.log_event("gate_decision", visitor=security.visitor_hash(v["id"]), tool=p["tool"], approved=bool(approved))
        resp = types.Part(function_response=types.FunctionResponse(
            id=p["id"], name="adk_request_confirmation", response={"confirmed": bool(approved)}))
        return await self._run(v, types.Content(role="user", parts=[resp]))
