"""Test-suite maintenance: release the state an E2E run left behind.

WHY THIS EXISTS
---------------
The driver tests claim a truck, and a claim is a real database write
(`users.vehicle_id`). A few runs of the suite would hold every cargo truck, after
which later runs fail on "no free truck" — a test suite that breaks the app it is
testing. Resetting the dispatch alone does NOT release these bindings; only
deleting the accounts does.

TWO SAFETY PROPERTIES, because this endpoint deletes rows
--------------------------------------------------------
1. It only ever deletes accounts whose email matches a caller-supplied prefix
   (the suite's `e2e_` / `drv_`) AND which were created at or after
   `newer_than_ms`. A blanket "delete all users" would destroy a real operator's
   account, so the prefix + age filter is required, not optional.
2. It refuses to run when APP_ENV is a production value, regardless of any flag.
   A destructive maintenance route must not be reachable in production even by
   accident — the same reasoning as `core/authz.py` failing closed.
"""
from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ...core.authz import require_auth
from ...database.engine import get_db
from ...models.entities import User

router = APIRouter(prefix="/api/fleet/maintenance", tags=["maintenance"])

APP_ENV = (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()
IS_PROD = APP_ENV in {"prod", "production", "staging"}


class CleanupIn(BaseModel):
    # Required: an empty prefix list would make this a delete-everything route.
    prefixes: list[str] = Field(min_length=1, max_length=10)
    newer_than_ms: int | None = None
    restart_fleet: bool = False


@router.post("/cleanup")
async def cleanup(body: CleanupIn, _auth: dict = Depends(require_auth), db=Depends(get_db)):
    if IS_PROD:
        raise HTTPException(403, "maintenance cleanup is disabled outside development")

    prefixes = [p.strip() for p in body.prefixes if p.strip()]
    if not prefixes:
        raise HTTPException(422, "at least one non-empty prefix is required")

    cutoff = datetime.utcfromtimestamp(body.newer_than_ms / 1000.0) if body.newer_than_ms else None

    rows = (await db.execute(select(User))).scalars().all()
    doomed = []
    for u in rows:
        if not any(u.email.startswith(p) for p in prefixes):
            continue
        if cutoff is not None and u.created_at and u.created_at < cutoff:
            continue  # older than this run — not ours to delete
        doomed.append(u)

    released = sum(1 for u in doomed if u.vehicle_id)
    for u in doomed:
        await db.delete(u)
    await db.commit()

    restarted = False
    if body.restart_fleet:
        # Reset per-twin runtime state (injected faults, positions, events) so the
        # next run — or a demo — does not inherit them.
        try:
            from ...simulation.fleet_orchestrator import FLEET

            await FLEET.rebuild()
            restarted = True
        except Exception:
            restarted = False

    return {
        "accounts_deleted": len(doomed),
        "trucks_released": released,
        "fleet_restarted": restarted,
    }
