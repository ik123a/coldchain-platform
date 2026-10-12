"""Prove the isolation mechanism works BEFORE any DB-writing test is run.

Asserts, with the real engine:
  1. The engine's bound URL is a temp path, not ./coldchain.db.
  2. The resolved file path is inside the temp dir, not the repo.
  3. A write through SessionLocal lands in the temp file, not the live one.
  4. The live database files are not modified by that write (byte-compare).

Run:  backend\\.venv\\Scripts\\python.exe tests\\verify_db_isolation.py
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _db_isolation import assert_isolated, isolate  # noqa: E402

isolate()

LIVE_FILES = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "coldchain.db"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "coldchain.db"),
]


def digest(path: str) -> str | None:
    if not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main() -> int:
    before = {p: digest(p) for p in LIVE_FILES}
    print("live DB digests before:")
    for p, d in before.items():
        print(f"  {d[:16] if d else '(absent)':18} {p}")

    url = assert_isolated()
    print(f"\nengine bound to: {url}")

    from app.database.engine import engine
    print(f"engine.url      : {engine.url}")
    print(f"database file   : {engine.url.database}")

    db_path = str(engine.url.database or "")
    assert "cc_test_" in db_path, f"not a temp path: {db_path}"
    assert "coldchain.db" not in db_path, f"resolved to the LIVE file: {db_path}"

    # A real write through the same sessionmaker the orchestrator uses.
    import asyncio

    from sqlalchemy import text

    from app.database.engine import Base, SessionLocal
    # Import the models module so every table registers on Base.metadata —
    # create_all() is a no-op against an empty metadata, which is exactly the
    # "no such table" failure this probe is designed to catch.
    from app.models import entities as _entities  # noqa: F401
    from app.models import fleet as _fleet  # noqa: F401

    async def write_probe():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as s:
            await s.execute(text(
                "INSERT INTO incidents (simulation_id, type, severity, status, "
                "detected_at, detected_tick, description, peak_temperature) VALUES "
                "(0, 'isolation_probe', 'LOW', 'DETECTED', datetime('now'), 0, 'probe', 0.0)"))
            await s.commit()
        async with SessionLocal() as s:
            n = (await s.execute(text("SELECT COUNT(*) FROM incidents"))).scalar()
        return n

    count = asyncio.run(write_probe())
    print(f"\nrows visible in TEMP db after probe write: {count}")
    assert count and count >= 1, "probe write did not land in the temp database"

    after = {p: digest(p) for p in LIVE_FILES}
    changed = [p for p in LIVE_FILES if before[p] != after[p]]
    print("\nlive DB digests after:")
    for p, d in after.items():
        print(f"  {d[:16] if d else '(absent)':18} {p}")
    assert not changed, f"LIVE DATABASE MODIFIED: {changed}"
    print("\nRESULT: ISOLATION VERIFIED — engine is on a temp DB, live files untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
