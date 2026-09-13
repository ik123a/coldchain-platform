"""Config from environment."""
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./coldchain.db")
JWT_SECRET = os.getenv("JWT_SECRET", "***REDACTED-JWT-PLACEHOLDER***")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "")
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000").split(",") if o.strip()]
AI_MODE = "LLM" if OPENAI_API_KEY else "DETERMINISTIC"
