"""Auth: register / login / me. JWT bearer, pbkdf2 hashing."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select
from ...database.engine import get_db
from ...core.security import hash_password, verify_password, create_token, decode_token
from ...models.entities import User
from ...schemas.dto import RegisterIn, LoginIn, TokenOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut)
async def register(body: RegisterIn, db=Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == body.email))
    if existing:
        raise HTTPException(409, "email already registered")
    role = body.role if body.role in ("driver", "operator") else "operator"
    # A driver without a truck is meaningless: bind them to one. No fleet is
    # available here (registration runs before any dispatch), so a driver
    # account starts unbound and picks up a truck via POST /api/auth/claim-truck.
    v = (body.vehicle_id or None) if role == "driver" else None
    u = User(name=body.name, email=body.email, password_hash=hash_password(body.password),
             role=role, vehicle_id=v)
    db.add(u); await db.commit(); await db.refresh(u)
    return TokenOut(access_token=create_token(u.id, u.email, u.role, u.vehicle_id),
                    user={"id": u.id, "name": u.name, "email": u.email,
                          "role": u.role, "vehicle_id": u.vehicle_id})


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db=Depends(get_db)):
    u = await db.scalar(select(User).where(User.email == body.email))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "invalid credentials")
    return TokenOut(access_token=create_token(u.id, u.email, u.role, u.vehicle_id),
                    user={"id": u.id, "name": u.name, "email": u.email,
                          "role": u.role, "vehicle_id": u.vehicle_id})


@router.get("/me")
async def me(authorization: str | None = Header(None), db=Depends(get_db)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing token")
    data = decode_token(authorization.split(None, 1)[1])
    if not data:
        raise HTTPException(401, "invalid token")
    u = await db.get(User, int(data["sub"]))
    if not u:
        raise HTTPException(401, "unknown user")
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role,
            "vehicle_id": u.vehicle_id, "created_at": u.created_at}


class ClaimTruckIn(BaseModel):
    vehicle_id: str = Field(min_length=3, max_length=40)


@router.get("/available-trucks")
async def available_trucks(authorization: str | None = Header(None), db=Depends(get_db)):
    """Cargo trucks a driver can be assigned to. Service trucks are excluded (no
    cargo bay, not a driver's vehicle) and trucks already held by another driver
    account come back with `taken: true` so the UI can disable them."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing token")
    if not decode_token(authorization.split(None, 1)[1]):
        raise HTTPException(401, "invalid token")
    from ...simulation.fleet_orchestrator import FLEET
    taken = {vid for (vid,) in (await db.execute(
        select(User.vehicle_id).where(User.vehicle_id.is_not(None)))).all()}
    out = []
    for vid, twin in getattr(FLEET, "vehicles", {}).items():
        # kind is "SERVICE_TRUCK" for service vehicles — substring, not equality,
        # or the service trucks leak into the picker.
        if "SERVICE" in str(getattr(twin, "kind", "")):
            continue
        out.append({"vehicle_id": vid,
                    "driver_name": getattr(twin, "driver", ""),
                    "cargo_type": getattr(twin, "cargo_type", ""),
                    "taken": vid in taken})
    out.sort(key=lambda r: (r["taken"], r["vehicle_id"]))
    return {"trucks": out}


@router.post("/claim-truck")
async def claim_truck(body: ClaimTruckIn, authorization: str | None = Header(None),
                      db=Depends(get_db)):
    """Bind the current driver account to a vehicle. The driver's name then
    becomes the truck's driver name, so the twin and the account agree."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing token")
    data = decode_token(authorization.split(None, 1)[1])
    if not data:
        raise HTTPException(401, "invalid token")
    u = await db.get(User, int(data["sub"]))
    if not u:
        raise HTTPException(401, "unknown user")
    if u.role != "driver":
        raise HTTPException(403, "only driver accounts claim trucks")
    from ...simulation.fleet_orchestrator import FLEET
    twin = getattr(FLEET, "vehicles", {}).get(body.vehicle_id)
    if twin is None:
        raise HTTPException(404, f"vehicle {body.vehicle_id} is not in the fleet")
    # One truck, one driver: refuse if another driver already holds it.
    other = await db.scalar(select(User).where(User.vehicle_id == body.vehicle_id,
                                               User.id != u.id))
    if other is not None:
        raise HTTPException(409, f"{body.vehicle_id} is already assigned to another driver")
    u.vehicle_id = body.vehicle_id
    await db.commit()
    try:
        twin.driver = u.name
    except Exception:
        pass
    return {"vehicle_id": u.vehicle_id, "driver_name": u.name}


@router.post("/unassign-truck")
async def unassign_truck(authorization: str | None = Header(None), db=Depends(get_db)):
    """Release the current driver's truck so they can pick another."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing token")
    data = decode_token(authorization.split(None, 1)[1])
    if not data:
        raise HTTPException(401, "invalid token")
    u = await db.get(User, int(data["sub"]))
    if not u:
        raise HTTPException(401, "unknown user")
    u.vehicle_id = None
    await db.commit()
    return {"vehicle_id": None}
