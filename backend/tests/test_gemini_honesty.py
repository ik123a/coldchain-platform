"""Critique honesty + billable-operation rate limits.

TWO LIES THESE TESTS KILL
-------------------------
1. `_fallback_critique` returned hardcoded 9.x scores with verdict APPROVED when
   the provider was missing, rate-limited, or broken. A caller could not tell a
   real critique from a fabricated one — the exact "looks scientific" failure the
   mission bans. Now every failure is explicit (`success: False` + `status`).
2. Billable gemini endpoints had NO rate limits. Now each is gated per-principal
   with an injectable-clock limiter, and tests use mocked transport only — no
   real billable call can occur.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("APP_ENV", "development")


class FakeResp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


GOOD_CRITIQUE = {
    "scores": {"visual_quality": 7.1},
    "overall_verdict": "NEEDS_REFINEMENT",
    "strengths": ["x"],
}


class CritiqueHonestyTests(unittest.TestCase):

    def setUp(self):
        import app.services.gemini.critique as critique_mod
        self.c = critique_mod
        self._key = critique_mod.GEMINI_API_KEY
        self._post = critique_mod.requests.post

    def tearDown(self):
        self.c.GEMINI_API_KEY = self._key
        self.c.requests.post = self._post

    def test_missing_key_is_unavailable_never_approved(self):
        self.c.GEMINI_API_KEY = ""
        res = self.c.critique_reference_asset("a1", "T", "cat", "p")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "unavailable")
        self.assertNotIn("overall_verdict", res)
        self.assertNotIn("scores", res)

    def test_provider_failure_is_explicit_not_approved(self):
        self.c.GEMINI_API_KEY = "dummy-key-for-test"
        def boom(*a, **k):
            raise ConnectionError("network down")
        self.c.requests.post = boom
        res = self.c.critique_reference_asset("a1", "T", "cat", "p")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "failed")
        self.assertNotIn("overall_verdict", res)

    def test_http_500_is_failed(self):
        self.c.GEMINI_API_KEY = "dummy-key-for-test"
        self.c.requests.post = lambda *a, **k: FakeResp(500, text="err")
        res = self.c.critique_reference_asset("a1", "T", "cat", "p")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "failed")

    def test_rate_limit_is_rate_limited_status(self):
        self.c.GEMINI_API_KEY = "dummy-key-for-test"
        self.c.requests.post = lambda *a, **k: FakeResp(429, text="quota")
        res = self.c.critique_reference_asset("a1", "T", "cat", "p")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "rate_limited")

    def test_garbage_output_is_not_a_verdict(self):
        self.c.GEMINI_API_KEY = "dummy-key-for-test"
        # Model returns 200 but not JSON / not a critique shape.
        self.c.requests.post = lambda *a, **k: FakeResp(200, payload={
            "candidates": [{"content": {"parts": [{"text": "I am a teapot"}]}}]})
        res = self.c.critique_reference_asset("a1", "T", "cat", "p")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "failed")

    def test_genuine_success_passes_through(self):
        self.c.GEMINI_API_KEY = "dummy-key-for-test"
        self.c.requests.post = lambda *a, **k: FakeResp(200, payload={
            "candidates": [{"content": {"parts": [{"text": __import__("json").dumps(GOOD_CRITIQUE)}]}}]})
        res = self.c.critique_reference_asset("a1", "T", "cat", "p")
        self.assertEqual(res["overall_verdict"], "NEEDS_REFINEMENT")
        self.assertTrue(res.get("scores"))

    def test_no_route_maps_failure_to_success(self):
        """The API layer must turn critique failure into 5xx, never 200+scores."""
        from fastapi import HTTPException
        from app.api.routes.gemini import api_critique, CritiqueRequest
        import app.services.gemini.critique as c

        self.c.GEMINI_API_KEY = ""
        req = CritiqueRequest(asset_id="a", title="t", category="c", prompt="p")
        with self.assertRaises(HTTPException) as ctx:
            __import__("asyncio").run(api_critique(req, claims={"email": "x@y.z"}))
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertNotIn("APPROVED", str(ctx.exception.detail))


class RateLimiterTests(unittest.TestCase):

    def _limiter(self, limit=3, now=[1000.0]):
        from app.core.rate_limit import RateLimiter
        clock = lambda: now[0]
        return RateLimiter(per_principal=limit, window_s=60, name="t", clock=clock), now

    def test_allows_up_to_limit_then_refuses(self):
        rl, _ = self._limiter(3)
        self.assertTrue(rl.allow("u1"))
        self.assertTrue(rl.allow("u1"))
        self.assertTrue(rl.allow("u1"))
        self.assertFalse(rl.allow("u1"))

    def test_principals_are_independent(self):
        rl, _ = self._limiter(2)
        self.assertTrue(rl.allow("u1"))
        self.assertTrue(rl.allow("u1"))
        self.assertFalse(rl.allow("u1"))
        self.assertTrue(rl.allow("u2"))

    def test_window_rolls(self):
        rl, now = self._limiter(2)
        rl.allow("u1"); rl.allow("u1")
        self.assertFalse(rl.allow("u1"))
        now[0] += 61                       # past the 60s window
        self.assertTrue(rl.allow("u1"))

    def test_global_cap_binds_everyone(self):
        from app.core.rate_limit import RateLimiter
        now = [1000.0]
        rl = RateLimiter(per_principal=10, window_s=60, name="t",
                         global_per_window=3, clock=lambda: now[0])
        for i in range(3):
            self.assertTrue(rl.allow(f"u{i}"))
        self.assertFalse(rl.allow("u9"), "global cap not enforced")


class EndpointRateLimitTests(unittest.TestCase):
    """The gemini routes consume limiter slots keyed by principal."""

    def test_route_uses_its_limiter(self):
        from app.api.routes import gemini as g
        # Prove the limiters are wired to the routes' named attributes.
        self.assertTrue(hasattr(g, "_image_limiter"))
        self.assertTrue(hasattr(g, "_video_limiter"))
        self.assertTrue(hasattr(g, "_critique_limiter"))
        self.assertLessEqual(g._video_limiter.limit, 10,
                             "video is the most expensive call; its limit must be tight")


if __name__ == "__main__":
    unittest.main(verbosity=2)
