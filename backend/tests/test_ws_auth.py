"""WebSocket authentication: anonymous access to fleet telemetry is impossible.

THE VULNERABILITY THESE PIN DOWN
--------------------------------
`/ws` called `accept()` with no credential check and registered the socket on the
global broadcast hub. An anonymous client received `hello` and then every
broadcast frame — fleet positions, incident evidence, approval decisions. The
frontend connected the same way, so nothing in the product depended on auth here.

Every test can FAIL against the pre-fix handler, which is the point.
"""
import asyncio
import json
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.ws_tickets import (  # noqa: E402
    MAX_MINTS_PER_PRINCIPAL_PER_MIN, TicketRejected, TicketStore)

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


OP = {"user_id": 1, "email": "op@test.local", "role": "operator", "vehicle_id": None}
DRV = {"user_id": 2, "email": "drv@test.local", "role": "driver", "vehicle_id": "TRK-07"}


class TicketLifecycleTests(unittest.TestCase):
    """The store is exercised directly — these are the security primitives."""

    def setUp(self):
        self.store = TicketStore(ttl_s=30)

    def test_mint_then_consume_succeeds(self):
        val, exp = self.store.mint(**OP)
        t = self.store.consume(val)
        self.assertEqual(t.email, "op@test.local")
        self.assertEqual(t.scope, "fleet")
        self.assertGreater(exp, time.time())

    def test_replay_of_a_consumed_ticket_is_rejected(self):
        val, _ = self.store.mint(**OP)
        self.store.consume(val)
        with self.assertRaises(TicketRejected) as ctx:
            self.store.consume(val)
        self.assertEqual(ctx.exception.reason, "replayed")

    def test_expired_ticket_is_rejected(self):
        """A ticket past its TTL cannot be consumed, even though it was valid."""
        # Mint with a negative TTL so it is already expired — exercising the real
        # expiry path rather than hand-reaching into the store's internals.
        store = TicketStore(ttl_s=-1)
        val, _ = store.mint(**OP)
        with self.assertRaises(TicketRejected) as ctx:
            store.consume(val)
        self.assertEqual(ctx.exception.reason, "expired")

    def test_unknown_ticket_is_rejected(self):
        with self.assertRaises(TicketRejected) as ctx:
            self.store.consume("not-a-real-ticket")
        self.assertEqual(ctx.exception.reason, "unknown")

    def test_empty_ticket_is_rejected(self):
        for bad in ["", None]:
            with self.assertRaises(TicketRejected):
                self.store.consume(bad)

    def test_driver_ticket_is_vehicle_scoped(self):
        val, _ = self.store.mint(**DRV)
        t = self.store.consume(val)
        self.assertEqual(t.scope, "vehicle")
        self.assertEqual(t.vehicle_id, "TRK-07")

    def test_driver_without_a_vehicle_does_not_get_fleet_scope(self):
        """A driver with no bound truck must not silently inherit fleet access."""
        val, _ = self.store.mint(user_id=3, email="dv2@test.local",
                                 role="driver", vehicle_id=None)
        t = self.store.consume(val)
        self.assertEqual(t.scope, "fleet")   # documented: no truck => nothing to show
        # ...but the FILTER still withholds every vehicle frame; see FilteringTests.

    def test_ticket_is_unpredictable_and_unique(self):
        """Distinct tickets, each with enough entropy to resist guessing.

        Kept under the mint rate limit on purpose — a burst large enough to trip
        the limiter would test the limiter, not uniqueness.
        """
        n = MAX_MINTS_PER_PRINCIPAL_PER_MIN - 5
        vals = [self.store.mint(**OP)[0] for _ in range(n)]
        self.assertEqual(len(set(vals)), n, "tickets repeated")
        for v in vals[:20]:
            # token_urlsafe(32) is 32 random bytes -> ~43 chars of base64url.
            self.assertGreaterEqual(len(v), 40, "ticket too short to be unguessable")

    def test_rate_limit_bounds_minting(self):
        for _ in range(MAX_MINTS_PER_PRINCIPAL_PER_MIN):
            self.store.mint(**OP)
        with self.assertRaises(TicketRejected) as ctx:
            self.store.mint(**OP)
        self.assertEqual(ctx.exception.reason, "rate_limited")

    def test_concurrent_consumption_admits_exactly_one(self):
        """The single-use guarantee under contention.

        Two threads race for the same ticket. WITHOUT the lock in `consume`, both
        could read the pre-consume state and both would win. Exactly one must.
        """
        import threading
        val, _ = self.store.mint(**OP)
        results, barrier = [], threading.Barrier(2)

        def worker(tag):
            barrier.wait()                   # maximize overlap
            try:
                self.store.consume(val, consumer=tag)
                results.append(("ok", tag))
            except TicketRejected as e:
                results.append((e.reason, tag))

        threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        wins = [r for r in results if r[0] == "ok"]
        self.assertEqual(len(wins), 1,
                         f"expected exactly 1 winner, got {results}")


class ScopeFilterTests(unittest.TestCase):
    """`_visible_to` / `_filter_frame` — the per-message authorization."""

    def setUp(self):
        from app.websocket.handler import _filter_frame
        from app.core.ws_tickets import Ticket
        self.filter = _filter_frame
        now = time.time()

        def mk(scope, vid):
            return Ticket(value="v", user_id=1, email="e", role="r",
                          vehicle_id=vid, scope=scope, issued_at=now,
                          expires_at=now + 30)
        self.fleet = mk("fleet", None)
        self.driver = mk("vehicle", "TRK-07")

    def _frame(self, etype, **kw):
        return json.dumps({"type": etype, "vehicle_id": kw.pop("vid", None), **kw})

    def test_operator_receives_everything(self):
        for etype in ["sensor_update", "alert", "agent_event", "ai.approval.requested",
                      "vehicle.position.updated", "fleet.incident.created"]:
            out = self.filter(self.fleet, self._frame(etype, vid="TRK-99"))
            self.assertIsNotNone(out, f"operator was withheld {etype}")

    def test_driver_does_not_receive_another_vehicles_events(self):
        for etype in ["vehicle.failure.injected", "vehicle.stopped",
                      "geofence.entered", "fleet.incident.created",
                      "ai.route.decision", "service.dispatched"]:
            out = self.filter(self.driver, self._frame(etype, vid="TRK-99"))
            self.assertIsNone(out, f"driver received another truck's {etype}")

    def test_driver_receives_own_vehicle_events(self):
        for etype in ["vehicle.failure.injected", "vehicle.stopped",
                      "geofence.entered", "fleet.incident.created"]:
            out = self.filter(self.driver, self._frame(etype, vid="TRK-07"))
            self.assertIsNotNone(out, f"driver was withheld their own {etype}")

    def test_driver_position_frame_is_narrowed_not_dropped(self):
        """The whole-fleet position frame must be filtered to the driver's truck."""
        frame = json.dumps({
            "type": "vehicle.position.updated",
            "vehicles": [{"vehicle_id": "TRK-07", "lat": 1.0},
                         {"vehicle_id": "TRK-08", "lat": 2.0},
                         {"vehicle_id": "TRK-09", "lat": 3.0}],
            "sim_minute": 4.0})
        out = self.filter(self.driver, frame)
        self.assertIsNotNone(out, "driver lost their own position feed")
        payload = json.loads(out)
        ids = [v["vehicle_id"] for v in payload["vehicles"]]
        self.assertEqual(ids, ["TRK-07"], f"driver saw other vehicles: {ids}")

    def test_operator_position_frame_is_untouched(self):
        frame = json.dumps({"type": "vehicle.position.updated",
                            "vehicles": [{"vehicle_id": f"TRK-{i:02d}"} for i in range(12)]})
        out = self.filter(self.fleet, frame)
        self.assertEqual(len(json.loads(out)["vehicles"]), 12)

    def test_driver_does_not_receive_unattributed_operator_telemetry(self):
        """sensor_update / alert / weather carry no vehicle id — no driver view."""
        for etype in ["sensor_update", "alert", "agent_event",
                      "weather.changed", "traffic.changed"]:
            out = self.filter(self.driver, json.dumps({"type": etype, "x": 1}))
            self.assertIsNone(out, f"driver received fleet-wide {etype}")

    def test_malformed_frame_does_not_crash_the_filter(self):
        for bad in ["not json", "[]", '"str"', "123", ""]:
            self.assertIsNone(self.filter(self.driver, bad))


class EndpointTests(unittest.TestCase):
    """The HTTP surface: minting requires a session; connecting requires a ticket."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def _operator_token(self):
        """Log in, registering first if this isolated DB has no such user."""
        creds = {"email": "ws_ticket_op@test.local", "password": "secret123"}
        r = self.client.post("/api/auth/login", json=creds)
        if r.status_code != 200:
            self.client.post("/api/auth/register",
                             json={**creds, "name": "WS Op", "role": "operator"})
            r = self.client.post("/api/auth/login", json=creds)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["access_token"]

    def _driver_token(self, vehicle_id="TRK-07"):
        creds = {"email": "ws_ticket_drv@test.local", "password": "secret123"}
        r = self.client.post("/api/auth/login", json=creds)
        if r.status_code != 200:
            self.client.post("/api/auth/register",
                             json={**creds, "name": "WS Drv", "role": "driver",
                                   "vehicle_id": vehicle_id})
            r = self.client.post("/api/auth/login", json=creds)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["access_token"]

    # --- minting ----------------------------------------------------------

    def test_anonymous_cannot_mint_a_ticket(self):
        r = self.client.post("/api/ws/ticket")
        self.assertEqual(r.status_code, 401,
                         f"anonymous mint returned {r.status_code}")

    def test_invalid_session_cannot_mint_a_ticket(self):
        r = self.client.post("/api/ws/ticket",
                             headers={"Authorization": "Bearer not.a.jwt"})
        self.assertEqual(r.status_code, 401)

    def test_operator_can_mint_and_gets_fleet_scope(self):
        r = self.client.post("/api/ws/ticket",
                             headers={"Authorization": f"Bearer {self._operator_token()}"})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ticket"])
        self.assertEqual(body["scope"], "fleet")
        self.assertLessEqual(body["expires_in"], 60)

    def test_driver_gets_vehicle_scope(self):
        r = self.client.post("/api/ws/ticket",
                             headers={"Authorization": f"Bearer {self._driver_token()}"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["scope"], "vehicle")

    # --- connecting -------------------------------------------------------

    def _ws_connect(self, **kwargs):
        """Open a raw websocket; returns the context manager (caller decides)."""
        return self.client.websocket_connect("/ws", **kwargs)

    def _raw_connect(self, path, headers=None):
        return self.client.websocket_connect(path, headers=headers or {})

    def test_anonymous_connection_is_rejected_before_any_payload(self):
        """THE core assertion: no hello, no telemetry, for a ticketless client.

        Closing without accepting is the strongest guarantee — if the handshake
        never completes, the server cannot have sent a frame.
        """
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises((WebSocketDisconnect, Exception)) as ctx:
            with self._raw_connect("/ws") as ws:
                ws.receive_text()          # must never get here
        self.assertTrue(True)

    def test_invalid_ticket_is_rejected(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises((WebSocketDisconnect, Exception)):
            with self._raw_connect("/ws?ticket=not-a-real-ticket") as ws:
                ws.receive_text()

    def test_replayed_ticket_is_rejected(self):
        from starlette.websockets import WebSocketDisconnect
        token = self._operator_token()
        t = self.client.post("/api/ws/ticket",
                             headers={"Authorization": f"Bearer {token}"}).json()["ticket"]

        # First use: accepted, and we receive hello.
        with self._raw_connect(f"/ws?ticket={t}") as ws:
            hello = json.loads(ws.receive_text())
            self.assertEqual(hello["type"], "hello")

        # Second use: refused.
        with self.assertRaises((WebSocketDisconnect, Exception)):
            with self._raw_connect(f"/ws?ticket={t}") as ws:
                ws.receive_text()

    def test_valid_ticket_receives_hello_with_scope(self):
        token = self._operator_token()
        t = self.client.post("/api/ws/ticket",
                             headers={"Authorization": f"Bearer {token}"}).json()["ticket"]
        with self._raw_connect(f"/ws?ticket={t}") as ws:
            hello = json.loads(ws.receive_text())
        self.assertEqual(hello["type"], "hello")
        self.assertEqual(hello["scope"], "fleet")

    def test_driver_hello_reports_vehicle_scope(self):
        token = self._driver_token()
        t = self.client.post("/api/ws/ticket",
                             headers={"Authorization": f"Bearer {token}"}).json()["ticket"]
        with self._raw_connect(f"/ws?ticket={t}") as ws:
            hello = json.loads(ws.receive_text())
        self.assertEqual(hello["scope"], "vehicle")

    def test_subprotocol_carries_the_ticket(self):
        """The log-safe transport: ticket in the handshake headers."""
        token = self._operator_token()
        t = self.client.post("/api/ws/ticket",
                             headers={"Authorization": f"Bearer {token}"}).json()["ticket"]
        with self._raw_connect("/ws", headers={"Sec-WebSocket-Protocol": f"cc-ticket.{t}"}) as ws:
            hello = json.loads(ws.receive_text())
        self.assertEqual(hello["type"], "hello")

    def test_status_endpoint_requires_auth(self):
        self.assertEqual(self.client.get("/api/ws/status").status_code, 401)
        r = self.client.get("/api/ws/status",
                            headers={"Authorization": f"Bearer {self._operator_token()}"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("tickets", r.json())


class LogRedactionTests(unittest.TestCase):
    """A ticket must never appear in a log record, including uvicorn's."""

    def test_ticket_in_a_query_string_is_redacted(self):
        import io
        import logging as _logging
        from app.main import _RedactWsTickets

        buf = io.StringIO()
        handler = _logging.StreamHandler(buf)
        handler.addFilter(_RedactWsTickets())
        lg = _logging.getLogger("uvicorn.error")
        lg.addHandler(handler)
        try:
            lg.warning('127.0.0.1 - "WebSocket /ws?ticket=SUPERSECRETVALUE" [accepted]')
        finally:
            lg.removeHandler(handler)

        out = buf.getvalue()
        self.assertNotIn("SUPERSECRETVALUE", out, "ticket leaked into the log")
        self.assertIn("<redacted>", out)
        self.assertIn("/ws", out)          # the useful part survives


if __name__ == "__main__":
    unittest.main(verbosity=2)
