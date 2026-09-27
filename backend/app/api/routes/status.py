"""Global status endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from ...database.engine import get_db, engine as db_engine
from ...models.entities import Incident, Simulation
from ...core.config import AI_MODE
from ...simulation.runner import RUNNERS
from ...schemas.dto import StatusOut
from datetime import datetime

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status", response_model=StatusOut)
async def status(db=Depends(get_db)):
    try:
        async with db_engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = "CONNECTED"
    except Exception:
        db_ok = "UNAVAILABLE"
    running = (await db.execute(select(Simulation).where(Simulation.status == "RUNNING"))).scalars().all()
    # A Simulation row is only genuinely running if a live runner backs it.
    # Rows left RUNNING with no runner are orphans from a previous process and
    # would otherwise inflate this count forever (nothing ever wrote COMPLETED
    # back on natural termination). Reconcile them to ORPHANED, then count only
    # ids that actually have a runner in this process.
    live_ids = {sid for sid, r in RUNNERS.items() if r.status == "RUNNING"}
    orphan_ids = [s.id for s in running if s.id not in live_ids]
    if orphan_ids:
        await db.execute(update(Simulation).where(Simulation.id.in_(orphan_ids))
                         .values(status="ORPHANED", end_time=datetime.utcnow()))
        await db.commit()
    open_inc = (await db.execute(select(Incident).where(Incident.status != "RESOLVED"))).scalars().all()
    return StatusOut(system=("OPERATIONAL" if db_ok == "CONNECTED" else "DEGRADED"),
                     api="ONLINE", database=db_ok, websocket="CONNECTED", ai_mode=AI_MODE,
                     simulations_running=len(live_ids), simulations_orphaned=len(orphan_ids),
                     incidents_open=len(open_inc),
                     timestamp=datetime.utcnow())
