"""ColdChain Rescue — FastAPI entrypoint."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import CORS_ORIGINS
from .database.engine import Base, engine
from .models import entities  # noqa: F401  (ensures models registered on Base.metadata)
from .api.routes import auth, facilities, shipments, simulations, incidents, analytics, reports, demo, status, fleet, gemini
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
    log.info("database ready (auto-created tables)")
    # fleet world (SIMULATION ONLY) — laptop demo, no hardware
    import os, asyncio
    from .simulation.fleet_orchestrator import FLEET
    if os.getenv("FLEET_AUTOSTART", "1") == "1":
        asyncio.create_task(FLEET.start(12))
        log.info("fleet world started (12 vehicles)")


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
app.include_router(gemini.router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"product": "ColdChain Rescue", "mode": "simulation", "docs": "/docs",
            "status": "/api/status", "demo_base": "POST /api/demo/base",
            "demo_launch": "POST /api/demo/launch"}
