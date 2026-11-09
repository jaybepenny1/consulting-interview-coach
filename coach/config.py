"""All settings in one place. Secrets come ONLY from environment variables."""
import os
import logging
from pathlib import Path

MODEL = os.environ.get("COACH_MODEL", "gemini-3.5-flash-lite")
APP_NAME = "consulting_coach"
DATA_DIR = Path(os.environ.get("COACH_DATA_DIR", "/tmp/coach_data"))   # ephemeral on Cloud Run
DATA_TTL_HOURS = 24

# ---- cost / abuse caps (the "BEFORE YOU SHARE" limits) ----
MAX_OUTPUT_TOKENS = 1500           # per model answer
MAX_TOOL_CALLS_PER_TURN = 20       # per user message
MAX_LLM_CALLS_PER_TURN = 30        # per user message (ADK RunConfig)
MAX_MESSAGES_PER_SESSION = int(os.environ.get("COACH_MAX_MESSAGES", "30"))   # per visitor
GLOBAL_MESSAGES_PER_DAY = int(os.environ.get("COACH_GLOBAL_CAP", "300"))     # resets on restart
MAX_INPUT_CHARS = 1500
MAX_RESEARCH_CALLS = 8
MAX_PAGE_CHARS = 6000
MAX_PAGE_BYTES = 1_000_000
MAX_PLAN_CHARS = 3500
MAX_TURNS = {"case": 6, "behavioral": 4, "framework": 3, "math": 5}   # candidate answers per interview
MIN_SECONDS_BETWEEN_CALLS = float(os.environ.get("COACH_PACE", "1.0"))

for _n in ("google_adk", "google.adk", "google_genai", "google.genai", "httpx", "urllib3"):
    logging.getLogger(_n).setLevel(logging.ERROR)
