"""WebSocket: frontend receives broadcast events from simulation runners."""
import asyncio, json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..simulation.runner import BROADCAST, RUNNERS

router = APIRouter()


@router.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    q = asyncio.Queue(maxsize=500)
    BROADCAST.add(q)
    try:
        # immediate hello + snapshot of running sims so a brand-new client has something to draw
        await websocket.send_text(json.dumps({"type": "hello", "sims": list(RUNNERS)}))
        while True:
            msg = await q.get()
            await websocket.send_text(msg)
    except WebSocketDisconnect:
        pass
    finally:
        BROADCAST.discard(q)
