"""ColdChain Rescue — FastAPI entrypoint."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import CORS_ORIGINS
from .database.engine import Base, engine
from .models import entities  # noqa: F401  (ensures models registered on Base.metadata)
from .api.routes import auth, facilities, shipments, simulations, incidents, analytics, reports, demo, status, fleet, gemini, maintenance
from .websocket.handler import router as ws_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("coldchain")

app = FastAPI(title="ColdChain Rescue", description="AI cold-chain simulation & operation center",
              version="1.0.0-m1")

app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS or ["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight migration: create_all does not ALTER an existing table, so
        # a database created before the RBAC columns existed would raise
        # "no such column: users.role" on the first login. Both columns are
        # nullable/defaulted so adding them in place is safe and idempotent.
        try:
            from sqlalchemy import text as _sql
            cols = {row[1] for row in (await conn.execute(_sql("PRAGMA table_info(users)"))).fetchall()}
            if "role" not in cols:
                await conn.execute(_sql("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'operator'"))
            if "vehicle_id" not in cols:
                await conn.execute(_sql("ALTER TABLE users ADD COLUMN vehicle_id VARCHAR(40)"))
        except Exception as e:  # non-SQLite backends create columns via create_all
            log.debug("users migration skipped: %s", e)
    log.info("database ready (auto-created tables)")
    # fleet world (SIMULATION ONLY) — laptop demo, no hardware
    #
    # Default is a COLD world: nothing spawns and nothing runs until the
    # operator adds and starts trucks from the UI (the world loop starts
    # lazily with the first truck — see FleetOrchestrator.ensure_loop).
    # Set FLEET_AUTOSTART=1 explicitly to boot with the 12-truck round-robin
    # demo fleet already moving.
    import os, asyncio
    from .simulation.fleet_orchestrator import FLEET
    if os.getenv("FLEET_AUTOSTART", "0") == "1":
        asyncio.create_task(FLEET.start(12))
        log.info("fleet world started (12 vehicles)")
    else:
        log.info("cold world: no vehicles running — add and start trucks from the UI")


app.include_router(auth.router)
app.include_router(status.router)
app.include_router(demo.router)
app.include_router(facilities.router)
app.include_router(shipments.router)
app.include_router(simulations.router)
app.include_router(incidents.router)
app.include_router(analytics.router)
app.include_router(reports.router)
app.include_router(fleet.router)
app.include_router(maintenance.router)
app.include_router(gemini.router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"product": "ColdChain Rescue", "mode": "simulation", "docs": "/docs",
            "status": "/api/status", "demo_base": "POST /api/demo/base",
            "demo_launch": "POST /api/demo/launch"}
