"""Redirect the application's database engine to a throwaway temp file.

WHY THIS MUST BE THE FIRST IMPORT IN A DB-WRITING TEST
------------------------------------------------------
`app/database/engine.py` binds the URL at **import time**:

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./coldchain.db")
    engine = create_async_engine(DATABASE_URL, ...)
    SessionLocal = async_sessionmaker(engine, ...)

and `fleet_orchestrator.py:23` does `from ..database.engine import SessionLocal`,
which captures a **direct reference** to that sessionmaker. So setting
`DATABASE_URL` (or even re-assigning `engine`) after those modules are imported
changes nothing — every write still goes to the live `./coldchain.db`.

The only reliable mechanism is to set the environment variable before any `app.*`
module is imported. `conftest.py` runs before test modules under pytest; for
direct `python tests/foo.py` runs the test file imports this module first.

Two independent guarantees, not one:
  1. `isolate()` redirects DATABASE_URL to a fresh temp directory.
  2. `assert_isolated()` inspects the engine ACTUALLY bound after import and
     raises if it points at the live file. An env var that was set but ignored
     therefore fails loudly instead of silently writing to production data.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile

# The live filenames this must never resolve to. `./coldchain.db` is reached
# relative to the CWD, which is why two live copies exist on this machine.
_LIVE_FILENAMES = ("coldchain.db",)

_TMP_DIR: str | None = None
_TMP_URL: str | None = None


def isolate() -> str:
    """Point DATABASE_URL at a fresh temp SQLite file. Idempotent.

    If CC_TEST_ISOLATION_OFF is set, this is a no-op — that switch exists ONLY so
    the guard itself can be negative-tested (proving it fails when isolation is
    absent). It must never be set during a normal run.
    """
    global _TMP_DIR, _TMP_URL
    if os.environ.get("CC_TEST_ISOLATION_OFF") == "1":
        _TMP_URL = os.environ.get("DATABASE_URL", "")
        return _TMP_URL
    if _TMP_URL is not None:
        return _TMP_URL

    # If a previous call in this process already set the marker, respect it —
    # a test module being imported twice must not create a second database.
    existing = os.environ.get("CC_TEST_ISOLATED")
    if existing == "1" and os.environ.get("DATABASE_URL"):
        _TMP_URL = os.environ["DATABASE_URL"]
        return _TMP_URL

    _TMP_DIR = tempfile.mkdtemp(prefix="cc_test_")
    # Forward slashes: SQLAlchemy parses a Windows backslash path as an escape.
    _TMP_URL = "sqlite+aiosqlite:///" + os.path.join(_TMP_DIR, "test.db").replace("\\", "/")
    os.environ["DATABASE_URL"] = _TMP_URL
    os.environ["CC_TEST_ISOLATED"] = "1"

    # Never touch an existing SQLite file: the temp dir is ours alone and is
    # removed on exit. remove_ignore_errors=True keeps a Windows file-lock
    # (aiosqlite pool still open) from turning a green run red.
    atexit.register(shutil.rmtree, _TMP_DIR, True)
    return _TMP_URL


def assert_isolated() -> str:
    """Assert the bound engine is the temp one. Call AFTER importing the engine.

    Checks `engine.url` — the value actually used — not the environment, so a
    module imported before this one cannot hide behind a hopeful env var.
    """
    from app.database.engine import engine  # imported here on purpose

    url = str(engine.url)
    if "cc_test_" not in url:
        raise AssertionError(
            f"TEST ISOLATION FAILED: the engine is bound to {url!r}, which is not "
            f"a temp test database. DATABASE_URL must be set before any app module "
            f"is imported — check that _db_isolation.isolate() ran first. Refusing "
            f"to run tests against an unknown database."
        )
    for live in _LIVE_FILENAMES:
        if live in url:
            raise AssertionError(
                f"TEST ISOLATION FAILED: the engine is bound to the LIVE database "
                f"({url!r})."
            )
    return url


def setup_called_from_conftest() -> str:
    """conftest.py entry point: isolate now, assert once the engine exists."""
    return isolate()
