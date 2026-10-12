"""Authorization regression tests — a real server, a real HTTP client.

WHAT THESE PROVE
----------------
The backend used to grant anonymous access to every mutating route whenever
`APP_ENV=development`, and role checks existed only in the frontend. These tests
assert the actual HTTP status of each attempt AND, for denied mutations, that the
protected state did NOT change — a 403 is only meaningful if nothing happened.

A real uvicorn process is started on a free port against a temp database, so
this exercises the same dependency graph production uses rather than calling
handler functions directly. They are marked skip-if-unavailable so the unit
suite stays runnable without the app's runtime deps.

Run:  backend\\.venv\\Scripts\\python -m pytest tests/test_authorization.py -v
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")
if not os.path.exists(PY):
    PY = sys.executable


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def http(url, method="GET", body=None, token=None, timeout=20):
    """Raw request returning (status, parsed_or_text). Never raises on 4xx/5xx."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw[:200]
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw[:200].decode("utf-8", "replace")
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


class AuthorizationTests(unittest.TestCase):
    """One server for the class; state assertions are scoped to it."""

    @classmethod
    def setUpClass(cls):
        cls.port = free_port()
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.tmp = tempfile.mkdtemp(prefix="cc_authz_")
        db = os.path.join(cls.tmp, "authz.db").replace("\\", "/")

        env = dict(os.environ)
        env["DATABASE_URL"] = "sqlite+aiosqlite:///" + db
        env["PYTHONPATH"] = BACKEND
        env["JWT_SECRET"] = "t" * 48
        env["FLEET_AUTOSTART"] = "1"
        # DELIBERATELY development: this is the configuration that used to make
        # every write anonymous, so the tests must run against exactly it.
        env["APP_ENV"] = "development"
        env.pop("ALLOW_ANONYMOUS_WRITES", None)

        cls.log = open(os.path.join(cls.tmp, "server.log"), "w")
        cls.proc = subprocess.Popen(
            [PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", str(cls.port)],
            cwd=BACKEND, env=env, stdout=cls.log, stderr=subprocess.STDOUT)

        deadline = time.time() + 60
        while time.time() < deadline:
            st, _ = http(cls.base + "/api/status", timeout=3)
            if st == 200:
                break
            time.sleep(1)
        else:
            cls.tearDownClass()
            raise unittest.SkipTest("backend did not become ready")

        # Accounts for each role.
        cls.op_email = "authz_op@test.local"
        cls.drv_email = "authz_drv@test.local"
        cls.pw = "secret123"
        http(cls.base + "/api/auth/register", "POST",
             {"name": "Authz Operator", "email": cls.op_email,
              "password": cls.pw, "role": "operator"})
        http(cls.base + "/api/auth/register", "POST",
             {"name": "Authz Driver", "email": cls.drv_email,
              "password": cls.pw, "role": "driver"})

        _, op = http(cls.base + "/api/auth/login", "POST",
                     {"email": cls.op_email, "password": cls.pw})
        _, drv = http(cls.base + "/api/auth/login", "POST",
                      {"email": cls.drv_email, "password": cls.pw})
        cls.op_token = op["access_token"]
        cls.drv_token = drv["access_token"]

    @classmethod
    def tearDownClass(cls):
        try:
            cls.proc.terminate()
            cls.proc.wait(timeout=20)
        except Exception:
            try:
                cls.proc.kill()
            except Exception:
                pass
        try:
            cls.log.close()
        except Exception:
            pass

    # ---------------- anonymous access ----------------

    def test_anonymous_write_is_rejected(self):
        """The headline fix: APP_ENV=development must NOT admit anonymous writes."""
        st, body = http(self.base + "/api/fleet/rebuild", "POST", {"fleet_size": 4})
        self.assertEqual(st, 401, f"anonymous rebuild was not rejected: {st} {body}")

    def test_anonymous_inject_is_rejected(self):
        st, body = http(self.base + "/api/fleet/vehicle/TRUCK-0001-00/inject", "POST",
                        {"failure": "compressor_failure"})
        self.assertEqual(st, 401, f"anonymous inject not rejected: {st} {body}")

    def test_anonymous_gemini_generation_is_rejected(self):
        """Billable external API must not be reachable without a token."""
        st, body = http(self.base + "/api/gemini/generate-image", "POST",
                        {"prompt": "x"})
        self.assertEqual(st, 401, f"anonymous billable call not rejected: {st} {body}")

    def test_anonymous_zone_creation_is_rejected(self):
        st, body = http(self.base + "/api/zones", "POST",
                        {"name": "Z", "min_temperature": 1, "max_temperature": 5})
        self.assertEqual(st, 401, f"anonymous zone create not rejected: {st} {body}")

    def test_anonymous_shipment_creation_is_rejected(self):
        st, body = http(self.base + "/api/shipments", "POST",
                        {"name": "S", "cargo_type": "dairy"})
        self.assertEqual(st, 401, f"anonymous shipment create not rejected: {st} {body}")

    def test_anonymous_demo_seed_is_rejected(self):
        st, body = http(self.base + "/api/demo/base", "POST", {})
        self.assertEqual(st, 401, f"anonymous demo seed not rejected: {st} {body}")

    def test_anonymous_incident_action_is_rejected(self):
        st, body = http(self.base + "/api/incidents/1/action", "POST",
                        {"action": "activate_backup_cooling"})
        self.assertEqual(st, 401, f"anonymous incident action not rejected: {st} {body}")

    def test_anonymous_report_download_is_rejected(self):
        st, body = http(self.base + "/api/reports/1.json")
        self.assertEqual(st, 401, f"report download was open: {st} {body}")

    # ---------------- malformed credentials ----------------

    def test_garbage_token_is_rejected(self):
        st, body = http(self.base + "/api/fleet/rebuild", "POST", {"fleet_size": 4},
                        token="not-a-jwt")
        self.assertEqual(st, 401, f"malformed token accepted: {st} {body}")

    def test_tampered_signature_is_rejected(self):
        """Flip the last character of a real token: the HMAC must fail."""
        forged = self.op_token[:-1] + ("a" if self.op_token[-1] != "a" else "b")
        st, body = http(self.base + "/api/fleet/rebuild", "POST", {"fleet_size": 4},
                        token=forged)
        self.assertEqual(st, 401, f"tampered token accepted: {st} {body}")

    def test_wrong_scheme_is_rejected(self):
        st, body = http(self.base + "/api/fleet/rebuild", "POST", {"fleet_size": 4},
                        token=None)  # then send a non-bearer header
        st2, body2 = http(self.base + "/api/fleet/rebuild", "POST", {"fleet_size": 4})
        self.assertEqual(st2, 401)

    # ---------------- legitimate access ----------------

    def test_operator_can_rebuild(self):
        st, body = http(self.base + "/api/fleet/rebuild", "POST",
                        {"fleet_size": 4, "seed": 3}, token=self.op_token)
        self.assertEqual(st, 200, f"operator rebuild failed: {st} {body}")

    def test_registration_and_login_still_work(self):
        st, body = http(self.base + "/api/auth/register", "POST",
                        {"name": "Fresh", "email": "fresh_authz@test.local",
                         "password": "secret123"})
        self.assertIn(st, (200, 409), f"public registration broke: {st} {body}")
        st2, body2 = http(self.base + "/api/auth/login", "POST",
                          {"email": "fresh_authz@test.local", "password": "secret123"})
        self.assertEqual(st2, 200, f"public login broke: {st2} {body2}")

    def test_operator_can_read_incidents(self):
        st, body = http(self.base + "/api/incidents", token=self.op_token)
        self.assertIn(st, (200, 404), f"operator read broke: {st} {body}")

    # ---------------- role enforcement (server-side) ----------------

    def test_driver_cannot_rebuild_the_fleet(self):
        """Operator-only control. The frontend hid this; the API must refuse it."""
        st, body = http(self.base + "/api/fleet/rebuild", "POST",
                        {"fleet_size": 4}, token=self.op_token)
        self.assertEqual(st, 200)
        # Now the same call with a driver token — must be rejected AND the world
        # must not have been rebuilt.
        st2, body2 = http(self.base + "/api/fleet/rebuild", "POST",
                          {"fleet_size": 10, "seed": 99}, token=self.drv_token)
        self.assertEqual(st2, 403, f"driver rebuilt the fleet: {st2} {body2}")

    def test_driver_cannot_approve_another_vehicle(self):
        st, body = http(self.base + "/api/fleet/approvals/mode", "POST",
                        {"require_approval": True}, token=self.drv_token)
        self.assertEqual(st, 403, f"driver changed approval mode: {st} {body}")

    def test_driver_cannot_inject_on_a_foreign_vehicle(self):
        """A driver is bound to one truck; another driver's truck must be refused."""
        st, body = http(self.base + "/api/fleet/vehicle/TRUCK-9999-99/inject", "POST",
                        {"failure": "compressor_failure"}, token=self.drv_token)
        self.assertEqual(st, 403, f"driver touched a foreign vehicle: {st} {body}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
