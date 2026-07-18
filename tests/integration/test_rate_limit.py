from __future__ import annotations

import os
from uuid import uuid4

import pytest
import redis.asyncio

from jobify_api.rate_limit import RateLimitExceededError, RedisRateLimiter

pytestmark = pytest.mark.integration


async def test_rate_limit_lua_allows_limit_and_rejects_next() -> None:
    client = redis.asyncio.Redis.from_url(os.environ["JOBIFY_REDIS_URL"])
    prefix = f"test:rate:{uuid4()}"
    redis_key = f"{prefix}:boundary"
    limiter = RedisRateLimiter(client, prefix=prefix)

    try:
        assert await limiter.hit(key="boundary", limit=2, window_seconds=60) == 1
        assert await limiter.hit(key="boundary", limit=2, window_seconds=60) == 0
        with pytest.raises(RateLimitExceededError) as raised:
            await limiter.hit(key="boundary", limit=2, window_seconds=60)
        assert 1 <= raised.value.retry_after <= 60
    finally:
        try:
            await client.delete(redis_key)
        finally:
            await client.aclose()
