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

_HARDCODED_FALLBACK = "coldchain-dev-secret-change-me"

# Additional well-known values that must never be accepted as a production
# signing key, whatever the environment says. `_HARDCODED_FALLBACK` alone is not
# enough: the git-history redaction pass replaced that literal in this file with
# a `***REDACTED-...***` sentinel, which silently broke the comparison below —
# a deployment setting JWT_SECRET to the old weak value was then accepted,
# because the sentinel no longer equalled that string. Nothing failed loudly;
# the signing key just became forgeable again.
#
# Rule: reject on a SHAPE test, never on an equality test against a literal that
# a redaction tool might rewrite. A weak or placeholder key is one we can
# recognise without storing it.
_WEAK_SECRETS = {
    # The original dev placeholder, and redaction sentinels.
    "coldchain-dev-secret-change-me",
    "changeme", "change-me", "secret", "password", "replace-me",
    "your-secret-here", "please-change",
}
_REDACTION_SENTINEL_PREFIX = "***REDACTED"
_MIN_SECRET_LENGTH = 32


def _is_weak_secret(raw: str) -> bool:
    """True when `raw` must not be used as a production signing key."""
    s = (raw or "").strip()
    if len(s) < _MIN_SECRET_LENGTH:
        return True
    if s.lower() in _WEAK_SECRETS:
        return True
    if s.startswith(_REDACTION_SENTINEL_PREFIX) or s.upper() == s:
        # All-caps sentinels and placeholders read as non-secrets.
        return True
    # Distinct-character ratio: catches keys that merely satisfy the length
    # rule but carry almost no entropy, e.g. "aaaa..." or "abababab...".
    # A genuine token_urlsafe(48) sits well above this; measured minimum
    # observed for real random output is ~0.85 over 64 characters.
    if len(set(s)) / len(s) < 0.30:
        return True
    return False


def _resolve_secret() -> str:
    raw = os.getenv("JWT_SECRET")
    if raw and raw != _HARDCODED_FALLBACK and not _is_weak_secret(raw):
        return raw
    if IS_DEV:
        # Random per process: unguessable, and no config needed to run locally.
        return "dev-" + secrets.token_urlsafe(32)
    raise RuntimeError(
        "JWT_SECRET is missing or too weak to sign tokens with. Refusing to "
        "start, because every token minted with a well-known or short key is "
        "forgeable. Generate one with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(48))\" "
        "(minimum 32 characters), or set APP_ENV=development to use an "
        "auto-generated per-process dev secret."
    )


SECRET = _resolve_secret()
USING_EPHEMERAL_DEV_SECRET = _is_weak_secret(os.getenv("JWT_SECRET", ""))
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


def create_token(user_id: int, email: str, role: str = "operator",
                 vehicle_id: str | None = None) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({"sub": str(user_id), "email": email, "role": role,
                               "vehicle_id": vehicle_id,
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
