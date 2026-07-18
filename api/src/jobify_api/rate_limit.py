"""Redis-backed fixed-window limits for authentication endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class RateLimiter(Protocol):
    async def hit(self, *, key: str, limit: int, window_seconds: int) -> int: ...


@dataclass(frozen=True)
class RateLimitExceededError(Exception):
    retry_after: int


class RedisRateLimiter:
    _SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""

    def __init__(self, redis_client: object, *, prefix: str = "jobify:rate") -> None:
        self._redis = redis_client
        self._prefix = prefix

    async def hit(self, *, key: str, limit: int, window_seconds: int) -> int:
        result = await self._redis.eval(  # type: ignore[attr-defined]
            self._SCRIPT,
            1,
            f"{self._prefix}:{key}",
            window_seconds,
        )
        current, ttl = int(result[0]), max(int(result[1]), 1)
        if current > limit:
            raise RateLimitExceededError(retry_after=ttl)
        return max(limit - current, 0)


def client_address(request: object) -> str:
    """Return the socket peer address; proxy trust belongs at the ingress."""
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return host if isinstance(host, str) and host else "unknown"
