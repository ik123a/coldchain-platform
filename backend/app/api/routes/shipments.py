"""Shipments CRUD + detail."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from ...database.engine import get_db
from ...core.authz import require_auth
from ...models.entities import Shipment
from ...schemas.dto import ShipmentIn, ShipmentOut

router = APIRouter(prefix="/api/shipments", tags=["shipments"])


@router.get("", response_model=list[ShipmentOut])
async def list_shipments(status: str | None = None, db=Depends(get_db)):
    q = select(Shipment)
    if status: q = q.where(Shipment.status == status)
    res = await db.execute(q)
    return res.scalars().all()


@router.post("", response_model=ShipmentOut, status_code=201)
async def create_shipment(body: ShipmentIn, _auth: dict = Depends(require_auth), db=Depends(get_db)):
    sh = Shipment(**body.model_dump())
    db.add(sh); await db.commit(); await db.refresh(sh)
    return sh


@router.get("/{sid}", response_model=ShipmentOut)
async def get_shipment(sid: int, db=Depends(get_db)):
    sh = await db.get(Shipment, sid)
    if not sh: raise HTTPException(404, "shipment not found")
    return sh
