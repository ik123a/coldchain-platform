"""Pytest bootstrap: redirect every test to a temp database.

Load this FIRST. conftest.py is imported by pytest before any test module, but
`app.database.engine` binds its URL at import time, so the redirect has to happen
at this point or not at all. See `_db_isolation.py` for the full reasoning.

This file deliberately does NOT touch the running application: it only sets an
environment variable in the *test process*.

DESIGN NOTE — why there is no session-scoped fixture here
---------------------------------------------------------
The first version asserted isolation from an autouse `scope="session"` fixture.
Under pytest-asyncio in STRICT mode that fixture is treated as an unmarked sync
generator, and the plugin's `pytest_fixture_setup` hook raised during setup, which
turned 28 tests across 6 files into ERRORs while every file passed on its own.
The check belongs at COLLECTION time, where it needs no fixture machinery and
cannot interfere with async tests.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _db_isolation import isolate  # noqa: E402

# Must happen before any `app.*` import anywhere in the test session.
isolate()

import pytest  # noqa: E402


def pytest_configure(config):
    """Fail the whole session early if the engine is not the temp one.

    Runs after conftest import but before test modules are collected/executed.
    `assert_isolated()` imports `app.database.engine`, whose URL is already fixed
    at that point, so it inspects the engine that will ACTUALLY be used rather
    than a hopeful environment variable.
    """
    from _db_isolation import assert_isolated

    try:
        url = assert_isolated()
    except AssertionError as exc:
        raise pytest.UsageError(str(exc)) from None
    config._cc_db_url = url  # surfaced by pytest_report_header


def pytest_report_header(config):
    return f"db-isolation: engine bound to {getattr(config, '_cc_db_url', '?')}"


@pytest.fixture(autouse=True)
def _schema_and_clean_state():
    """Create tables and clear per-test state so runs cannot leak into one another.

    Only ever touches the temp database: `pytest_configure` has already proven the
    engine is not the live one, and these DELETEs run through that engine.

    Deliberately sync at function scope, and it must work for both
    `unittest.IsolatedAsyncioTestCase` classes and plain sync tests. The project's
    async tests each get their own event loop, so the work is driven with
    `asyncio.run()` here rather than by pytest-asyncio.
    """
    import asyncio

    from sqlalchemy import text

    from app.database.engine import Base, engine
    # Models must be imported or Base.metadata is empty and create_all() is a
    # silent no-op, leaving every table missing.
    from app.models import entities as _entities  # noqa: F401
    from app.models import fleet as _fleet  # noqa: F401

    async def _prepare():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Explicit table list, not reflection: a reflected delete would
            # eventually include a table someone added that must be preserved.
            for table in ("ai_analyses", "incidents", "fleet_cargo_transfers",
                          "fleet_vehicle_events", "simulations"):
                try:
                    await conn.execute(text("DELETE FROM " + table))
                except Exception:
                    pass  # table not present in this schema version

    asyncio.run(_prepare())
    yield
