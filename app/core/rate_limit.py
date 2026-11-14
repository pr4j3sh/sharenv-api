import asyncio
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowCounter:
    def __init__(self) -> None:
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def locked(self, key: str, limit: int, window_seconds: int) -> int:
        async with self._lock:
            now = self._prune(key, window_seconds)
            events = self._events[key]

            if len(events) < limit:
                return 0

            return max(int(events[0] + window_seconds - now) + 1, 1)

    async def allow(self, key: str, limit: int, window_seconds: int) -> int:
        async with self._lock:
            now = self._prune(key, window_seconds)
            events = self._events[key]

            if len(events) >= limit:
                return max(int(events[0] + window_seconds - now) + 1, 1)

            events.append(now)
            self._compact()
            return 0

    async def record(self, key: str, window_seconds: int) -> None:
        async with self._lock:
            now = self._prune(key, window_seconds)
            self._events[key].append(now)
            self._compact()

    async def clear(self, key: str) -> None:
        async with self._lock:
            self._events.pop(key, None)

    def _prune(self, key: str, window_seconds: int) -> float:
        now = time.monotonic()
        cutoff = now - window_seconds
        events = self._events[key]
        while events and events[0] <= cutoff:
            events.pop(0)
        return now

    def _compact(self) -> None:
        if len(self._events) > settings.RATE_LIMIT_MAX_KEYS:
            self._events = {
                key: events for key, events in self._events.items() if events
            }


auth_ip_limits = SlidingWindowCounter()
login_failures = SlidingWindowCounter()
otp_attempts = SlidingWindowCounter()
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
