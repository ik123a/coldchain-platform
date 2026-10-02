"""Route protection for operational endpoints.

Why this exists
---------------
`/api/auth/*` has always implemented register/login/`me` with pbkdf2 hashing
and HS256 JWTs, but nothing *depended* on it. All 19 `/api/fleet/*` endpoints
were reachable by anyone who could open the port, including the destructive
ones: `inject` (force a compressor failure), `service/dispatch`, `transfer`
(move cargo between trucks), `speed`, `weather`, `rebuild`. Deploying that
publicly would hand a stranger the controls to the simulation.

Design: fail closed in production, invisible in development
------------------------------------------------------------
Requiring a token unconditionally would break the entire demo path — the
frontend has no login screen, and `StoreProvider` polls `/api/fleet/state`
plus several write endpoints on every load. A gate that makes the product
undemoable gets removed by the next person who needs to show it.

So protection is *environment-shaped*:

  * `REQUIRE_AUTH=true`   -> writes need a valid bearer token. The default
                             whenever APP_ENV is not a dev value.
  * development           -> writes stay open, and startup logs exactly why.

This is the same pattern `core/security.py` already uses for JWT_SECRET, so
there is one rule to learn: dev is permissive on purpose, and that permissiveness
is bounded by an explicit env value rather than by accident.

Read endpoints are NOT gated by default. The dashboard, the map and the
analytics panels poll continuously; gating reads turns "no token yet" into a
blank screen. Set `REQUIRE_AUTH_READS=true` to close them too (recommended for a
public deployment).
"""
from __future__ import annotations

import os

from fastapi import Depends, Header, HTTPException

from ..core.security import decode_token

APP_ENV = (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()
IS_DEV = APP_ENV in {"dev", "development", "local", "test"} or bool(os.getenv("DEV"))


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Fail closed: anything that is not explicitly a development environment
# requires a token. A typo in APP_ENV therefore protects rather than exposes.
REQUIRE_AUTH = _flag("REQUIRE_AUTH", not IS_DEV)
REQUIRE_AUTH_READS = _flag("REQUIRE_AUTH_READS", False)


def auth_required() -> None:
    """Dependency that rejects the request unless it carries a valid token.

    Raises 503 rather than 401 when protection is switched on but tokens cannot
    be issued at all, which distinguishes "you did not log in" from "this
    deployment is misconfigured".
    """
    if not REQUIRE_AUTH:
        return
    try:
        from ..core.security import USING_EPHEMERAL_DEV_SECRET

        if USING_EPHEMERAL_DEV_SECRET:
            raise HTTPException(
                503,
                "Authentication is required but JWT_SECRET is not configured, so "
                "no token can be issued. Set a strong JWT_SECRET (32+ random "
                "characters) before enabling REQUIRE_AUTH.",
            )
    except ImportError:  # pragma: no cover
        pass


def require_auth(
    authorization: str | None = Header(None),
) -> dict:
    """Validate a bearer token and return its claims."""
    auth_required()
    if not REQUIRE_AUTH:
        return {"sub": "anonymous", "mode": "dev-open"}

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            401,
            "Missing bearer token. POST /api/auth/login to obtain one, then send "
            "it as `Authorization: Bearer <token>`.",
        )
    claims = decode_token(authorization.split(None, 1)[1])
    if not claims:
        raise HTTPException(401, "Invalid or expired token.")
    return claims


def require_auth_read(
    authorization: str | None = Header(None),
) -> dict:
    """Same as `require_auth`, but inert unless REQUIRE_AUTH_READS is set."""
    if not REQUIRE_AUTH_READS:
        return {"sub": "anonymous", "mode": "reads-open"}
    return require_auth(authorization)


def protection_summary() -> dict:
    """Machine-readable description of the current posture, for /api/status."""
    return {
        "write_auth_required": REQUIRE_AUTH,
        "read_auth_required": REQUIRE_AUTH_READS,
        "environment": APP_ENV or "(unset)",
        "note": (
            "development mode leaves operational writes open so the demo runs "
            "without a login screen; production fails closed"
            if IS_DEV
            else "operational writes require a bearer token"
        ),
    }
