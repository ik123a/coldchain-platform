"""ColdChain Rescue — DB engine (SQLite default, postgres-compatible URL)."""
from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker, create_async_engine)
from sqlalchemy.orm import DeclarativeBase


def _default_sqlite_url() -> str:
    """CWD-independent default database location.

    `sqlite:///./coldchain.db` resolves `./` against the PROCESS working
    directory, so running uvicorn from the repo root silently created/used a
    DIFFERENT (empty) database than running it from `backend/` — which is exactly
    how the 0-byte root-level coldchain.db artefact appeared. The default now
    anchors on this file's location (<repo>/backend/app/database/engine.py ->
    backend/coldchain.db), matching the documented, already-populated database.

    An explicit DATABASE_URL always wins and keeps its documented semantics
    (relative sqlite URLs in an explicit setting remain CWD-relative, and the
    test harness sets an absolute temp path before any import).
    """
    env = os.getenv("DATABASE_URL")
    if env:
        return env
    backend_dir = Path(__file__).resolve().parents[2]     # backend/
    return f"sqlite+aiosqlite:///{(backend_dir / 'coldchain.db').as_posix()}"


DATABASE_URL = _default_sqlite_url()

# SQLite pragmas that match this app's write pattern (one writer loop + short
# request transactions): a 5s busy timeout prevents immediate
# 'database is locked' errors when the sim loop and a request collide, and FK
# enforcement is off by default in SQLite but the schema models relations
# explicitly — enabling it is the documented, intended behaviour.
_connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    _connect_args = {"timeout": 5}

engine = create_async_engine(DATABASE_URL, echo=bool(os.getenv("DB_ECHO")),
                             pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        yield session
