"""ColdChain Rescue — relational models."""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column
from ..database.engine import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), default="")
    # RBAC. "operator" sees the whole fleet; "driver" is bound to one vehicle
    # (vehicle_id) and only sees their own truck. Default operator so accounts
    # created before this column existed keep full access.
    role: Mapped[str] = mapped_column(String(20), default="operator")
    vehicle_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StorageFacility(Base):
    __tablename__ = "facilities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer, default=1000)
    status: Mapped[str] = mapped_column(String(20), default="OPERATIONAL")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StorageZone(Base):
    __tablename__ = "zones"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"))
    name: Mapped[str] = mapped_column(String(40))
    min_temperature: Mapped[float] = mapped_column(Float, default=2.0)
    max_temperature: Mapped[float] = mapped_column(Float, default=8.0)
    target_temperature: Mapped[float] = mapped_column(Float, default=4.0)
    humidity_min: Mapped[float] = mapped_column(Float, default=60.0)
    humidity_max: Mapped[float] = mapped_column(Float, default=85.0)


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    cargo_type: Mapped[str] = mapped_column(String(60))
    quantity: Mapped[int] = mapped_column(Integer, default=100)
    origin: Mapped[str] = mapped_column(String(80))
    destination: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(24), default="PREPARING")
    cargo_value: Mapped[float] = mapped_column(Float, default=0.0)  # INR
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Simulation(Base):
    __tablename__ = "simulations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[int | None] = mapped_column(ForeignKey("shipments.id"), nullable=True)
    storage_zone_id: Mapped[int | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="CREATED")  # CREATED / RUNNING / PAUSED / COMPLETED
    scenario: Mapped[str] = mapped_column(String(30), default="normal")
    simulation_speed: Mapped[int] = mapped_column(Integer, default=10)
    tick_seconds: Mapped[int] = mapped_column(Integer, default=1)  # wall-seconds per tick
    current_tick: Mapped[int] = mapped_column(Integer, default=0)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id"), index=True)
    tick: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    ambient_temperature: Mapped[float] = mapped_column(Float)
    door_open: Mapped[bool] = mapped_column(Boolean, default=False)
    compressor_on: Mapped[bool] = mapped_column(Boolean, default=True)
    backup_cooling: Mapped[bool] = mapped_column(Boolean, default=False)
    power_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    battery_level: Mapped[float] = mapped_column(Float, default=100.0)
    cargo_health: Mapped[float] = mapped_column(Float, default=100.0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id"), index=True)
    type: Mapped[str] = mapped_column(String(40), default="temperature_excursion")
    severity: Mapped[str] = mapped_column(String(12), default="HIGH")  # MEDIUM/HIGH/CRITICAL
    status: Mapped[str] = mapped_column(String(24), default="DETECTED")  # DETECTED/DIAGNOSED/PLANNED/RECOVERING/RESOLVED
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    detected_tick: Mapped[int] = mapped_column(Integer, default=0)
    resolved_tick: Mapped[int | None] = mapped_column(Integer, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(60), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    peak_temperature: Mapped[float] = mapped_column(Float, default=0.0)
    root_cause_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(40))  # monitoring/diagnosis/risk/planner/verifier/reporter
    analysis: Mapped[str] = mapped_column(Text)  # JSON string
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RecommendedAction(Base):
    __tablename__ = "recommended_actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), index=True)
    action: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(160), default="")
    priority: Mapped[str] = mapped_column(String(12), default="HIGH")  # CRITICAL/HIGH/MEDIUM
    reason: Mapped[str] = mapped_column(Text, default="")
    expected_effect: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(16), default="PENDING")  # PENDING/EXECUTED/SKIPPED
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[int] = mapped_column(ForeignKey("simulations.id"), index=True)
    type: Mapped[str] = mapped_column(String(30), default="threshold")
    severity: Mapped[str] = mapped_column(String(12), default="COPY")  # INFO/WARNING/CRITICAL
    message: Mapped[str] = mapped_column(Text)
    tick: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
