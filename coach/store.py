"""Per-visitor storage (ephemeral files) and memory helpers."""
import re
import json
import time
import shutil
from pathlib import Path

from . import config


def _short(text, n=500):
    text = str(text)
    return text if len(text) <= n else text[:n] + f"... [truncated, {len(text)} chars]"


# =====================================================================
# STORAGE: one folder per candidate; memory is a JSON file
# =====================================================================
def _user_dir(user_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id or "anon")[:40]
    d = config.DATA_DIR / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_mem(user_id: str) -> dict:
    path = _user_dir(user_id) / "memory.json"
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"profile": {}, "sessions": [], "math": {"attempted": 0, "correct": 0}}


def _save_mem(user_id: str, mem: dict) -> None:
    d = _user_dir(user_id)
    (d / "memory.json").write_text(json.dumps(mem, indent=2))
    d.touch()


def _dim_stats(mem: dict) -> dict:
    """Average score per (mode, dimension) across all graded sessions."""
    acc = {}
    for s in mem.get("sessions", []):
        for dim, score in (s.get("scores") or {}).items():
            acc.setdefault((s["mode"], dim), []).append(score)
    return {k: (sum(v) / len(v), len(v)) for k, v in acc.items()}


def _memory_text(user_id: str) -> str:
    mem = _load_mem(user_id)
    prof = mem.get("profile") or {}
    lines = []
    if prof:
        lines.append("PROFILE: " + "; ".join(f"{k}={v}" for k, v in prof.items() if v))
    else:
        lines.append("PROFILE: none saved yet (new candidate).")
    sessions = mem.get("sessions", [])
    lines.append(f"GRADED SESSIONS: {len(sessions)}")
    stats = _dim_stats(mem)
    if stats:
        ranked = sorted(stats.items(), key=lambda kv: kv[1][0])
        weakest = ", ".join(f"{m}:{d} ({avg:.1f}/5)" for (m, d), (avg, n) in ranked[:3])
        strongest = ", ".join(f"{m}:{d} ({avg:.1f}/5)" for (m, d), (avg, n) in ranked[-2:])
        lines.append("WEAKEST AREAS: " + weakest)
        lines.append("STRONGEST AREAS: " + strongest)
    m = mem.get("math", {})
    if m.get("attempted"):
        lines.append(f"MATH DRILLS: {m['correct']}/{m['attempted']} correct")
    if sessions:
        last = sessions[-1]
        lines.append(f"LAST SESSION: {last['mode']} ({last.get('case_id') or last.get('theme') or 'n/a'}) - next focus: {last.get('next_focus', '')}")
        done = [s.get("case_id") for s in sessions if s["mode"] == "case" and s.get("case_id")]
        if done:
            lines.append("CASES ALREADY PRACTICED: " + ", ".join(done))
    return "\n".join(lines)


def _user_text_count(session) -> int:
    n = 0
    for ev in session.events:
        if ev.author == "user" and ev.content and any(p.text for p in (ev.content.parts or [])):
            n += 1
    return n


def _build_transcript(session, start_idx: int) -> str:
    lines = []
    for ev in session.events[start_idx:]:
        if not ev.content:
            continue
        text = " ".join(p.text for p in (ev.content.parts or []) if p.text and not getattr(p, "thought", False)).strip()
        if not text:
            continue
        if ev.author == "user":
            lines.append(f"CANDIDATE: {text}")
        elif ev.author == "interviewer":
            lines.append(f"INTERVIEWER: {text}")
    return "\n\n".join(lines)




def delete_user_data(user_id: str) -> bool:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id or "anon")[:40]
    d = config.DATA_DIR / safe
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


def cleanup_old(ttl_hours: int = None) -> int:
    """Delete visitor folders not touched for ttl_hours."""
    ttl = (ttl_hours if ttl_hours is not None else config.DATA_TTL_HOURS) * 3600
    n = 0
    if not config.DATA_DIR.exists():
        return 0
    for d in config.DATA_DIR.iterdir():
        try:
            if d.is_dir() and time.time() - d.stat().st_mtime > ttl:
                shutil.rmtree(d, ignore_errors=True)
                n += 1
        except OSError:
            pass
    return n
