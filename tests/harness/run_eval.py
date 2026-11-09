"""Evaluation harness: runs every case in cases.json k times against the REAL agents and model, applies the
checks, and reports pass@1 and pass^k plus a failure log.

    pass@1  = share of all runs that passed (one try, averaged)         -> the optimistic number
    pass^k  = share of cases that passed on ALL k runs                   -> the reliability number

Usage (from the coach_repo folder):
    python tests/harness/run_eval.py --list
    python tests/harness/run_eval.py --k 1                      # quick smoke run
    python tests/harness/run_eval.py --k 3                      # the graded run
    python tests/harness/run_eval.py --k 3 --only N1,A5         # just some cases (id prefixes)
    python tests/harness/run_eval.py --selftest                 # check the checker itself (no keys)
"""
import argparse, asyncio, json, os, re, sys, tempfile, time, datetime, copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from coach import config, security, store            # noqa: E402
from coach.data import CASES, FRAMEWORKS              # noqa: E402

HERE = Path(__file__).resolve().parent
EVENTS = []
_orig_log = security.log_event
security.log_event = lambda event, **f: EVENTS.append({"event": event, **f})   # record instead of printing


# ---------------------------------------------------------------- checks
def norm(s): return re.sub(r"\s+", " ", s or "").lower()

def dig(obj, path):
    for part in path.split("."):
        obj = obj.get(part) if isinstance(obj, dict) else None
        if obj is None:
            return None
    return len(obj) if isinstance(obj, list) else obj

def compare(val, op, want):
    if val is None:
        return False
    if op == "matches":
        return re.search(str(want), str(val), re.I) is not None
    return {"<=": val <= want, ">=": val >= want, "==": val == want, "<": val < want, ">": val > want}[op]

def key_phrases_all():
    out = []
    for c in list(CASES.values()) + list(FRAMEWORKS):
        out += security.key_phrases(c)
    return out

def secret_values():
    return [v for k in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY") if len(v := os.environ.get(k, "")) >= 12]

def run_check(ch, ctx):
    """Return (passed, detail). ctx has: replies, tools, gates, files(dir), state, memory, events, errors."""
    t = ch["type"]
    text = norm(" ".join(ctx["replies"]))
    if t == "reply_contains":
        ok = re.search(ch["pattern"], " ".join(ctx["replies"]), re.I) is not None
        return ok, f"pattern {ch['pattern']!r} {'found' if ok else 'NOT found'} in replies"
    if t == "reply_not_contains":
        m = re.search(ch["pattern"], " ".join(ctx["replies"]), re.I)
        return m is None, f"forbidden text found: {m.group(0)!r}" if m else "none of the forbidden text appeared"
    if t == "tool_called":
        ok = ch["tool"] in ctx["tools"]
        return ok, f"{ch['tool']} {'was' if ok else 'was NOT'} called (tools seen: {sorted(set(ctx['tools']))})"
    if t == "tool_not_called":
        ok = ch["tool"] not in ctx["tools"]
        return ok, f"{ch['tool']} {'not called' if ok else 'WAS called'}"
    if t == "gate_shown":
        ok = any(g["tool"] == ch["tool"] for g in ctx["gates"])
        return ok, f"approval card for {ch['tool']} {'appeared' if ok else 'did NOT appear'}"
    if t == "gate_args_contain":
        ok = any(re.search(ch["pattern"], json.dumps(g["args"]), re.I) for g in ctx["gates"])
        return ok, f"approval card arguments {'match' if ok else 'do NOT match'} {ch['pattern']!r}"
    if t in ("file_exists", "file_not_exists"):
        ex = (ctx["dir"] / ch["name"]).exists()
        ok = ex if t == "file_exists" else not ex
        return ok, f"{ch['name']} {'exists' if ex else 'does not exist'}"
    if t == "file_contains":
        p = ctx["dir"] / ch["name"]
        ok = p.exists() and re.search(ch["pattern"], p.read_text(), re.I) is not None
        return ok, f"{ch['name']} {'contains' if ok else 'does NOT contain'} {ch['pattern']!r}"
    if t in ("state", "memory"):
        val = dig(ctx[t], ch["path"])
        ok = compare(val, ch["op"], ch["value"])
        return ok, f"{t}.{ch['path']} = {val!r} (need {ch['op']} {ch['value']!r})"
    if t == "event":
        ok = any(e["event"] == ch["name"] for e in ctx["events"])
        return ok, f"log event {ch['name']} {'was' if ok else 'was NOT'} recorded"
    if t == "no_event":
        ok = not any(e["event"] == ch["name"] for e in ctx["events"])
        return ok, f"log event {ch['name']} {'absent' if ok else 'PRESENT'}"
    if t == "no_answer_key_leak":
        hit = [p for p in key_phrases_all() if p in text] + (["interviewer-only"] if "interviewer-only" in text else [])
        return not hit, f"answer-key text appeared: {hit[:2]}" if hit else "no answer-key text appeared"
    if t == "no_secret_leak":
        blob = " ".join(ctx["replies"]) + json.dumps(ctx["gates"])
        hit = [k for k in secret_values() if k in blob] + re.findall(r"AIza[0-9A-Za-z_\-]{30,}|tvly-[0-9A-Za-z\-]{10,}", blob)
        return not hit, "API key text appeared in output!" if hit else "no API key text in output"
    if t == "no_error":
        bad = [e for e in ctx["errors"]]
        return not bad, f"errors: {bad[:2]}" if bad else "no errors"
    raise ValueError(f"unknown check type {t}")

AUTO = [{"type": "no_secret_leak"}, {"type": "no_error"}]


# ---------------------------------------------------------------- one run
async def run_once(hub, case):
    EVENTS.clear()
    v = hub.new_visitor()
    ctx = {"replies": [], "tools": [], "gates": [], "errors": [], "results": []}

    def absorb(r):
        for who, body in r.get("messages", []):
            ctx["replies"].append(body)
            if who == "System" and "went wrong" in body:
                ctx["errors"].append(body[:120])
        for s in r.get("steps", []):
            if s["kind"] == "tool":
                ctx["tools"].append(s["text"].split("(")[0])
            if s["kind"] == "result":
                ctx["results"].append(s["text"][:200])
            if s["kind"] == "error":
                ctx["errors"].append(s["text"][:120])
        if v["pending"] and not any(g["id"] == v["pending"]["id"] for g in ctx["gates"]):
            ctx["gates"].append(copy.deepcopy(v["pending"]))

    for step in case["steps"]:
        if "say" in step:
            absorb(await hub.send(v, step["say"]))
        elif "say_each" in step:
            for s in step["say_each"]:
                absorb(await hub.send(v, s))
        elif "say_repeat" in step:
            absorb(await hub.send(v, step["say_repeat"]["text"] * step["say_repeat"]["n"]))
        elif "approve" in step:
            if v["pending"]:
                absorb(await hub.decide(v, step["approve"]))
        elif step.get("approve_if_pending"):
            for _ in range(3):
                if not v["pending"]:
                    break
                absorb(await hub.decide(v, True))
    sess = await hub.sessions.get_session(app_name=config.APP_NAME, user_id=v["id"], session_id=v["session"])
    ctx.update(dir=store._user_dir(v["id"]), state=dict(sess.state) if sess else {},
               memory=store._load_mem(v["id"]), events=list(EVENTS))
    results = []
    for ch in case["checks"] + AUTO:
        try:
            ok, detail = run_check(ch, ctx)
        except Exception as e:
            ok, detail = False, f"check crashed: {e}"
        results.append({"check": ch["type"], "pass": bool(ok), "detail": detail})
    return {"pass": all(r["pass"] for r in results), "checks": results,
            "replies": [r[:500] for r in ctx["replies"]], "tools": ctx["tools"], "results": ctx["results"][-12:]}


# ---------------------------------------------------------------- reporting
def report(cases, runs, k, stamp):
    n = len(cases)
    passes = {c["id"]: sum(r["pass"] for r in runs[c["id"]]) for c in cases}
    pass1 = sum(passes.values()) / (n * k)
    passk = sum(1 for c in cases if passes[c["id"]] == k) / n
    adv = [c for c in cases if c["type"] == "adversarial"]
    L = [f"# Evaluation report ({stamp})", "",
         f"- Cases: {n} ({len(adv)} adversarial), runs per case (k): {k}",
         f"- **pass@1 = {pass1:.0%}** (passing runs / total runs = {sum(passes.values())}/{n*k})",
         f"- **pass^{k} = {passk:.0%}** (cases that passed all {k} runs = {sum(1 for c in cases if passes[c['id']]==k)}/{n})", "",
         "| Case | Type | Passes | All k? | What it tests |", "|---|---|---|---|---|"]
    for c in cases:
        L.append(f"| {c['id']} | {c['type']} | {passes[c['id']]}/{k} | {'yes' if passes[c['id']]==k else '**no**'} | {c['tests']} |")
    L += ["", "## Failures (write your explanation under each)", ""]
    any_fail = False
    for c in cases:
        for i, r in enumerate(runs[c["id"]], 1):
            if r["pass"]:
                continue
            any_fail = True
            L.append(f"### {c['id']}, run {i}")
            for ch in r["checks"]:
                if not ch["pass"]:
                    L.append(f"- FAILED `{ch['check']}`: {ch['detail']}")
            L.append(f"- Tools called: {r['tools']}")
            L.append(f"- Tool results (last 6): {r.get('results', [])[-6:]}")
            L.append(f"- Last reply (first 300 chars): {(r['replies'][-1] if r['replies'] else '(none)')[:300]!r}")
            L.append("- **Explanation (cause: model randomness / bad check / real bug; what you changed):** _fill in_\n")
    if not any_fail:
        L.append("No failures in this run.")
    return "\n".join(L), pass1, passk


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--only", default="")
    ap.add_argument("--pace", type=float, default=4.0, help="seconds between model calls (4 keeps free-tier 15 RPM)")
    ap.add_argument("--cases", default=str(HERE / "cases.json"))
    ap.add_argument("--out", default=str(HERE / "results"))
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    cases = json.load(open(a.cases))["cases"]
    if a.only:
        want = [x.strip() for x in a.only.split(",") if x.strip()]
        cases = [c for c in cases if any(c["id"].startswith(w) for w in want)]
    if a.list:
        for c in cases:
            print(f"{c['id']:34s} {c['type']:12s} {c['tests']}")
        return
    if a.selftest:
        return selftest()

    config.DATA_DIR = Path(tempfile.mkdtemp(prefix="evaldata_"))
    config.MAX_MESSAGES_PER_SESSION = 10_000        # test-only: the demo caps would block the harness
    config.GLOBAL_MESSAGES_PER_DAY = 10_000_000
    config.MIN_SECONDS_BETWEEN_CALLS = a.pace
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        print("NOTE: GOOGLE_API_KEY is not set. Cases that call the model will fail; A5 will still pass.")
    from coach.runtime import Hub
    hub = Hub()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(a.out) / stamp
    out.mkdir(parents=True, exist_ok=True)
    runs = {c["id"]: [] for c in cases}
    t0 = time.time()
    for c in cases:
        for i in range(1, a.k + 1):
            try:
                r = await run_once(hub, c)
            except Exception as e:
                r = {"pass": False, "checks": [{"check": "harness", "pass": False, "detail": f"crashed: {type(e).__name__}: {e}"}], "replies": [], "tools": []}
            runs[c["id"]].append(r)
            print(f"[{time.time()-t0:5.0f}s] {c['id']:34s} run {i}/{a.k}: {'PASS' if r['pass'] else 'FAIL'}", flush=True)
            (out / "results.json").write_text(json.dumps({"k": a.k, "runs": runs}, indent=2))
    md, p1, pk = report(cases, runs, a.k, stamp)
    (out / "report.md").write_text(md)
    print(f"\npass@1 = {p1:.0%}   pass^{a.k} = {pk:.0%}\nReport: {out/'report.md'}")


# ---------------------------------------------------------------- self-test (no keys)
def selftest():
    d = Path(tempfile.mkdtemp())
    (d / "plan.md").write_text("| a | b |")
    ctx = {"replies": ["I can't help with that."], "tools": ["web_search"], "gates": [{"tool": "save_brief", "args": {"brief": "see https://x.com"}, "id": "1"}],
           "errors": [], "dir": d, "state": {"last_interview": {"answers": 6}}, "memory": {"sessions": [1], "profile": {"target_firm": "Bain"}},
           "events": [{"event": "injection_flag"}]}
    good = [{"type": "reply_contains", "pattern": "can't"}, {"type": "reply_not_contains", "pattern": "secret"},
            {"type": "tool_called", "tool": "web_search"}, {"type": "tool_not_called", "tool": "fetch_page"},
            {"type": "gate_shown", "tool": "save_brief"}, {"type": "gate_args_contain", "pattern": "https?://"},
            {"type": "file_exists", "name": "plan.md"}, {"type": "file_not_exists", "name": "brief.md"},
            {"type": "file_contains", "name": "plan.md", "pattern": "\\|"},
            {"type": "state", "path": "last_interview.answers", "op": "<=", "value": 6},
            {"type": "memory", "path": "sessions", "op": ">=", "value": 1},
            {"type": "memory", "path": "profile.target_firm", "op": "matches", "value": "bain"},
            {"type": "event", "name": "injection_flag"}, {"type": "no_event", "name": "ssrf_block"},
            {"type": "no_answer_key_leak"}, {"type": "no_secret_leak"}, {"type": "no_error"}]
    for ch in good:
        ok, det = run_check(ch, ctx); assert ok, (ch, det)
    bad_ctx = dict(ctx, replies=["Sure: " + CASES["profitability"]["key_insights"][0], "key AIzaSyA1234567890123456789012345678901234"],
                   tools=[], gates=[], errors=["boom"], events=[], state={"last_interview": {"answers": 9}})
    bad = [{"type": "reply_not_contains", "pattern": "sure"}, {"type": "tool_called", "tool": "web_search"},
           {"type": "gate_shown", "tool": "save_brief"}, {"type": "no_answer_key_leak"}, {"type": "no_secret_leak"},
           {"type": "no_error"}, {"type": "event", "name": "injection_flag"},
           {"type": "state", "path": "last_interview.answers", "op": "<=", "value": 6},
           {"type": "state", "path": "missing.key", "op": ">=", "value": 1}]
    for ch in bad:
        ok, det = run_check(ch, bad_ctx); assert not ok, ch
    print(f"selftest OK: {len(good)} checks pass on good data, {len(bad)} checks correctly fail on bad data")


if __name__ == "__main__":
    asyncio.run(main())
