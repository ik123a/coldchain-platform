"""Fleet relational models."""
from sqlalchemy import (Boolean, DateTime, Float, ForeignKey, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from .entities import Base


class Vehicle(Base):
    __tablename__ = "fleet_vehicles"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    kind: Mapped[str] = mapped_column(String(24), default="REFRIGERATED_TRUCK")
    energy_type: Mapped[str] = mapped_column(String(10), default="DIESEL")
    driver: Mapped[str] = mapped_column(String(40), default="")
    lat: Mapped[float] = mapped_column(Float, default=0.0)
    lng: Mapped[float] = mapped_column(Float, default=0.0)
    heading: Mapped[float] = mapped_column(Float, default=0.0)
    speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_pct: Mapped[float] = mapped_column(Float, default=80.0)
    battery_pct: Mapped[float] = mapped_column(Float, default=80.0)
    engine_on: Mapped[bool] = mapped_column(Boolean, default=True)
    vehicle_health: Mapped[float] = mapped_column(Float, default=95.0)
    capacity_units: Mapped[int] = mapped_column(Integer, default=1000)
    load_units: Mapped[int] = mapped_column(Integer, default=0)
    cargo_type: Mapped[str] = mapped_column(String(24), default="fresh_produce")
    shipment_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    destination_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="IN_TRANSIT")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FleetRoute(Base):
    __tablename__ = "fleet_routes"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(ForeignKey("fleet_vehicles.id"), index=True)
    origin_id: Mapped[str] = mapped_column(String(12))
    destination_id: Mapped[str] = mapped_column(String(12))
    route_type: Mapped[str] = mapped_column(String(16), default="BASE")
    geometry: Mapped[str] = mapped_column(Text, default="[]")
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    eta_min: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VehicleEvent(Base):
    __tablename__ = "fleet_vehicle_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(12), index=True)
    event_type: Mapped[str] = mapped_column(String(40))
    lat: Mapped[float] = mapped_column(Float, default=0.0)
    lng: Mapped[float] = mapped_column(Float, default=0.0)
    severity: Mapped[str] = mapped_column(String(10), default="info")
    description: Mapped[str] = mapped_column(Text, default="")
    sim_minute: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RouteDecision(Base):
    __tablename__ = "fleet_route_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(12), index=True)
    decision: Mapped[str] = mapped_column(String(16))
    recommended: Mapped[str] = mapped_column(Text, default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sim_minute: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CargoTransfer(Base):
    __tablename__ = "fleet_cargo_transfers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(12), index=True)
    facility_id: Mapped[str] = mapped_column(String(12))
    units: Mapped[int] = mapped_column(Integer, default=0)
    health_pct: Mapped[float] = mapped_column(Float, default=100.0)
    sim_minute: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
