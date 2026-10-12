"""Short-lived, single-use WebSocket connection tickets.

WHY NOT JUST PASS THE SESSION TOKEN
-----------------------------------
The frontend used to open `new WebSocket(WS_URL)` with no credential at all, so
`/ws` handed the entire fleet broadcast stream — positions, temperatures,
incidents, operator approval decisions — to anyone who asked.

A browser cannot attach an `Authorization` header to a WebSocket handshake, so
the credential has to ride in the handshake itself. Putting the 12-hour session
JWT there (or in a query string, which uvicorn logs verbatim) would leak a
long-lived credential into logs and browser history. Instead the client mints a
short-lived ticket over the authenticated REST API and presents that.

WHY SINGLE-USE NEEDS A STORE, NOT A SIGNED TOKEN
------------------------------------------------
A signed token stays valid until it expires, so capturing one from a log or a
proxy replay of the handshake yields a working credential for its whole life.
Single-use is impossible to express in a self-contained token — it needs
server-side state. This module keeps that state in memory, which matches the
current single-process application. The trade-off is real and deliberate: a
restart voids all outstanding tickets (harmless — the client just mints another)
and a multi-worker deployment would break self-consistency, because worker A
cannot see the tickets worker B minted. Multi-worker deployments need Redis or a
shared table; see `docs` note in the phase report. `MAX_OUTSTANDING` bounds the
damage an unauthenticated flood could do.
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger("coldchain.ws.tickets")

# A ticket only has to survive one handshake: mint -> connect. 30s is generous for
# that and tiny compared to a session lifetime.
TICKET_TTL_S = 30

# Both are abuse controls, not capacity planning. Beyond these, a caller is
# either buggy or hostile; a bounded failure beats an unbounded allocation.
MAX_OUTSTANDING = 500        # tickets minted but not yet consumed
MAX_CONSUMED_KEPT = 4000     # tombstones, so a replay is distinguishable from garbage
MAX_MINTS_PER_PRINCIPAL_PER_MIN = 30
MAX_MINTS_GLOBAL_PER_MIN = 600


def _fingerprint(ticket: str) -> str:
    """A stable, non-reversible id for logs.

    Never log a ticket value itself: it is a bearer credential, and application
    logs are far more widely readable than the ticket store.
    """
    import hashlib
    return hashlib.sha256(ticket.encode()).hexdigest()[:12]


@dataclass
class Ticket:
    value: str
    user_id: int
    email: str
    role: str
    vehicle_id: str | None
    scope: str                     # "fleet" (operator) | "vehicle" (driver)
    issued_at: float
    expires_at: float
    consumed_at: float | None = None
    consumed_by: str | None = None
    meta: dict = field(default_factory=dict)

    def is_expired(self, now: float | None = None) -> bool:
        return (now or time.time()) >= self.expires_at


class TicketRejected(Exception):
    """A presented ticket is not usable. Never carries the ticket value."""

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(reason)


class _RateWindow:
    """Fixed-window counter. Small, monotonic, and cannot grow without bound."""

    def __init__(self, limit: int, window_s: int = 60):
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, tuple[int, int]] = {}   # key -> (window_index, count)

    def allow(self, key: str, now: float | None = None) -> bool:
        idx = int((now or time.time()) // self.window_s)
        prev, count = self._hits.get(key, (idx, 0))
        if prev != idx:
            count = 0
        if count >= self.limit:
            self._hits[key] = (idx, count)
            return False
        self._hits[key] = (idx, count + 1)
        # Opportunistic pruning: this dict is per-principal and would otherwise
        # retain an entry for every email that ever minted a ticket.
        if len(self._hits) > 512:
            self._hits = {k: v for k, v in self._hits.items() if v[0] == idx}
        return True


class TicketStore:
    """In-memory single-use tickets.

    EVERY mutation takes the lock, including `consume`, so two concurrent
    handshakes presenting the same ticket cannot both win: the first sets
    `consumed_at` under the lock and the second observes it and is rejected.
    A read-then-write without the lock would let both through.
    """

    def __init__(self, ttl_s: int = TICKET_TTL_S):
        self.ttl_s = ttl_s
        self._lock = threading.Lock()
        self._outstanding: dict[str, Ticket] = {}
        self._consumed: dict[str, Ticket] = {}
        self._per_principal = _RateWindow(MAX_MINTS_PER_PRINCIPAL_PER_MIN)
        self._global = _RateWindow(MAX_MINTS_GLOBAL_PER_MIN)

    # ---- minting -----------------------------------------------------------

    def mint(self, *, user_id: int, email: str, role: str,
             vehicle_id: str | None, now: float | None = None) -> tuple[str, float]:
        """Create a ticket bound to this principal and its telemetry scope.

        Returns (ticket_value, expires_at). Raises TicketRejected if rate limited.
        """
        now = now or time.time()

        # is_signed: secrets.token_urlsafe is a CSPRNG directly, not a PRNG seeded
        # per process. Do NOT use random.random()/randint here: Mersenne Twister
        # output is predictable from a handful of samples, which is exactly the
        # property a guessing attacker needs.
        value = secrets.token_urlsafe(32)

        scope = "vehicle" if role == "driver" and vehicle_id else "fleet"

        with self._lock:
            if not self._global.allow("*", now):
                raise TicketRejected("rate_limited", "global mint limit reached")
            if not self._per_principal.allow(email or str(user_id), now):
                raise TicketRejected("rate_limited", "per-principal mint limit reached")

            self._prune(now)

            t = Ticket(value=value, user_id=user_id, email=email, role=role,
                       vehicle_id=vehicle_id, scope=scope, issued_at=now,
                       expires_at=now + self.ttl_s)
            self._outstanding[value] = t

        log.info("ws ticket minted fp=%s role=%s scope=%s",
                 _fingerprint(value), role, scope)
        return value, t.expires_at

    # ---- consuming ---------------------------------------------------------

    def consume(self, value: str, *, consumer: str = "", now: float | None = None) -> Ticket:
        """Atomically claim a ticket. Raises TicketRejected on any problem."""
        now = now or time.time()
        if not value or not isinstance(value, str):
            raise TicketRejected("missing", "no ticket presented")

        with self._lock:
            # Already used -> replay. Checked FIRST so a replay of a valid-looking
            # ticket is reported as a replay rather than as expired.
            used = self._consumed.get(value)
            if used is not None:
                log.warning("ws ticket REPLAY fp=%s first_consumer=%s",
                            _fingerprint(value), used.consumed_by or "?")
                raise TicketRejected("replayed",
                                     "this ticket has already been used")

            t = self._outstanding.get(value)
            if t is None:
                # Burn a comparison so a probe of random values is not several
                # times cheaper than a probe of live ones.
                secrets.compare_digest(value, secrets.token_urlsafe(32))
                log.warning("ws ticket unknown fp=%s", _fingerprint(value))
                raise TicketRejected("unknown", "ticket not recognised")

            if t.is_expired(now):
                del self._outstanding[value]
                log.warning("ws ticket expired fp=%s", _fingerprint(value))
                raise TicketRejected("expired", "ticket has expired")

            # Claim it: remove from outstanding and record the tombstone, both
            # inside the lock, so no second consumer can pass.
            del self._outstanding[value]
            t.consumed_at = now
            t.consumed_by = consumer or "?"
            self._consumed[value] = t

        log.info("ws ticket consumed fp=%s role=%s scope=%s by=%s",
                 _fingerprint(value), t.role, t.scope, t.consumed_by)
        return t

    # ---- housekeeping ------------------------------------------------------

    def _prune(self, now: float) -> None:
        """Drop expired outstanding tickets and old tombstones. Caller holds lock."""
        if len(self._outstanding) > MAX_OUTSTANDING:
            for k in [k for k, v in self._outstanding.items() if v.is_expired(now)]:
                del self._outstanding[k]
            if len(self._outstanding) > MAX_OUTSTANDING:
                # Still full of live tickets: refuse rather than grow.
                raise TicketRejected("too_many_outstanding",
                                     "too many unclaimed tickets; try again shortly")
        if len(self._consumed) > MAX_CONSUMED_KEPT:
            # Tombstones only need to outlive the replay window they defend; the
            # oldest are dropped by insertion order.
            for k in list(self._consumed)[: len(self._consumed) - MAX_CONSUMED_KEPT]:
                del self._consumed[k]

    def stats(self) -> dict:
        with self._lock:
            return {"outstanding": len(self._outstanding),
                    "consumed_kept": len(self._consumed)}


# Single process-wide store. Tests build their own to stay isolated.
STORE = TicketStore()
