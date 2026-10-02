"""Facilities + zones CRUD."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from ...database.engine import get_db
from ...core.authz import require_auth
from ...models.entities import StorageFacility, StorageZone
from ...schemas.dto import FacilityOut, ZoneIn, ZoneOut

router = APIRouter(prefix="/api", tags=["facilities"])


@router.get("/facilities", response_model=list[FacilityOut])
async def list_facilities(db=Depends(get_db)):
    res = await db.execute(select(StorageFacility))
    return res.scalars().all()


@router.get("/facilities/{fid}", response_model=FacilityOut)
async def get_facility(fid: int, db=Depends(get_db)):
    f = await db.get(StorageFacility, fid)
    if not f: raise HTTPException(404, "facility not found")
    return f


@router.get("/zones", response_model=list[ZoneOut])
async def list_zones(facility_id: int | None = None, db=Depends(get_db)):
    q = select(StorageZone)
    if facility_id: q = q.where(StorageZone.facility_id == facility_id)
    res = await db.execute(q)
    return res.scalars().all()


@router.post("/zones", response_model=ZoneOut, status_code=201)
async def create_zone(body: ZoneIn, db=Depends(get_db)):
    z = StorageZone(**body.model_dump())
    db.add(z); await db.commit(); await db.refresh(z)
    return z
