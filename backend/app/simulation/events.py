"""Typed event envelope for the fleet + facility world."""
from __future__ import annotations
import time, uuid


def make_event(etype: str, payload: dict, source: str = "fleet") -> dict:
    assert "." in etype, f"event type must be namespaced, got {etype!r}"
    return {
        "event_id": uuid.uuid4().hex[:12],
        "type": etype,
        "ts": time.time(),
        "source": source,
        "payload": payload,
    }


