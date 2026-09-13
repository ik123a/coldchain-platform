"""Auth: register / login / me. JWT bearer, pbkdf2 hashing."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Header
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
    u = User(name=body.name, email=body.email, password_hash=hash_password(body.password))
    db.add(u); await db.commit(); await db.refresh(u)
    return TokenOut(access_token=create_token(u.id, u.email),
                    user={"id": u.id, "name": u.name, "email": u.email})


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, db=Depends(get_db)):
    u = await db.scalar(select(User).where(User.email == body.email))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "invalid credentials")
    return TokenOut(access_token=create_token(u.id, u.email),
                    user={"id": u.id, "name": u.name, "email": u.email})


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
    return {"id": u.id, "name": u.name, "email": u.email, "created_at": u.created_at}
