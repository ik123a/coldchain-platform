"""Security helpers: password hashing + JWT (HS256)."""
from __future__ import annotations
import base64, hashlib, hmac, json, os, time

SECRET = os.getenv("JWT_SECRET", "***REDACTED-JWT-PLACEHOLDER***")
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
