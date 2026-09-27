"""Security helpers: password hashing + JWT (HS256)."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, secrets, time

# --- JWT signing key -------------------------------------------------------
# Previously: SECRET = os.getenv("JWT_SECRET", "***REDACTED-JWT-PLACEHOLDER***")
# That default was a live vulnerability, not a convenience. The fallback string
# is public (it sat in git history at dfcd959), and anyone who knows it can mint
# a token for any user_id, so the "auth" boundary was forgeable by default.
#
# Behaviour now:
#   * explicit JWT_SECRET in the environment -> used as-is.
#   * otherwise, if we are clearly in local development, generate a RANDOM
#     per-process secret. Dev keeps working with no setup, and the key is
#     unguessable -- it just changes on restart, which invalidates old tokens.
#   * otherwise (any non-dev environment) -> refuse to start. A deployable
#     deployment must supply its own key; silently falling back is how a
#     forgeable default reaches production.
#
# Set APP_ENV=development (or DEV=1) to opt into the generated-dev-secret path.
APP_ENV = (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()
IS_DEV = APP_ENV in {"dev", "development", "local", "test"} or bool(os.getenv("DEV"))

_HARDCODED_FALLBACK = "***REDACTED-JWT-PLACEHOLDER***"


def _resolve_secret() -> str:
    raw = os.getenv("JWT_SECRET")
    if raw and raw != _HARDCODED_FALLBACK:
        return raw
    if IS_DEV:
        # Random per process: unguessable, and no config needed to run locally.
        return "dev-" + secrets.token_urlsafe(32)
    raise RuntimeError(
        "JWT_SECRET is not set to a real value. Refusing to start with a "
        "well-known signing key, because every token would be forgeable. "
        "Set JWT_SECRET to a strong random value, or set APP_ENV=development "
        "to use an auto-generated per-process dev secret."
    )


SECRET = _resolve_secret()
USING_EPHEMERAL_DEV_SECRET = os.getenv("JWT_SECRET") in (None, "", _HARDCODED_FALLBACK)
TOKEN_TTL = 60 * 60 * 12


def hash_password(pw: str) -> str:
    salt = os.urandom(12)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000)
    return "pbkdf2$" + base64.b64encode(salt + dk).decode()


def verify_password(pw: str, stored: str) -> bool:
    try:
        raw = base64.b64decode(stored.split("$", 1)[1])
        salt, dk = raw[:12], raw[12:]
        dk2 = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 120_000)
        return hmac.compare_digest(dk, dk2)
    except Exception:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_token(user_id: int, email: str) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({"sub": str(user_id), "email": email,
                               "exp": int(time.time()) + TOKEN_TTL}).encode())
    sig = _b64(hmac.new(SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def decode_token(token: str) -> dict | None:
    try:
        header, payload, sig = token.split(".")
        expected = _b64(hmac.new(SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(time.time()) > int(data.get("exp", 0)):
            return None
        return data
    except Exception:
        return None
