"""Global status endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from ...database.engine import get_db, engine as db_engine
from ...models.entities import Incident, Simulation
from ...core.config import AI_MODE
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
    open_inc = (await db.execute(select(Incident).where(Incident.status != "RESOLVED"))).scalars().all()
    return StatusOut(system=("OPERATIONAL" if db_ok == "CONNECTED" else "DEGRADED"),
                     api="ONLINE", database=db_ok, websocket="CONNECTED", ai_mode=AI_MODE,
                     simulations_running=len(running), incidents_open=len(open_inc),
                     timestamp=datetime.utcnow())
