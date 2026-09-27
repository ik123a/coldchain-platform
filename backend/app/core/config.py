"""Config from environment."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./coldchain.db")
# JWT signing key resolution lives in app.core.security, which refuses to fall
# back to a well-known value outside development. Do not re-add a literal here.
JWT_SECRET = os.getenv("JWT_SECRET", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "")

# --- API keys --------------------------------------------------------------
# These previously carried hardcoded literal fallbacks, which put two LIVE
# Google/Gemini keys into tracked source: one matching .env, and a second
# ("...BACKUP") that is the SAME value exposed in git history at dfcd959. Both
# were therefore compromised, and because the code preferred the literal when
# the env var was absent, deleting .env would not have removed the exposure --
# the app would keep working with the embedded key.
#
# Now: env var only, empty by default. If it is missing, the AI design-reference
# service reports itself unavailable; the operational simulation does not use
# these keys at all (it is deterministic rule-based Python).
GEMINI_API_KEY_PRIMARY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_KEY_BACKUP = os.getenv("GEMINI_API_KEY_BACKUP", "")
GEMINI_API_KEYS = [k for k in [GEMINI_API_KEY_PRIMARY, GEMINI_API_KEY_BACKUP] if k]

GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
GEMINI_PREMIUM_IMAGE_MODEL = os.getenv("GEMINI_PREMIUM_IMAGE_MODEL", "gemini-3-pro-image")
GEMINI_VIDEO_MODEL = os.getenv("GEMINI_VIDEO_MODEL", "veo-3.1-generate-preview")
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
GEMINI_FALLBACK_TEXT_MODEL = os.getenv("GEMINI_FALLBACK_TEXT_MODEL", "gemini-3-flash-preview")

CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000").split(",") if o.strip()]
# Operational AI is the deterministic six-agent team in app/simulation/agents_d.py
# and fleet_agents.py — pure Python, zero API keys, no LLM at runtime. The Gemini
# service under app/services/gemini/ only generates design-reference images and is
# reachable solely through /api/gemini, so a key being present says nothing about
# how decisions are made. Report the mode that is actually true.
AI_MODE = "DETERMINISTIC-AGENTS"
