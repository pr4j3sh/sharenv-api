"""In-memory sliding-window rate limiting for the auth endpoints.

Single-process only: with more than one uvicorn worker these counters no
longer share state (nginx adds a coarse outer limit via ``limit_req``).
Keys are pruned lazily so memory stays bounded.
"""

import asyncio
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.core.config import settings

_MAX_KEYS = 10_000


class SlidingWindowCounter:
    """Sliding-window counters guarded by an asyncio lock."""

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def locked(self, key: str, limit: int, window_seconds: int) -> int:
        """Seconds until ``key`` is allowed again, or 0 when under the limit.

        Does not consume a slot; pair with ``record`` on failures.
        """
        async with self._lock:
            now = self._prune(key, window_seconds)
            events = self._events[key]

            if len(events) < limit:
                return 0

            return max(int(events[0] + window_seconds - now) + 1, 1)

    async def allow(self, key: str, limit: int, window_seconds: int) -> int:
        """Like ``locked``, but consumes a slot when allowed."""
        async with self._lock:
            now = self._prune(key, window_seconds)
            events = self._events[key]

            if len(events) >= limit:
                return max(int(events[0] + window_seconds - now) + 1, 1)

            events.append(now)
            self._compact()
            return 0

    async def record(self, key: str, window_seconds: int) -> None:
        """Record a failure event (not limited by itself)."""
        async with self._lock:
            now = self._prune(key, window_seconds)
            self._events[key].append(now)
            self._compact()

    async def clear(self, key: str) -> None:
        async with self._lock:
            self._events.pop(key, None)

    def _prune(self, key: str, window_seconds: int) -> float:
        """Caller must hold the lock. Drops expired events, returns the time."""
        now = time.monotonic()
        cutoff = now - window_seconds
        events = self._events[key]
        while events and events[0] <= cutoff:
            events.pop(0)
        return now

    def _compact(self) -> None:
        """Caller must hold the lock. Bounds total memory."""
        if len(self._events) > _MAX_KEYS:
            self._events = {
                key: events for key, events in self._events.items() if events
            }


# Per-IP requests across all /v1/auth/* routes.
auth_ip_limits = SlidingWindowCounter()
# Failed login attempts per email; cleared on successful login.
login_failures = SlidingWindowCounter()
# Wrong OTP guesses per user id; cleared on successful verification.
otp_attempts = SlidingWindowCounter()
# OTP resends per user id.
otp_resends = SlidingWindowCounter()


async def enforce_auth_ip_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"

    retry_after = await auth_ip_limits.allow(
        f"ip:{ip}", settings.AUTH_RATE_LIMIT_PER_IP, 60
    )

    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(retry_after)},
        )
