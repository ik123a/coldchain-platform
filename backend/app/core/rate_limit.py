"""Per-principal sliding-window rate limiter for billable operations.

A counter class, deliberately: image/video generation and critique each cost
real money per call, and before this file there was nothing stopping a client
(or a stuck frontend loop) from minting unlimited billable requests.

Single-process, in-memory — the same documented limitation as the WebSocket
ticket store. A restart clears the counters (harmless: the window is seconds) and
a multi-worker deployment would NOT share them, so per-worker limits would be
`limit × workers`. Documented in FINAL_ENGINEERING_AND_SECURITY_REPORT.md.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Fixed-window counter keyed by principal.

    `allow()` is the only gate a caller needs; `check()` reports state without
    consuming. All state lives under one lock — the class is shared across
    asyncio request handlers, which are single-threaded per event loop, but the
    same store may also be touched from test threads.
    """

    def __init__(self, per_principal: int, window_s: int = 60, name: str = "limiter",
                 global_per_window: int | None = None, clock=time.time):
        self.limit = max(1, int(per_principal))
        self.global_limit = global_per_window
        self.window_s = window_s
        self.name = name
        self._clock = clock          # injectable for deterministic tests
        self._lock = threading.Lock()
        self._hits: dict[str, deque] = defaultdict(deque)
        self._global_hits: deque = deque()

    def _window_start(self, now: float) -> float:
        return now - self.window_s

    def allow(self, principal: str) -> bool:
        """Consume one slot for `principal`, or refuse. Returns True if allowed."""
        now = self._clock()
        cutoff = self._window_start(now)
        with self._lock:
            q = self._hits[principal]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return False
            if self.global_limit is not None:
                g = self._global_hits
                while g and g[0] <= cutoff:
                    g.popleft()
                if len(g) >= self.global_limit:
                    return False
                g.append(now)
            q.append(now)
            # Opportunistic retention cap: a principal storm cannot grow state.
            if len(self._hits) > 4096:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]
                if len(self._hits) > 4096:
                    # Last resort: drop the oldest half by insertion order.
                    for k in list(self._hits)[: len(self._hits) // 2]:
                        del self._hits[k]
            return True

    def check(self, principal: str) -> dict:
        """Read-only state (used by tests and the status endpoint)."""
        now = self._clock()
        cutoff = self._window_start(now)
        with self._lock:
            q = self._hits.get(principal)
            used = sum(1 for t in (q or ()) if t > cutoff)
            return {"name": self.name, "limit": self.limit, "used": used,
                    "window_s": self.window_s}


def too_many(detail: str = "rate limit exceeded; retry later") -> HTTPException:
    return HTTPException(429, detail)
