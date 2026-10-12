"""Route protection for operational endpoints.

Why this exists
---------------
`/api/auth/*` has always implemented register/login/`me` with pbkdf2 hashing
and HS256 JWTs, but for a long time nothing *depended* on it. All `/api/fleet/*`
endpoints were reachable by anyone who could open the port, including the
destructive ones: `inject` (force a compressor failure), `service/dispatch`,
`transfer` (move cargo between trucks), `speed`, `weather`, `rebuild`.

Fail closed (changed 2026-10-12)
--------------------------------
This module used to model protection as *environment-shaped*: development
granted anonymous writes so the demo stayed runnable. Reviewed, that was the
wrong trade — `APP_ENV=development` silently turned every protected route into
an anonymous one, so a dev-mode deployment had no authorization at all and
nothing distinguished "the operator is signed in" from "nobody is". A security
control that a single env var disables by default is not a control.

Now `require_auth` ALWAYS requires a valid bearer token. There is no implicit
dev bypass. If a genuinely open demo is needed, `ALLOW_ANONYMOUS_WRITES=1` must
be set explicitly, and it logs a warning on every anonymous write it admits so
the state is never invisible.

Role enforcement is server-side (`require_role`). The frontend already hid
operator controls from driver accounts, but that is presentation: a driver could
still call the endpoints directly. The JWT carries `role` and `vehicle_id`, and
these dependencies are what actually decide.

Read endpoints stay open by default (`REQUIRE_AUTH_READS`): the dashboard, map
and analytics panels poll continuously and gating them turns "not signed in yet"
into a blank screen. Set `REQUIRE_AUTH_READS=true` for a public deployment.
Sensitive reads (incident reports) are protected explicitly regardless.
"""
from __future__ import annotations

import logging
import os

from fastapi import Depends, Header, HTTPException

from ..core.security import decode_token

log = logging.getLogger("authz")

APP_ENV = (os.getenv("APP_ENV") or os.getenv("ENV") or "").strip().lower()
IS_DEV = APP_ENV in {"dev", "development", "local", "test"} or bool(os.getenv("DEV"))


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Kept for compatibility with callers that referenced it; it no longer decides
# whether writes are authorized (see the module docstring).
REQUIRE_AUTH = True
# Deliberate, explicit, off-by-default escape hatch for a demo box. Never set
# this on anything reachable from an untrusted network.
ALLOW_ANONYMOUS_WRITES = _flag("ALLOW_ANONYMOUS_WRITES", False)
# Public deployment hardening: also require a token to read.
REQUIRE_AUTH_READS = _flag("REQUIRE_AUTH_READS", False)


def _ephemeral_secret_guard() -> None:
    """Refuse with 503 when protection is on but no token can be ISSUED.

    Only enforced OUTSIDE development. In dev the secret is random per process,
    which is fine on a laptop: tokens are unforgeable from outside even though
    they do not survive a restart. Raising here in dev would 503 every protected
    route on a default `APP_ENV=development` launch — that is the "undemoable
    product" failure mode, and a guard that blocks legitimate use gets deleted.

    Outside dev an ephemeral/well-known key is a real deployment hazard, so it is
    refused loudly rather than left as a silent weakness.
    """
    if IS_DEV:
        return
    try:
        from ..core.security import USING_EPHEMERAL_DEV_SECRET

        if USING_EPHEMERAL_DEV_SECRET:
            raise HTTPException(
                503,
                "Authentication is required but JWT_SECRET is not configured, so "
                "no token can be issued. Set a strong JWT_SECRET (32+ random "
                "characters) before serving requests.",
            )
    except ImportError:  # pragma: no cover
        pass


def require_auth(
    authorization: str | None = Header(None),
) -> dict:
    """Validate a bearer token and return its claims. Fails closed."""
    _ephemeral_secret_guard()

    if not authorization or not authorization.lower().startswith("bearer "):
        if ALLOW_ANONYMOUS_WRITES:
            log.warning("anonymous write admitted (ALLOW_ANONYMOUS_WRITES=1)")
            return {"sub": "anonymous", "role": "anonymous", "mode": "explicit-opt-in"}
        raise HTTPException(
            401,
            "Missing bearer token. POST /api/auth/login to obtain one, then send "
            "it as `Authorization: Bearer <token>`.",
        )
    claims = decode_token(authorization.split(None, 1)[1])
    if not claims:
        raise HTTPException(401, "Invalid or expired token.")
    # Accounts created before RBAC have no role claim; they are operators, which
    # is exactly what the column default says.
    claims.setdefault("role", "operator")
    claims.setdefault("vehicle_id", None)
    return claims


def require_auth_read(
    authorization: str | None = Header(None),
) -> dict:
    """Same as `require_auth`, but inert unless REQUIRE_AUTH_READS is set."""
    if not REQUIRE_AUTH_READS:
        return {"sub": "anonymous", "role": "anonymous", "mode": "reads-open"}
    return require_auth(authorization)


def require_role(*roles: str):
    """Dependency factory: the caller's role must be one of `roles`.

    Server-side authority. The frontend also hides controls, but hiding a button
    is presentation — this is what a driver cannot get around by calling the API
    directly.
    """
    allowed = set(roles)

    def _dep(claims: dict = Depends(require_auth)) -> dict:
        role = (claims or {}).get("role") or "anonymous"
        if role not in allowed:
            raise HTTPException(
                403,
                f"This operation requires role {' or '.join(sorted(allowed))}; "
                f"the presented token carries '{role}'.",
            )
        return claims

    return _dep


def require_vehicle_scope(vehicle_id: str, claims: dict) -> None:
    """A driver may only act on the vehicle their account is bound to.

    Operators are unrestricted. Raises 403 otherwise. Call this inside a route
    that already depends on `require_auth`, passing the id from the path.
    """
    role = (claims or {}).get("role")
    if role != "driver":
        return
    owned = (claims or {}).get("vehicle_id")
    if not owned or owned != vehicle_id:
        raise HTTPException(
            403,
            f"Driver accounts may only operate their assigned vehicle "
            f"({owned or 'none assigned'}), not {vehicle_id}.",
        )
