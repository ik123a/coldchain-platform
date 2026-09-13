"""Pydantic schemas (API contracts)."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=160)
    password: str = Field(min_length=6, max_length=72)


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class FacilityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; location: str; capacity: int; status: str


class ZoneIn(BaseModel):
    facility_id: int
    name: str
    min_temperature: float = 2.0
    max_temperature: float = 8.0
    target_temperature: float = 4.0
    humidity_min: float = 60.0
    humidity_max: float = 85.0


class ZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; facility_id: int; name: str
    min_temperature: float; max_temperature: float; target_temperature: float
    humidity_min: float; humidity_max: float


class ShipmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    cargo_type: str = "fresh_produce"
    quantity: int = 100
    origin: str = "Delhi"
    destination: str = "Jaipur"
    cargo_value: float = 0.0


class ShipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; cargo_type: str; quantity: int
    origin: str; destination: str; status: str; cargo_value: float


class SimulationCreateIn(BaseModel):
    shipment_id: int | None = None
    storage_zone_id: int | None = None
    scenario: str = "normal"
    simulation_speed: int = Field(default=10, ge=1, le=100)


class SimulationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; shipment_id: int | None; storage_zone_id: int | None
    status: str; scenario: str; simulation_speed: int
    current_tick: int


class SpeedIn(BaseModel):
    speed: int = Field(ge=1, le=100)


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; simulation_id: int; type: str; severity: str; status: str
    detected_at: datetime; resolved_at: datetime | None
    detected_tick: int; resolved_tick: int | None
    root_cause: str | None; description: str; peak_temperature: float
    root_cause_confidence: float | None
    actions: list[dict] = []; analyses: list[dict] = []


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=600)


class ExecuteActionIn(BaseModel):
    action: str = Field(min_length=3, max_length=60)


class StatusOut(BaseModel):
    system: str = "OPERATIONAL"
    api: str = "ONLINE"
    database: str = "CONNECTED"
    websocket: str = "CONNECTED"
    ai_mode: str = "DETERMINISTIC"
    simulations_running: int = 0
    incidents_open: int = 0
    timestamp: datetime
