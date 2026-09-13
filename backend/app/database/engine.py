"""ColdChain Rescue — DB engine (SQLite default, postgres-compatible URL)."""
from __future__ import annotations
import os
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker, create_async_engine)
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./coldchain.db")

engine = create_async_engine(DATABASE_URL, echo=bool(os.getenv("DB_ECHO")), pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        yield session
