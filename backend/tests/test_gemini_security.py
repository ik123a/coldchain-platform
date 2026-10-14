"""Gemini reference-image security: arbitrary local file read must be impossible.

THE VULNERABILITY THESE PIN DOWN
--------------------------------
`generate-reference-image` / `generate-reference-video` accepted
`reference_images: List[str]` and passed each entry to `Path(p).open("rb")`,
base64-encoding what it read and POSTing it to Google. The CLIENT chose the path,
so `../../../backend/.env` or `~/.ssh/id_rsa` would be read and exfiltrated to an
external provider.

Every test here can FAIL against the pre-fix code, which is the point.

Database isolation: the real redirect is irrelevant to these (no DB is touched),
but the module is still imported through the same app package.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("APP_ENV", "development")

from app.services.gemini.safe_paths import (  # noqa: E402
    ALLOWED_SUFFIXES, APPROVED_IMAGES, MAX_REFERENCE_BYTES,
    ReferenceRejected, read_reference, resolve_reference)

BACKEND = Path(__file__).resolve().parent.parent


class PathTraversalTests(unittest.TestCase):

    def test_dot_dot_traversal_is_rejected(self):
        for raw in ["../../../etc/passwd",
                    "..\\..\\..\\Windows\\System32\\drivers\\etc\\hosts",
                    "../../backend/.env",
                    "....//....//etc/passwd"]:
            with self.assertRaises(ReferenceRejected, msg=f"allowed {raw!r}"):
                resolve_reference(raw)

    def test_absolute_paths_are_rejected(self):
        for raw in ["/etc/passwd", "C:/Windows/win.ini", "C:\\Windows\\win.ini",
                    "\\\\server\\share\\file.png", "file:///etc/passwd"]:
            with self.assertRaises(ReferenceRejected, msg=f"allowed {raw!r}"):
                resolve_reference(raw)

    def test_repo_config_files_are_unreachable(self):
        """The concrete exfiltration target: the backend .env."""
        for raw in ["backend/.env", ".env", "../.env",
                    os.path.join(str(BACKEND), ".env")]:
            with self.assertRaises(ReferenceRejected, msg=f"allowed {raw!r}"):
                resolve_reference(raw)

    def test_null_byte_is_rejected(self):
        with self.assertRaises(ReferenceRejected):
            resolve_reference("map-01.png\x00.txt")

    def test_empty_and_whitespace_are_rejected(self):
        for raw in ["", "   ", ".", ".."]:
            with self.assertRaises(ReferenceRejected, msg=f"allowed {raw!r}"):
                resolve_reference(raw)

    def test_non_image_suffix_is_rejected(self):
        for raw in ["secrets.txt", "key.pem", "archive.zip", "db.sqlite"]:
            with self.assertRaises(ReferenceRejected, msg=f"allowed {raw!r}"):
                resolve_reference(raw)

    def test_unknown_asset_id_is_rejected(self):
        with self.assertRaises(ReferenceRejected):
            resolve_reference("no-such-asset-99")


class LegitimateWorkflowTests(unittest.TestCase):
    """The approved library must keep working — the fix must not break real use."""

    def test_a_real_catalogue_asset_resolves(self):
        # Pick any real file from the approved directory rather than hardcoding a
        # name that a future cleanup might rename.
        if not APPROVED_IMAGES.is_dir():
            self.skipTest("approved asset directory not present")
        pngs = [p for p in APPROVED_IMAGES.iterdir()
                if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES]
        if not pngs:
            self.skipTest("no approved images to resolve")
        resolved = resolve_reference(pngs[0].name)
        self.assertTrue(resolved.is_relative_to(APPROVED_IMAGES))
        self.assertEqual(resolved.name, pngs[0].name)

    def test_asset_id_without_extension_resolves(self):
        from app.services.gemini.prompts import IMAGE_PROMPTS
        if not APPROVED_IMAGES.is_dir():
            self.skipTest("approved asset directory not present")
        # An id resolves only if a file with that stem exists.
        for asset_id in list(IMAGE_PROMPTS)[:40]:
            candidate = APPROVED_IMAGES / f"{asset_id}.png"
            if candidate.exists():
                resolved = resolve_reference(asset_id)
                self.assertEqual(resolved.stem, asset_id)
                return
        self.skipTest("no catalogue id has a corresponding image file")

    def test_resolved_path_always_inside_approved_root(self):
        if not APPROVED_IMAGES.is_dir():
            self.skipTest("approved asset directory not present")
        for p in list(APPROVED_IMAGES.iterdir())[:20]:
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES:
                self.assertTrue(resolve_reference(p.name).is_relative_to(APPROVED_IMAGES))

    def test_read_reference_returns_bytes_and_mime(self):
        if not APPROVED_IMAGES.is_dir():
            self.skipTest("approved asset directory not present")
        for p in APPROVED_IMAGES.iterdir():
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES:
                data, mime = read_reference(p.name)
                self.assertIsInstance(data, bytes)
                self.assertTrue(data)
                self.assertTrue(mime.startswith("image/"))
                return
        self.skipTest("no approved images to read")


class BillableCallGuardTests(unittest.TestCase):
    """A rejected reference must NOT reach the upstream generation call."""

    def test_service_never_opens_an_unapproved_path(self):
        """Drive the real service with a traversal reference and a fake transport.

        The service must not open the attacker path, and must not POST. A mock
        transport stands in for requests.post so no billable call can occur — and
        if one is attempted the test fails.
        """
        import app.services.gemini.image_generation as ig

        calls = []
        original_post = ig.requests.post

        def spy_post(*a, **k):
            calls.append(a)
            raise AssertionError("an upstream (billable) call was attempted")

        ig.requests.post = spy_post
        # Force a key so the function proceeds past the early return.
        original_key = ig.GEMINI_API_KEY
        ig.GEMINI_API_KEY = "test-key-not-real"
        try:
            res = ig.generate_reference_image(
                prompt="x",
                reference_images=["../../../backend/.env"])
            self.assertIn("success", res)
            self.assertEqual(calls, [], "a billable call was made for a rejected reference")
        finally:
            ig.requests.post = original_post
            ig.GEMINI_API_KEY = original_key

    def test_route_rejects_before_calling_the_service(self):
        """The route must 400 on a bad reference, not silently generate."""
        from fastapi import HTTPException
        from app.api.routes.gemini import _validate_references

        with self.assertRaises(HTTPException) as ctx:
            _validate_references(["../../../backend/.env"])
        self.assertEqual(ctx.exception.status_code, 400)

        # A legitimate reference must NOT raise.
        if APPROVED_IMAGES.is_dir():
            for p in APPROVED_IMAGES.iterdir():
                if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES:
                    _validate_references([p.name])
                    break

    def test_request_models_bound_expensive_inputs(self):
        """Prompt length and video duration must be capped."""
        from app.api.routes.gemini import ImageGenRequest, VideoGenRequest
        import pydantic

        with self.assertRaises(pydantic.ValidationError):
            ImageGenRequest(prompt="x" * 5000)

        with self.assertRaises(pydantic.ValidationError):
            VideoGenRequest(prompt="x", duration_seconds=9999)

        with self.assertRaises(pydantic.ValidationError):
            ImageGenRequest(prompt="x", reference_images=["a", "b", "c", "d"])


class SecretHygieneTests(unittest.TestCase):
    """Credentials must never be reconstructable from logged artifacts."""

    def test_no_api_key_in_any_upstream_url(self):
        """The services must send keys via header, never the query string.

        Regression anchor: a failed-call test printed a LIVE Google API key
        because the URL embedded `?key=<value>` and the assertion diff echoed the
        URL. URLs get logged; headers do not.
        """
        import pathlib
        services = pathlib.Path(__file__).resolve().parent.parent / "app" / "services" / "gemini"
        offenders = []
        for f in services.glob("*.py"):
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if "key={" in line and ("url" in line or "http" in line):
                    offenders.append(f"{f.name}:{i}")
        self.assertEqual(offenders, [],
                         f"API key interpolated into URL(s): {offenders}")

    def test_operation_name_is_validated_before_reaching_a_url(self):
        from app.services.gemini.video_generation import check_video_operation
        for bad in ["", "../secret", "models//operations/x",
                    "models/m/operations/id?steal=1", "https://evil.example/x"]:
            res = check_video_operation(bad)
            self.assertFalse(res.get("success"), f"accepted malformed {bad!r}")
            self.assertIn("malformed", res.get("error", ""), f"bad error for {bad!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
