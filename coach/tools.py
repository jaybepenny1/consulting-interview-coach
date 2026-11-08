"""Tools. Each agent only gets the tools it needs (permission isolation): see agents.py."""
import os
import re
import json
import random
import datetime

from bs4 import BeautifulSoup
from google.adk.tools import ToolContext

from . import config, security
from .config import MAX_TURNS, MAX_RESEARCH_CALLS, MAX_PAGE_CHARS, MAX_PLAN_CHARS
from .data import CASES, BEHAVIORAL, BEHAVIORAL_PROBES, FRAMEWORKS, RUBRICS
from .store import (_short, _user_dir, _load_mem, _save_mem, _dim_stats, _memory_text,
                    _user_text_count, _build_transcript)


# =====================================================================
# COACH TOOLS: profile and memory
# =====================================================================
def get_memory_summary(tool_context: ToolContext) -> str:
    """Return what is known about this candidate: saved profile, graded practice history,
    weakest and strongest areas, math drill accuracy, and cases already practiced."""
    return _memory_text(tool_context.user_id)


def save_profile(
    tool_context: ToolContext,
    target_firm: str,
    target_role: str,
    days_available: int,
    experience_level: str,
    strengths: str,
    weaknesses: str,
    requests: str = "",
) -> str:
    """Save or update the candidate's profile after intake.

    Args:
        target_firm: Firm the candidate is interviewing with, e.g. 'Bain & Company'.
        target_role: Role, e.g. 'Associate Consultant Intern'.
        days_available: Days left before the interview (use 14 if unknown).
        experience_level: One of 'beginner', 'intermediate', 'advanced'.
        strengths: Short list of self-reported strengths, comma separated.
        weaknesses: Short list of self-reported weaknesses, comma separated.
        requests: What the candidate specifically asked to work on, if anything.
    """
    level = (experience_level or "").strip().lower()
    if level not in ("beginner", "intermediate", "advanced"):
        return "ERROR: experience_level must be beginner, intermediate or advanced."
    mem = _load_mem(tool_context.user_id)
    mem["profile"] = {
        "target_firm": target_firm,
        "target_role": target_role,
        "days_available": int(days_available),
        "experience_level": level,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "requests": requests,
        "updated": datetime.date.today().isoformat(),
    }
    _save_mem(tool_context.user_id, mem)
    tool_context.state["profile"] = mem["profile"]
    return "Profile saved: " + json.dumps(mem["profile"])


# =====================================================================
# RESEARCHER TOOLS: search, read, save (with verification)
# =====================================================================
def _get_tavily():
    from tavily import TavilyClient
    return TavilyClient(api_key=os.environ["TAVILY_API_KEY"])


def _norm_url(u: str) -> str:
    u = u.strip().rstrip(".,);]>")
    u = re.sub(r"^https?://(www\.)?", "", u, flags=re.I)
    return u.rstrip("/").lower()


def _remember_urls(tool_context: ToolContext, urls) -> None:
    seen = list(tool_context.state.get("seen_urls", []))
    for u in urls:
        if u:
            n = _norm_url(u)
            if n not in seen:
                seen.append(n)
    tool_context.state["seen_urls"] = seen


def _research_budget(tool_context: ToolContext):
    used = int(tool_context.state.get("research_calls", 0)) + 1
    tool_context.state["research_calls"] = used
    if used > MAX_RESEARCH_CALLS:
        return f"BUDGET EXHAUSTED: {MAX_RESEARCH_CALLS} research calls used. Call save_brief now with what you have; mark anything unverified."
    return None


def web_search(tool_context: ToolContext, reasoning: str, query: str) -> str:
    """Search the web. Returns the top 5 results with title, url and a text excerpt.

    Args:
        reasoning: One sentence on why you are making this search and what you hope to learn.
        query: A plain-language search query (no site: operators or quotation marks).
    """
    over = _research_budget(tool_context)
    if over:
        return over
    try:
        data = _get_tavily().search(query=query, max_results=5)
        results = [
            {"title": r.get("title"), "url": r.get("url"), "snippet": (r.get("content") or "")[:500]}
            for r in data.get("results", [])
        ]
        _remember_urls(tool_context, [r["url"] for r in results])
        if not results:
            return "No results found. Try different wording."
        return security.wrap_untrusted(json.dumps(results, indent=2), "search results")
    except Exception as e:
        return f"ERROR: search failed ({_short(e, 200)})"


def fetch_page(tool_context: ToolContext, reasoning: str, url: str) -> str:
    """Download a web page and return its cleaned text (first several thousand characters).

    Args:
        reasoning: One sentence on why you are reading this page and what you hope to learn.
        url: A full http or https URL taken from a search result.
    """
    over = _research_budget(tool_context)
    if over:
        return over
    try:
        resp = security.safe_get(url)
        soup = BeautifulSoup(resp.content.decode(resp.encoding or "utf-8", errors="ignore"), "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        _remember_urls(tool_context, [url, getattr(resp, "final_url", url)])
        if not text:
            return "Page had no readable text."
        return security.wrap_untrusted(text[:MAX_PAGE_CHARS], url)
    except security.BlockedURL as e:
        security.log_event("ssrf_block", url=_short(url, 200), reason=str(e))
        return f"ERROR: that URL is not allowed ({e}). Use a public https URL from your search results."
    except Exception as e:
        return f"ERROR: could not fetch page ({_short(e, 200)})"


def validate_brief(tool_context: ToolContext, brief: str):
    """Return an error string if the brief is not acceptable, else None."""
    headings = [ln.lower() for ln in brief.splitlines() if ln.lstrip().startswith("#")]
    missing = [k for k in ("interview", "screens", "news", "prep") if not any(k in h for h in headings)]
    if missing:
        return ("REJECTED: missing section(s) for keywords " + ", ".join(missing)
                + ". Use headings: Interview Format, What the Firm Screens For, Recent News, Prep Priorities.")
    cited = {_norm_url(u) for u in re.findall(r"https?://[^\s)\]>]+", brief)}
    seen = set(tool_context.state.get("seen_urls", []))
    unseen = sorted(c for c in cited if c not in seen)
    if unseen:
        return ("REJECTED: these URLs were never returned by a tool in this session, so they may be wrong: "
                + "; ".join(unseen) + ". Remove them or replace them with URLs from your search results.")
    if len(cited) < 3:
        return "REJECTED: cite at least 3 distinct source URLs from your research."
    news, capture = "", False
    for ln in brief.splitlines():
        if ln.lstrip().startswith("#"):
            capture = "news" in ln.lower()
            continue
        if capture:
            news += ln + "\n"
    if "http" not in news and "no verified recent news" not in news.lower():
        return ("REJECTED: the Recent News section needs a sourced item, or the exact words "
                "'No verified recent news found' if your search found none. Do not write news from memory.")
    if len(brief) > 6000:
        return "REJECTED: brief is too long. Keep it under 500 words."
    return None


def save_brief(tool_context: ToolContext, reasoning: str, brief: str) -> str:
    """Save the finished firm brief. The candidate is shown the exact text and must approve it first.
    The brief must have the four required sections and may only cite URLs that the tools returned.

    Args:
        reasoning: One sentence on why you now have enough information to write the brief.
        brief: The full brief in markdown with these headings: Interview Format, What the Firm
            Screens For, Recent News, Prep Priorities. Every claim needs a source URL.
    """
    err = validate_brief(tool_context, brief)
    if err:
        return err
    path = _user_dir(tool_context.user_id) / "brief.md"
    path.write_text(brief)
    tool_context.state["research_calls"] = 0
    tool_context.state["brief_saved"] = True
    return "Brief approved and saved."


# =====================================================================
# PLANNER TOOLS
# =====================================================================
def read_brief(tool_context: ToolContext) -> str:
    """Return the saved firm brief for this candidate, or say none exists."""
    path = _user_dir(tool_context.user_id) / "brief.md"
    return path.read_text() if path.exists() else "NO BRIEF SAVED YET. Ask the researcher to create one first."


def save_plan(tool_context: ToolContext, plan_markdown: str) -> str:
    """Save the prep plan. Must be short and contain a day-by-day markdown table.

    Args:
        plan_markdown: The plan in markdown: a one-line summary, a table with one row per day or
            block of days, and a short 'Do today' list. Under 3500 characters.
    """
    if "|" not in plan_markdown:
        return "REJECTED: include a markdown table (Day | Focus | Tasks | Time)."
    if len(plan_markdown) > MAX_PLAN_CHARS:
        return f"REJECTED: plan is {len(plan_markdown)} characters. Shorten it to under {MAX_PLAN_CHARS}."
    path = _user_dir(tool_context.user_id) / "plan.md"
    path.write_text(plan_markdown)
    return f"Plan saved to {path}."


# =====================================================================
# INTERVIEWER TOOLS: sessions, case pack, math drills
# =====================================================================
def _pick_case(mem: dict, case_type: str):
    key = (case_type or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in CASES:
        return key
    done = [s.get("case_id") for s in mem.get("sessions", []) if s["mode"] == "case"]
    fresh = [k for k in CASES if k not in done]
    return random.choice(fresh or list(CASES))


def start_interview(tool_context: ToolContext, mode: str, case_type: str = "", theme: str = "") -> str:
    """Begin a practice session and get the interviewer-only materials. Call this exactly once at the start.

    Args:
        mode: 'case', 'behavioral', 'framework' or 'math'.
        case_type: For case mode only: 'profitability', 'market_entry', 'market_sizing' or 'operations'. Leave blank to choose automatically.
        theme: For behavioral mode only: 'leadership', 'teamwork_conflict', 'drive_resilience', 'change_initiative' or 'failure_learning'. Leave blank to choose automatically.
    """
    mode = (mode or "").strip().lower()
    if mode not in MAX_TURNS:
        return "ERROR: mode must be case, behavioral, framework or math."
    cur = tool_context.state.get("interview") or {}
    if cur.get("active"):
        return "ERROR: a session is already active. Call end_interview first."
    mem = _load_mem(tool_context.user_id)
    session = tool_context.session
    info = {
        "active": True,
        "mode": mode,
        "case_id": "",
        "theme": "",
        "max_turns": MAX_TURNS[mode],
        "start_user_msgs": _user_text_count(session),
        "start_event_index": len(session.events),
        "started": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    firm = (mem.get("profile") or {}).get("target_firm", "")
    n = MAX_TURNS[mode]
    if mode == "case":
        cid = _pick_case(mem, case_type)
        c = CASES[cid]
        info["case_id"] = cid
        tool_context.state["interview"] = info
        clar = "\n".join(f"  - {k}: {v}" for k, v in c["clarifying"].items())
        return (
            f"SESSION STARTED: case ({cid}). The candidate gets {n} answers in total.\n"
            f"INTERVIEWER-ONLY MATERIALS (never read these out unprompted):\n"
            f"TITLE: {c['title']}\n"
            f"OPENING PROMPT (read this to the candidate): {c['prompt']}\n"
            f"CLARIFYING FACTS (give only the fact asked about):\n{clar}\n"
            f"EXHIBIT (show when the candidate asks about costs/data, or at turn 3):\n{c['exhibit']}\n"
            f"MATH QUESTION (ask around turn 3 or 4): {c['math_question']}\n"
            f"CORRECT MATH ANSWER (do not reveal until they answer): {c['math_answer']}\n"
            f"KEY INSIGHTS (to steer, never to read out): " + " | ".join(c["key_insights"]) + "\n"
            f"PLAN: turn 1 structure; turn 2 clarifying/data; turn 3 exhibit or math; turn 4 insight; turn {n-1} ask for the final recommendation; turn {n} closing."
        )
    if mode == "behavioral":
        stats = _dim_stats(mem)
        key = (theme or "").strip().lower()
        if key not in BEHAVIORAL:
            key = random.choice(list(BEHAVIORAL))
        info["theme"] = key
        tool_context.state["interview"] = info
        b = BEHAVIORAL[key]
        deep = "mckinsey" in firm.lower()
        style = ("Single-story deep dive (McKinsey-style): ask ONE question, then probe the same story with every follow-up."
                 if deep else
                 "Fit-style: ask one question, probe it 2 times, then ask a second question from the same theme if turns remain.")
        return (
            f"SESSION STARTED: behavioral ({b['label']}). The candidate gets {n} answers in total.\n"
            f"STYLE: {style}\n"
            f"QUESTIONS: " + " | ".join(b["questions"]) + "\n"
            f"FOLLOW-UP PROBES (use one at a time, based on what was missing): " + " | ".join(BEHAVIORAL_PROBES) + "\n"
            f"PLAN: turn 1 opening answer; turns 2 to {n-1} probes; turn {n} closing."
        )
    if mode == "framework":
        fw = random.choice(FRAMEWORKS)
        info["case_id"] = fw["id"]
        tool_context.state["interview"] = info
        return (
            f"SESSION STARTED: framework drill ({fw['id']}). The candidate gets {n} answers in total.\n"
            f"PROMPT (read to the candidate): {fw['prompt']}\n"
            f"STRONG STRUCTURE (never read out): " + " | ".join(fw["strong"]) + "\n"
            f"PLAN: turn 1 they give a structure; turn 2 probe one gap or overlap; turn {n} ask which branch to start with and why."
        )
    tool_context.state["interview"] = info
    return (f"SESSION STARTED: math drill. {n} problems. For each, call get_math_problem, read the "
            f"question, wait for the answer, then call check_math_answer.")


def end_interview(tool_context: ToolContext) -> str:
    """End the active practice session and save its transcript. Call this after the closing remark."""
    info = dict(tool_context.state.get("interview") or {})
    if not info.get("active"):
        return "ERROR: no active session."
    session = tool_context.session
    transcript = _build_transcript(session, info.get("start_event_index", 0))
    answers = _user_text_count(session) - info.get("start_user_msgs", 0)
    info["active"] = False
    info["ended"] = datetime.datetime.now().isoformat(timespec="seconds")
    tool_context.state["interview"] = info
    record = {
        "mode": info["mode"], "case_id": info.get("case_id", ""), "theme": info.get("theme", ""),
        "answers": answers, "transcript": transcript, "feedback_saved": False,
    }
    tool_context.state["last_interview"] = record
    tdir = _user_dir(tool_context.user_id) / "transcripts"
    tdir.mkdir(exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    (tdir / f"{stamp}_{info['mode']}.txt").write_text(transcript)
    if info["mode"] == "math":
        return f"Session ended after {answers} answers. NEXT: give a one-line score summary, then transfer to coach."
    return f"Session ended after {answers} candidate answers. NEXT: transfer to critic for feedback."


def _gen_math(difficulty: str):
    r = random.Random()
    d = (difficulty or "medium").lower()
    if d == "easy":
        if r.random() < 0.5:
            rev = r.choice([40, 50, 60, 80, 90])
            cost = round(rev * r.choice([0.55, 0.65, 0.75, 0.8]), 1)
            ans = round((rev - cost) / rev * 100, 1)
            return (f"A company has revenue of ${rev}M and total costs of ${cost}M. What is its profit margin? Answer in percent.",
                    ans, f"Profit = {rev} - {cost} = {round(rev-cost,1)}. Margin = {round(rev-cost,1)} / {rev} = {ans}%.")
        a = r.choice([120, 150, 180, 240, 300])
        b = round(a * r.choice([0.85, 0.9, 1.1, 1.2, 1.35]))
        ans = round((b - a) / a * 100, 1)
        return (f"Sales were {a} units last year and {b} units this year. What is the percent change? Answer in percent (negative if a decline).",
                ans, f"Change = {b} - {a} = {b-a}. Percent change = {b-a} / {a} = {ans}%.")
    if d == "hard":
        if r.random() < 0.5:
            fixed = r.choice([120000, 180000, 240000, 300000])
            price = r.choice([40, 50, 60])
            var = price - r.choice([10, 15, 20])
            ans = round(fixed / (price - var))
            return (f"A product sells for ${price} with variable cost of ${var} per unit and fixed costs of ${fixed:,}. How many units are needed to break even? Answer in units.",
                    ans, f"Contribution per unit = {price} - {var} = {price-var}. Breakeven = {fixed:,} / {price-var} = {ans:,} units.")
        inv = r.choice([30, 45, 60, 90])
        rev = r.choice([40, 50, 60, 80])
        m = r.choice([20, 25, 30])
        ans = round(inv / (rev * m / 100), 1)
        return (f"A ${inv}M investment will generate ${rev}M of annual revenue at a {m}% operating margin. What is the simple payback period? Answer in years, one decimal.",
                ans, f"Annual profit = {rev} x {m}% = {round(rev*m/100,2)}M. Payback = {inv} / {round(rev*m/100,2)} = {ans} years.")
    if r.random() < 0.5:
        units = r.choice([8000, 10000, 12000, 15000])
        price = r.choice([40, 45, 50])
        var = price - r.choice([12, 15, 18])
        fixed = r.choice([90000, 120000, 150000])
        ans = round((units * (price - var) - fixed) / 1000, 1)
        return (f"A firm sells {units:,} units at ${price} with variable cost of ${var} per unit and fixed costs of ${fixed:,}. What is its profit? Answer in $ thousands.",
                ans, f"Contribution = {units:,} x {price-var} = {units*(price-var):,}. Profit = {units*(price-var):,} - {fixed:,} = {int(ans*1000):,}, i.e. ${ans}K.")
    pop = r.choice([6, 8, 10, 12])
    seg = r.choice([20, 25, 40])
    share = r.choice([5, 10, 15])
    spend = r.choice([60, 90, 120, 200])
    ans = round(pop * seg / 100 * share / 100 * spend, 2)
    return (f"A market has {pop}M people. {seg}% fit the target segment, a company wins {share}% of that segment, and each customer spends ${spend} a year. What is the company's annual revenue? Answer in $ millions.",
            ans, f"{pop}M x {seg}% = {pop*seg/100}M in segment; x {share}% = {round(pop*seg/100*share/100,3)}M customers; x ${spend} = ${ans}M.")


def get_math_problem(tool_context: ToolContext, difficulty: str = "medium") -> str:
    """Generate one consulting-style math problem with a hidden correct answer.

    Args:
        difficulty: 'easy', 'medium' or 'hard'.
    """
    q, ans, sol = _gen_math(difficulty)
    tool_context.state["math_current"] = {"question": q, "answer": ans, "solution": sol}
    return "READ THIS PROBLEM TO THE CANDIDATE: " + q


def check_math_answer(tool_context: ToolContext, answer: float) -> str:
    """Check the candidate's numeric answer against the hidden correct answer and update their math record.

    Args:
        answer: The number the candidate gave, in the units the problem asked for.
    """
    cur = tool_context.state.get("math_current")
    if not cur:
        return "ERROR: no active math problem. Call get_math_problem first."
    ok = abs(float(answer) - cur["answer"]) <= max(abs(cur["answer"]) * 0.015, 0.15)
    mem = _load_mem(tool_context.user_id)
    m = mem.setdefault("math", {"attempted": 0, "correct": 0})
    m["attempted"] += 1
    m["correct"] += 1 if ok else 0
    _save_mem(tool_context.user_id, mem)
    tool_context.state["math_current"] = None
    verdict = "CORRECT" if ok else "NOT CORRECT"
    return f"{verdict}. Correct answer: {cur['answer']}. Worked solution: {cur['solution']} Running score: {m['correct']}/{m['attempted']}."


# =====================================================================
# CRITIC TOOLS
# =====================================================================
def get_interview_for_review(tool_context: ToolContext) -> str:
    """Return the most recent completed session: transcript, rubric, and the answer key."""
    rec = tool_context.state.get("last_interview")
    if not rec:
        return "NO COMPLETED SESSION FOUND. Tell the candidate to run a mock interview first."
    mode = rec["mode"]
    rub = RUBRICS[mode]
    dims = "\n".join(f"  - {k}: {v}" for k, v in rub["dims"].items())
    key = ""
    if mode == "case" and rec.get("case_id") in CASES:
        c = CASES[rec["case_id"]]
        key = ("ANSWER KEY: insights: " + " | ".join(c["key_insights"]) + "\nSTRONG STRUCTURE: "
               + " | ".join(c["strong_structure"]) + f"\nMATH ANSWER: {c['math_answer']}\nRECOMMENDATION: {c['recommendation_hint']}")
    if mode == "framework":
        for fw in FRAMEWORKS:
            if fw["id"] == rec.get("case_id"):
                key = "STRONG STRUCTURE: " + " | ".join(fw["strong"])
    return (f"MODE: {mode} ({rec.get('case_id') or rec.get('theme')}); candidate answers: {rec['answers']}\n"
            f"RUBRIC (score each 1-5; study aid, not any firm's official criteria):\n{dims}\n{key}\n"
            f"TRANSCRIPT:\n{rec['transcript'] or '(empty)'}")


def save_feedback(
    tool_context: ToolContext,
    scores_json: str,
    strengths: str,
    improvements: str,
    next_focus: str,
) -> str:
    """Save the graded result to the candidate's memory. Call once, after reading the transcript.

    Args:
        scores_json: A JSON object mapping EVERY rubric dimension name to an integer 1-5.
        strengths: The top two strengths, one sentence.
        improvements: The top two things to improve, one sentence.
        next_focus: The single most useful next drill, one sentence.
    """
    rec = dict(tool_context.state.get("last_interview") or {})
    if not rec:
        return "ERROR: no completed session to grade."
    if rec.get("feedback_saved"):
        return "Feedback for this session is already saved. Do not save again."
    try:
        scores = json.loads(scores_json)
    except Exception:
        return "ERROR: scores_json must be valid JSON, e.g. a mapping of dimension name to integer."
    dims = list(RUBRICS[rec["mode"]]["dims"])
    if sorted(scores) != sorted(dims):
        return f"ERROR: scores must contain exactly these dimensions: {', '.join(dims)}."
    for k, v in scores.items():
        if not isinstance(v, int) or not 1 <= v <= 5:
            return f"ERROR: score for {k} must be an integer from 1 to 5."
    mem = _load_mem(tool_context.user_id)
    mem["sessions"].append({
        "time": datetime.datetime.now().isoformat(timespec="seconds"),
        "mode": rec["mode"], "case_id": rec.get("case_id", ""), "theme": rec.get("theme", ""),
        "scores": scores, "strengths": strengths, "improvements": improvements, "next_focus": next_focus,
    })
    _save_mem(tool_context.user_id, mem)
    rec["feedback_saved"] = True
    tool_context.state["last_interview"] = rec
    return "Feedback saved to memory.\n" + _memory_text(tool_context.user_id)


# =====================================================================
# WRITER TOOL
# =====================================================================
def save_story(tool_context: ToolContext, title: str, framework: str, story: str) -> str:
    """Save an approved behavioral story to the candidate's story bank.

    Args:
        title: Short title for the story.
        framework: 'STAR' or 'CAR'.
        story: The final story text.
    """
    path = _user_dir(tool_context.user_id) / "stories.md"
    if path.exists() and path.stat().st_size > 20000:
        return "ERROR: story bank is full for this demo."
    story = story[:3000]
    with open(path, "a") as f:
        f.write(f"\n## {title} ({framework})\n\n{story}\n")
    return f"Story saved to {path}."
