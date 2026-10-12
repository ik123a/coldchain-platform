"""Resolve client-supplied reference-image identifiers to approved local assets.

WHY THIS EXISTS
---------------
`generate-reference-image` and `generate-reference-video` accepted
`reference_images: List[str]` and passed each entry straight to
`Path(p).open("rb")`, base64-encoding whatever it read and POSTing it to Google.
The caller therefore chose the path. `["../../../backend/.env"]`,
`["C:/Users/<user>/.ssh/id_rsa"]` or any readable file on the host would be read
and sent to an external model provider — arbitrary local file disclosure, with
the response body potentially echoing the content back.

The fix is to stop trusting paths entirely. A client now supplies one of:
  * an ASSET ID from the prompt catalogue (`map-01-dark-command-center`), resolved
    to `<approved_root>/images/<id>.png` or `<approved_root>/videos/<id>.*`; or
  * a plain FILENAME that exists directly inside the approved images directory.

Anything containing a path separator, a drive prefix, or `..` is rejected before
any filesystem call, and the fully resolved path is confirmed to sit inside the
approved root afterwards (`Path.resolve()` + `is_relative_to`, which defeats both
traversal and symlinks that escape the directory).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("coldchain.gemini.assets")

# The only directory a generation request may read images from. Both the repo-root
# and frontend-public copies exist; the repo-root one is canonical for the backend.
_BACKEND_DIR = Path(__file__).resolve().parents[3]
APPROVED_ROOT = Path(
    os.getenv("GEMINI_ASSET_ROOT") or (_BACKEND_DIR.parent / "design-references")
).resolve()
APPROVED_IMAGES = APPROVED_ROOT / "images"

# Matches the content types the two upstream APIs accept. Anything else is
# rejected rather than guessed at.
ALLOWED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# One reference image may be at most this large. Base64 inflates by ~4/3, and the
# whole payload goes into a single JSON POST, so an unbounded read is both a
# memory and an egress problem.
MAX_REFERENCE_BYTES = int(os.getenv("GEMINI_MAX_REFERENCE_BYTES", 8 * 1024 * 1024))


class ReferenceRejected(Exception):
    """A caller-supplied reference could not be resolved to an approved asset."""


def _looks_like_a_path(raw: str) -> bool:
    """True if `raw` is trying to name a location rather than an asset.

    Checked BEFORE touching the filesystem, so a rejected request never causes a
    stat/open on an attacker-chosen path.
    """
    if not raw or not raw.strip():
        return True
    if "\x00" in raw:
        return True
    # Any directory component, drive letter, or UNC prefix.
    if "/" in raw or "\\" in raw:
        return True
    if ":" in raw:                      # C:..., or a URL scheme
        return True
    if raw in {".", ".."} or raw.startswith(".."):
        return True
    return False


def resolve_reference(raw: str) -> Path:
    """Map a client reference to a path inside the approved directory, or raise.

    Never returns a path outside `APPROVED_IMAGES`.
    """
    if not isinstance(raw, str):
        raise ReferenceRejected(f"reference must be a string, got {type(raw).__name__}")
    if _looks_like_a_path(raw):
        raise ReferenceRejected(
            f"reference {raw!r} looks like a filesystem path. Send an asset id "
            f"(e.g. 'map-01-dark-command-center') or a bare filename from the "
            f"approved reference library."
        )

    suffix = Path(raw).suffix.lower()
    if suffix and suffix not in ALLOWED_SUFFIXES:
        raise ReferenceRejected(f"unsupported reference type {suffix!r}")

    # An asset id from the catalogue; ids contain no extension.
    candidates = [raw] if suffix else [raw + ext for ext in (".png", ".jpg", ".jpeg", ".webp")]
    for name in candidates:
        candidate = APPROVED_IMAGES / name
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        # resolve() has followed every symlink by now, so this is the check that
        # actually matters — a link pointing outside the root fails here.
        if not resolved.is_relative_to(APPROVED_IMAGES):
            raise ReferenceRejected(
                f"reference {raw!r} resolves outside the approved directory")
        size = resolved.stat().st_size
        if size > MAX_REFERENCE_BYTES:
            raise ReferenceRejected(
                f"reference {raw!r} is {size} bytes, over the "
                f"{MAX_REFERENCE_BYTES}-byte limit")
        return resolved

    raise ReferenceRejected(
        f"no approved reference asset matches {raw!r} in {APPROVED_IMAGES.name}/")


def read_reference(raw: str) -> tuple[bytes, str]:
    """Read an approved reference, returning (bytes, mime_type)."""
    path = resolve_reference(raw)
    mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else (
        "image/webp" if path.suffix.lower() == ".webp" else "image/png")
    with open(path, "rb") as fh:
        return fh.read(MAX_REFERENCE_BYTES + 1), mime
